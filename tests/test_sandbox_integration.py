import os
import sys
import unittest
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sandbox_world import ExecutionResult
from core.tools.registery.bash import ExecuteCommandTool
from core.tools.registery.python_exec import ExecutePythonTool


class TestSandboxIntegration(unittest.TestCase):
    """Integration test verifying agent tools properly delegate to standalone sandbox_world."""

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
