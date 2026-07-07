import subprocess
import shlex
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_COMMANDS = ["ls", "pwd", "echo", "cat", "whoami"]


class ExecuteCommandArgs(BaseModel):
    command: str = Field(description="The shell command string to execute (e.g. 'ls -la /tmp').")


class ExecuteCommandTool(BaseTool):
    name = "execute_command"
    description = "Execute a whitelisted shell command and return its output."
    args_schema = ExecuteCommandArgs

    def run(self, **kwargs) -> str:
        command = kwargs["command"]
        command_parts = shlex.split(command)
        if command_parts[0] not in ALLOWED_COMMANDS:
            return f"Error: Command '{command_parts[0]}' is not allowed."

        try:
            result = subprocess.run(
                command_parts, capture_output=True, text=True, check=True, timeout=300
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error executing command: {e.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 5 minutes."