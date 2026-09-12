import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.sandbox.config import SandboxConfig
from core.sandbox.security import (
    SecurityViolationError,
    validate_mount,
    validate_security_policy,
    build_docker_security_args,
)
from core.sandbox.manager import DockerSandbox, ExecutionResult
from core.tools.registery.bash import ExecuteCommandTool
from core.tools.registery.python_exec import ExecutePythonTool


class TestSandboxSecurity(unittest.TestCase):
    """Unit tests for the Sandbox security enforcement rules."""

    def setUp(self):
        self.temp_workspace = os.path.abspath("./tmp_test_workspace")
        os.makedirs(self.temp_workspace, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.temp_workspace):
            try:
                os.rmdir(self.temp_workspace)
            except OSError:
                pass

    def test_cannot_enable_privileged(self):
        """Privileged mode must be rejected immediately at config level."""
        with self.assertRaises(ValueError) as ctx:
            SandboxConfig(privileged=True)
        self.assertIn("Privileged containers are strictly forbidden", str(ctx.exception))

    def test_cannot_run_as_root(self):
        """Root user must be rejected immediately at config level."""
        for root_user in ["0", "root", "0:0"]:
            with self.assertRaises(ValueError) as ctx:
                SandboxConfig(user=root_user)
            self.assertIn("Running as root", str(ctx.exception))

    def test_cannot_use_host_network(self):
        """Host network must be rejected at config level."""
        with self.assertRaises(ValueError) as ctx:
            SandboxConfig(network_mode="host")
        self.assertIn("Host networking (--network host) is strictly forbidden", str(ctx.exception))

    def test_cannot_mount_docker_socket(self):
        """Mounting Docker socket must be blocked by validate_mount."""
        forbidden_sockets = [
            "/var/run/docker.sock",
            "/var/run/docker.sock.raw",
            "//./pipe/docker_engine",
            "//./pipe/dockerDesktopLinuxEngine"
        ]
        for sock in forbidden_sockets:
            with self.assertRaises(SecurityViolationError) as ctx:
                validate_mount(sock, "/workspace")
            self.assertIn("Mounting Docker socket", str(ctx.exception))

    def test_cannot_mount_host_root(self):
        """Mounting host root filesystem or top-level drives must be blocked."""
        forbidden_roots = ["/", "C:\\", "C:/", "C:\\Windows"]
        for forbidden in forbidden_roots:
            with self.assertRaises(SecurityViolationError):
                validate_mount(forbidden, "/workspace")

    def test_cannot_mount_to_non_workspace_container_path(self):
        """Mounting anywhere other than /workspace inside the container must be rejected."""
        with self.assertRaises(SecurityViolationError) as ctx:
            validate_mount(self.temp_workspace, "/root")
        self.assertIn("Allowed container mount targets", str(ctx.exception))

    def test_read_only_rootfs_enforced(self):
        """Read-only rootfs is mandatory in security policy."""
        cfg = SandboxConfig(workspace_dir=self.temp_workspace)
        cfg.read_only_rootfs = False
        with self.assertRaises(SecurityViolationError) as ctx:
            validate_security_policy(cfg)
        self.assertIn("Container root filesystem must be mounted read-only", str(ctx.exception))

    def test_capabilities_drop_enforced(self):
        """Dropping ALL capabilities is mandatory in security policy."""
        cfg = SandboxConfig(workspace_dir=self.temp_workspace)
        cfg.drop_capabilities = []
        with self.assertRaises(SecurityViolationError) as ctx:
            validate_security_policy(cfg)
        self.assertIn("capabilities must be dropped", str(ctx.exception))

    def test_build_docker_security_args(self):
        """Verify generated Docker CLI arguments include all mandatory security flags."""
        cfg = SandboxConfig(
            workspace_dir=self.temp_workspace,
            cpu_limit=1.5,
            memory_limit="256m",
            memory_swap="256m",
            pids_limit=32,
            network_mode="none"
        )
        args = build_docker_security_args(cfg)

        # Check required security flags
        self.assertIn("--read-only", args)
        self.assertIn("--user", args)
        self.assertEqual(args[args.index("--user") + 1], "1000:1000")
        self.assertIn("--network", args)
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertIn("--cpus", args)
        self.assertEqual(args[args.index("--cpus") + 1], "1.5")
        self.assertIn("--memory", args)
        self.assertEqual(args[args.index("--memory") + 1], "256m")
        self.assertIn("--memory-swap", args)
        self.assertEqual(args[args.index("--memory-swap") + 1], "256m")
        self.assertIn("--pids-limit", args)
        self.assertEqual(args[args.index("--pids-limit") + 1], "32")
        self.assertIn("--cap-drop", args)
        self.assertEqual(args[args.index("--cap-drop") + 1], "ALL")
        self.assertIn("--security-opt", args)
        self.assertIn("no-new-privileges:true", args)
        self.assertIn("--tmpfs", args)
        self.assertIn("/tmp:rw,noexec,nosuid,size=64m", args)
        self.assertIn("/home/agent:rw,nosuid,size=64m", args)


class TestDockerSandboxLifecycle(unittest.TestCase):
    """Unit tests for DockerSandbox lifecycle methods and execution handling."""

    def setUp(self):
        self.temp_workspace = os.path.abspath("./tmp_lifecycle_workspace")
        os.makedirs(self.temp_workspace, exist_ok=True)
        self.config = SandboxConfig(workspace_dir=self.temp_workspace)
        self.sandbox = DockerSandbox(self.config)

    def tearDown(self):
        if os.path.exists(self.temp_workspace):
            try:
                os.rmdir(self.temp_workspace)
            except OSError:
                pass

    @patch("subprocess.run")
    def test_is_docker_available_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.sandbox.is_docker_available())

    @patch("subprocess.run")
    def test_is_docker_available_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(self.sandbox.is_docker_available())

    @patch("subprocess.run")
    def test_is_running(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n")
        self.assertTrue(self.sandbox.is_running())

        mock_run.return_value = MagicMock(returncode=0, stdout="false\n")
        self.assertFalse(self.sandbox.is_running())

    @patch("subprocess.run")
    def test_create_container(self, mock_run):
        # mock destroy rm, then create
        mock_run.return_value = MagicMock(returncode=0, stdout="container_id_123\n")
        res = self.sandbox.create()
        self.assertTrue(res)
        
        # Verify docker create was invoked
        called_cmds = [call.args[0] for call in mock_run.call_args_list]
        create_calls = [cmd for cmd in called_cmds if "create" in cmd]
        self.assertTrue(len(create_calls) > 0)
        cmd = create_calls[0]
        self.assertIn("--read-only", cmd)
        self.assertIn("--cap-drop", cmd)

    @patch("subprocess.run")
    def test_start_container(self, mock_run):
        # Container already running check returns false, then inspect returns 0, start returns 0
        def side_effect(cmd, *args, **kwargs):
            if "inspect" in cmd and "{{.State.Running}}" in cmd:
                return MagicMock(returncode=0, stdout="false\n")
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="{}")
            if "start" in cmd:
                return MagicMock(returncode=0, stdout="folderagent_sandbox\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        self.assertTrue(self.sandbox.start())

    @patch("subprocess.run")
    def test_stop_container(self, mock_run):
        # is_running returns true, docker stop returns 0
        def side_effect(cmd, *args, **kwargs):
            if "{{.State.Running}}" in cmd:
                return MagicMock(returncode=0, stdout="true\n")
            if "stop" in cmd:
                return MagicMock(returncode=0, stdout="folderagent_sandbox\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        self.assertTrue(self.sandbox.stop(timeout=2))

    @patch("subprocess.run")
    def test_destroy_container(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.sandbox.destroy(remove_workspace=False))

    @patch.object(DockerSandbox, "is_running", return_value=True)
    @patch("subprocess.run")
    def test_execute_command(self, mock_run, mock_is_running):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="agent\n",
            stderr=""
        )
        res = self.sandbox.execute_command("whoami")
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.stdout, "agent\n")
        self.assertEqual(res.output(), "agent\n")

    @patch.object(DockerSandbox, "is_running", return_value=True)
    @patch("subprocess.run")
    def test_execute_python(self, mock_run, mock_is_running):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="42\n",
            stderr=""
        )
        res = self.sandbox.execute_python("print(42)")
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.stdout, "42\n")

    @patch.object(DockerSandbox, "is_running", return_value=True)
    @patch("subprocess.run")
    def test_execution_timeout(self, mock_run, mock_is_running):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker exec", timeout=5)
        res = self.sandbox.execute_command("while true; do sleep 1; done", timeout=5)
        self.assertTrue(res.timed_out)
        self.assertEqual(res.exit_code, 124)
        self.assertIn("timed out after 5 seconds", res.output())


class TestToolsWithSandbox(unittest.TestCase):
    """Test ExecuteCommandTool and ExecutePythonTool delegation to Sandbox."""

    def test_execute_command_tool_sandbox_delegation(self):
        mock_sandbox = MagicMock()
        mock_sandbox.is_docker_available.return_value = True
        mock_sandbox.execute_command.return_value = ExecutionResult(
            stdout="hello from container",
            stderr="",
            exit_code=0,
            duration=0.1
        )

        tool = ExecuteCommandTool()
        tool.sandbox = mock_sandbox

        out = tool.run(command="echo 'hello from container'")
        self.assertEqual(out, "hello from container")
        mock_sandbox.execute_command.assert_called_once_with(command="echo 'hello from container'")

    def test_execute_python_tool_sandbox_delegation(self):
        mock_sandbox = MagicMock()
        mock_sandbox.is_docker_available.return_value = True
        mock_sandbox.execute_python.return_value = ExecutionResult(
            stdout="result: 100",
            stderr="",
            exit_code=0,
            duration=0.2
        )

        tool = ExecutePythonTool()
        tool.sandbox = mock_sandbox
        tool.authorize_execution = lambda prompt: True

        out = tool.run(code="print('result: 100')")
        self.assertEqual(out, "result: 100")
        mock_sandbox.execute_python.assert_called_once_with(code="print('result: 100')", timeout=60)


if __name__ == "__main__":
    unittest.main()
