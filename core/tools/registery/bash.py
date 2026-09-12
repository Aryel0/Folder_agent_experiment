import subprocess
import shlex
import os
import getpass
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
    description = "Execute a shell command in a secured environment (e.g. ls, pwd, echo, cat, whoami, or arbitrary commands inside Docker sandbox)."
    args_schema = ExecuteCommandArgs
    sandbox = None  # Optional DockerSandbox instance

    def run(self, **kwargs) -> str:
        command = kwargs["command"]

        # If DockerSandbox is configured/enabled
        use_docker = os.environ.get("USE_DOCKER_SANDBOX", "0").lower() in ("1", "true")
        if self.sandbox or use_docker:
            try:
                from core.sandbox import DockerSandbox
                sb = self.sandbox or DockerSandbox()
                if sb.is_docker_available():
                    result = sb.execute_command(command=command)
                    return result.output()
            except Exception:
                pass

        try:
            command_parts = shlex.split(command, posix=False)
            command_parts = [
                p[1:-1] if (p.startswith("'") and p.endswith("'")) or (p.startswith('"') and p.endswith('"')) else p
                for p in command_parts
            ]
        except ValueError as e:
            return f"Error parsing command: {e}"

        if not command_parts:
            return "Error: Empty command."

        cmd = command_parts[0]
        args = command_parts[1:]

        if cmd not in ALLOWED_COMMANDS:
            return f"Error: Command '{cmd}' is not allowed."

        try:
            if cmd == "pwd":
                return os.getcwd()

            elif cmd == "whoami":
                return getpass.getuser()

            elif cmd == "echo":
                return " ".join(args)

            elif cmd == "cat":
                if not args:
                    return "Error: cat requires a file argument."
                output = []
                for arg in args:
                    if os.path.exists(arg):
                        with open(arg, 'r', encoding='utf-8', errors='replace') as f:
                            output.append(f.read())
                    else:
                        output.append(f"cat: {arg}: No such file or directory")
                return "\n".join(output)

            elif cmd == "ls":
                paths = [a for a in args if not a.startswith('-')]
                flags = [a for a in args if a.startswith('-')]

                target_dir = paths[0] if paths else "."
                if not os.path.exists(target_dir):
                    return f"ls: cannot access '{target_dir}': No such file or directory"

                if os.path.isfile(target_dir):
                    return target_dir

                entries = os.listdir(target_dir)

                show_hidden = any('a' in flag for flag in flags)
                if not show_hidden:
                    entries = [e for e in entries if not e.startswith('.')]

                return "\n".join(sorted(entries))

        except Exception as e:
            return f"Error executing command: {str(e)}"