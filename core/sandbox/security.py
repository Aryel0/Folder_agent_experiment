from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import List
from core.sandbox.config import SandboxConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class SandboxError(Exception):
    """Base exception for sandbox operations."""
    pass


class SecurityViolationError(SandboxError):
    """Raised when an action or configuration violates sandbox security boundaries."""
    pass


# Disallowed mount paths and patterns on host
FORBIDDEN_HOST_TARGETS = [
    "/",
    "/root",
    "/etc",
    "/var",
    "/var/run",
    "/var/run/docker.sock",
    "docker.sock",
    "//./pipe/docker_engine",
    "//./pipe/dockerDesktopLinuxEngine",
    "C:\\",
    "C:/",
    "C:\\Windows",
    "C:/Windows",
    "C:\\Program Files",
    "C:/Program Files",
    "C:\\Users",
    "C:/Users",
]


def normalize_path(p: str) -> str:
    """Normalize a path to resolve relative segments and symlinks."""
    return str(Path(p).resolve())


def validate_mount(host_path: str, container_path: str) -> None:
    """Validate that a proposed mount point does not violate sandbox isolation rules.
    
    Raises:
        SecurityViolationError: If the mount targets host root, system paths, or docker socket.
    """
    resolved_host = normalize_path(host_path)

    # 1. Reject any reference to docker socket or named pipes
    lower_host = host_path.lower()
    if "docker.sock" in lower_host or "pipe/docker" in lower_host:
        raise SecurityViolationError(
            f"SecurityViolation: Mounting Docker socket ('{host_path}') is strictly forbidden! "
            "Preventing container escape and host takeover."
        )

    # 2. Reject host root or top-level drives
    for forbidden in FORBIDDEN_HOST_TARGETS:
        forbidden_norm = normalize_path(forbidden) if os.path.exists(forbidden) else forbidden.lower()
        if resolved_host.lower() == forbidden_norm.lower():
            raise SecurityViolationError(
                f"SecurityViolation: Mounting host root/system directory ('{host_path}') into container is strictly forbidden!"
            )

    # Check if host_path is the drive root e.g. "C:\" or "/"
    path_obj = Path(resolved_host)
    if path_obj.parent == path_obj:  # root directory
        raise SecurityViolationError(
            f"SecurityViolation: Cannot mount drive root ('{host_path}')."
        )

    # 3. Only allow mounting to /workspace inside container
    valid_container_destinations = ["/workspace"]
    if container_path not in valid_container_destinations:
        raise SecurityViolationError(
            f"SecurityViolation: Mounting to '{container_path}' is disallowed. "
            f"Allowed container mount targets: {valid_container_destinations}"
        )


def validate_security_policy(config: SandboxConfig) -> None:
    """Verify that all mandatory security constraints are met by the configuration.
    
    Raises:
        SecurityViolationError: If any mandatory security constraint is missing or invalid.
    """
    # 1. Non-root user check
    if not config.user or config.user in ("0", "root", "0:0"):
        raise SecurityViolationError(
            "SecurityViolation: Sandbox must run as a non-root user (e.g., '1000:1000')."
        )

    # 2. Privileged container check
    if config.privileged:
        raise SecurityViolationError(
            "SecurityViolation: Privileged containers (--privileged) are strictly prohibited."
        )

    # 3. Host network check
    if config.network_mode.lower() == "host":
        raise SecurityViolationError(
            "SecurityViolation: Host networking (--network host) is strictly prohibited."
        )

    # 4. Read-only filesystem check
    if not config.read_only_rootfs:
        raise SecurityViolationError(
            "SecurityViolation: Container root filesystem must be mounted read-only."
        )

    # 5. Linux capabilities check
    if "ALL" not in config.drop_capabilities:
        raise SecurityViolationError(
            "SecurityViolation: All Linux capabilities must be dropped (--cap-drop=ALL)."
        )

    # 6. No-new-privileges check
    if not config.no_new_privileges:
        raise SecurityViolationError(
            "SecurityViolation: 'no-new-privileges' must be enabled to block setuid elevation."
        )

    # 7. Workspace mount check
    validate_mount(config.workspace_dir, "/workspace")


def build_docker_security_args(config: SandboxConfig) -> List[str]:
    """Generate the complete, hardened command-line arguments for Docker container creation.
    
    Enforces:
    - Dedicated non-root user (--user 1000:1000)
    - Read-only root filesystem (--read-only)
    - Dedicated tmpfs for /tmp and /home/agent
    - Dedicated, validated workspace volume
    - Resource limits (CPU, RAM, swap, PIDs)
    - Dropped capabilities (--cap-drop=ALL)
    - Privilege escalation prevention (--security-opt no-new-privileges:true)
    - Seccomp profile (--security-opt seccomp=...)
    - Network isolation (--network none or bridge)
    """
    validate_security_policy(config)

    # Ensure host workspace exists
    os.makedirs(config.workspace_dir, exist_ok=True)
    abs_workspace = normalize_path(config.workspace_dir)

    args = [
        # Non-root user
        "--user", config.user,
        
        # Read-only root filesystem
        "--read-only",

        # Network isolation
        "--network", config.network_mode,

        # Resource limits
        "--cpus", str(config.cpu_limit),
        "--memory", config.memory_limit,
        "--memory-swap", config.memory_swap,
        "--pids-limit", str(config.pids_limit),

        # Drop all capabilities
        "--cap-drop", "ALL",

        # Prevent privilege escalation
        "--security-opt", "no-new-privileges:true",

        # Writable tmpfs for /tmp (noexec, nosuid)
        "--tmpfs", f"/tmp:rw,noexec,nosuid,size={config.tmpfs_tmp_size}",

        # Writable tmpfs for /home/agent (nosuid)
        "--tmpfs", f"/home/agent:rw,nosuid,size={config.tmpfs_home_size}",

        # Mount validated workspace
        "-v", f"{abs_workspace}:/workspace:rw",

        # Workdir inside container
        "-w", "/workspace",
    ]

    # Add Seccomp profile if available
    if config.seccomp_profile_path and os.path.exists(config.seccomp_profile_path):
        seccomp_abs = normalize_path(config.seccomp_profile_path)
        args.extend(["--security-opt", f"seccomp={seccomp_abs}"])

    return args
