import unittest
from unittest.mock import patch, MagicMock
from sandbox_world.config import SandboxConfig
from sandbox_world.manager import DockerSandbox, ExecutionResult


class TestStandaloneManager(unittest.TestCase):
    def setUp(self):
        self.config = SandboxConfig(workspace_dir="./tmp_mgr_ws")
        self.sandbox = DockerSandbox(self.config)

    @patch("subprocess.run")
    def test_docker_available_check(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.sandbox.is_docker_available())

        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(self.sandbox.is_docker_available())

    @patch.object(DockerSandbox, "is_running", return_value=True)
    @patch("subprocess.run")
    def test_execute_command(self, mock_run, mock_running):
        mock_run.return_value = MagicMock(returncode=0, stdout="agent\n", stderr="")
        res = self.sandbox.execute_command("whoami")
        self.assertTrue(res.success)
        self.assertEqual(res.stdout, "agent\n")

    @patch.object(DockerSandbox, "is_running", return_value=True)
    @patch("subprocess.run")
    def test_execute_python(self, mock_run, mock_running):
        mock_run.return_value = MagicMock(returncode=0, stdout="42\n", stderr="")
        res = self.sandbox.execute_python("print(42)")
        self.assertTrue(res.success)
        self.assertEqual(res.stdout, "42\n")


if __name__ == "__main__":
    unittest.main()
