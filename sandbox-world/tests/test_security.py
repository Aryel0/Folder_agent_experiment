import os
import unittest
from pathlib import Path
from sandbox_world.config import SandboxConfig
from sandbox_world.security import (
    SecurityViolationError,
    validate_mount,
    validate_security_policy,
    build_docker_security_args
)


class TestStandaloneSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_ws = Path("./tmp_stand_security").resolve()
        self.temp_ws.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.temp_ws.exists():
            try:
                self.temp_ws.rmdir()
            except OSError:
                pass

    def test_cannot_enable_privileged(self):
        with self.assertRaises(ValueError):
            SandboxConfig(privileged=True)

    def test_cannot_run_as_root(self):
        for user in ["0", "root", "0:0"]:
            with self.assertRaises(ValueError):
                SandboxConfig(user=user)

    def test_cannot_use_host_network(self):
        with self.assertRaises(ValueError):
            SandboxConfig(network_mode="host")

    def test_cannot_mount_docker_socket(self):
        forbidden = [
            "/var/run/docker.sock",
            "//./pipe/docker_engine",
            "//./pipe/dockerDesktopLinuxEngine"
        ]
        for sock in forbidden:
            with self.assertRaises(SecurityViolationError):
                validate_mount(sock, "/workspace")

    def test_cannot_mount_host_root(self):
        for root in ["/", "C:\\", "C:/", "C:\\Windows"]:
            with self.assertRaises(SecurityViolationError):
                validate_mount(root, "/workspace")

    def test_build_docker_security_args(self):
        cfg = SandboxConfig(workspace_dir=str(self.temp_ws))
        args = build_docker_security_args(cfg)
        self.assertIn("--read-only", args)
        self.assertIn("--cap-drop", args)
        self.assertIn("--security-opt", args)
        self.assertIn("no-new-privileges:true", args)


if __name__ == "__main__":
    unittest.main()
