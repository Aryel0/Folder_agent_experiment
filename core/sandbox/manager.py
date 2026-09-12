from __future__ import annotations
import subprocess
import time
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List
from core.sandbox.config import SandboxConfig
from core.sandbox.security import (
    SecurityViolationError,
    SandboxError,
    build_docker_security_args,
    validate_security_policy
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Standardized result of a sandbox execution."""
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def output(self) -> str:
        """Combined readable output."""
        if self.timed_out:
            return f"Error: Command timed out after {self.duration:.1f}s.\n[stderr]: {self.stderr}"
        res = self.stdout
        if self.stderr:
            if res:
                res += f"\n[stderr]:\n{self.stderr}"
            else:
                res = f"[stderr]:\n{self.stderr}"
        return res or "(executed successfully, no output)"


class DockerSandbox:
    """Manages the lifecycle and secure execution inside an isolated Docker container."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        validate_security_policy(self.config)

    def is_docker_available(self) -> bool:
        """Check if Docker CLI and Engine daemon are responsive."""
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0
        except Exception as e:
            logger.debug(f"Docker availability check failed: {e}")
            return False

    def is_running(self) -> bool:
        """Check if the sandbox container is currently running."""
        try:
            res = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.config.container_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0 and res.stdout.strip().lower() == "true"
        except Exception:
            return False

    def create(self) -> bool:
        """Create the hardened sandbox container with all security constraints.
        
        Returns:
            bool: True if created successfully.
        """
        logger.info(f"Creating sandbox container '{self.config.container_name}'...")
        
        # Build strict security arguments
        sec_args = build_docker_security_args(self.config)

        # Remove existing container with same name if any
        self.destroy(remove_workspace=False)

        cmd = [
            "docker", "create",
            "--name", self.config.container_name,
            *sec_args,
            self.config.image_name,
            "sleep", "infinity"
        ]

        logger.debug(f"Docker create command: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise SandboxError(f"Failed to create sandbox container: {res.stderr.strip()}")

        logger.info(f"Container '{self.config.container_name}' created successfully.")
        return True

    def start(self) -> bool:
        """Start the sandbox container. If it doesn't exist, creates it first."""
        if self.is_running():
            logger.debug(f"Container '{self.config.container_name}' is already running.")
            return True

        # Check if container exists
        res = subprocess.run(
            ["docker", "inspect", self.config.container_name],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            # Container doesn't exist; create it
            self.create()

        logger.info(f"Starting sandbox container '{self.config.container_name}'...")
        start_res = subprocess.run(
            ["docker", "start", self.config.container_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if start_res.returncode != 0:
            raise SandboxError(f"Failed to start container: {start_res.stderr.strip()}")

        return True

    def stop(self, timeout: int = 5) -> bool:
        """Gracefully stop the running sandbox container."""
        if not self.is_running():
            return True

        logger.info(f"Stopping sandbox container '{self.config.container_name}'...")
        res = subprocess.run(
            ["docker", "stop", "-t", str(timeout), self.config.container_name],
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        return res.returncode == 0

    def destroy(self, remove_workspace: bool = False) -> bool:
        """Forcefully remove the sandbox container and optionally its workspace."""
        logger.info(f"Destroying sandbox container '{self.config.container_name}'...")
        subprocess.run(
            ["docker", "rm", "-f", self.config.container_name],
            capture_output=True,
            text=True
        )

        if remove_workspace and os.path.exists(self.config.workspace_dir):
            try:
                shutil.rmtree(self.config.workspace_dir)
            except Exception as e:
                logger.warning(f"Could not clear workspace {self.config.workspace_dir}: {e}")

        return True

    def reset(self) -> bool:
        """Completely reset the sandbox to a clean state.
        
        Destroys the current container and starts a fresh one.
        """
        logger.info(f"Resetting sandbox container '{self.config.container_name}'...")
        self.destroy(remove_workspace=False)
        self.create()
        return self.start()

    def status(self) -> dict:
        """Retrieve the status and statistics of the sandbox container."""
        available = self.is_docker_available()
        if not available:
            return {
                "docker_available": False,
                "status": "docker_offline",
                "container_name": self.config.container_name
            }

        running = self.is_running()
        return {
            "docker_available": True,
            "container_name": self.config.container_name,
            "running": running,
            "image": self.config.image_name,
            "user": self.config.user,
            "network_mode": self.config.network_mode,
            "read_only": self.config.read_only_rootfs,
            "workspace": self.config.workspace_dir,
            "cpu_limit": self.config.cpu_limit,
            "memory_limit": self.config.memory_limit,
            "pids_limit": self.config.pids_limit,
        }

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        workdir: str = "/workspace",
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        """Execute a shell command inside the sandbox container.
        
        Runs as dedicated non-root user 'agent' (UID 1000) inside container.
        Enforces execution timeout.
        """
        timeout_val = timeout if timeout is not None else self.config.default_timeout

        if not self.is_running():
            self.start()

        cmd = [
            "docker", "exec",
            "-i",
            "--user", self.config.user,
            "-w", workdir,
        ]

        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])

        cmd.extend([
            self.config.container_name,
            "bash", "-c", command
        ])

        start_time = time.time()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_val
            )
            duration = time.time() - start_time
            return ExecutionResult(
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                duration=duration,
                timed_out=False
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            logger.warning(f"Command execution timed out after {timeout_val}s: {command}")
            # Best effort to kill running processes in the container
            try:
                subprocess.run(
                    ["docker", "exec", "--user", "1000:1000", self.config.container_name, "kill", "-9", "-1"],
                    capture_output=True,
                    timeout=3
                )
            except Exception:
                pass

            return ExecutionResult(
                stdout=e.stdout if isinstance(e.stdout, str) else "",
                stderr=f"Execution timed out after {timeout_val} seconds.",
                exit_code=124,
                duration=duration,
                timed_out=True
            )

    def execute_python(
        self,
        code: str,
        timeout: Optional[int] = None,
        workdir: str = "/workspace"
    ) -> ExecutionResult:
        """Safely execute Python code inside the container.
        
        Transfers code via stdin to python3 in container without creating 
        insecure temporary files on host.
        """
        timeout_val = timeout if timeout is not None else self.config.default_timeout

        if not self.is_running():
            self.start()

        cmd = [
            "docker", "exec",
            "-i",
            "--user", self.config.user,
            "-w", workdir,
            self.config.container_name,
            "python3", "-"
        ]

        start_time = time.time()
        try:
            res = subprocess.run(
                cmd,
                input=code,
                capture_output=True,
                text=True,
                timeout=timeout_val
            )
            duration = time.time() - start_time
            return ExecutionResult(
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.returncode,
                duration=duration,
                timed_out=False
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            logger.warning(f"Python execution timed out after {timeout_val}s")
            try:
                subprocess.run(
                    ["docker", "exec", "--user", "1000:1000", self.config.container_name, "kill", "-9", "-1"],
                    capture_output=True,
                    timeout=3
                )
            except Exception:
                pass

            return ExecutionResult(
                stdout="",
                stderr=f"Python execution timed out after {timeout_val} seconds.",
                exit_code=124,
                duration=duration,
                timed_out=True
            )
