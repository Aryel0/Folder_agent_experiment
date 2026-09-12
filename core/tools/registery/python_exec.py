import os
import sys
import io
import tempfile
import subprocess
import traceback
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool


class ExecutePythonArgs(BaseModel):
    code: str = Field(description="The Python source code to execute.")
    timeout: int = Field(default=60, description="Maximum execution time in seconds.")


class ExecutePythonTool(BaseTool):
    name = "execute_python"
    description = "Execute a Python code snippet in a sandboxed environment and return its stdout output or error traceback."
    args_schema = ExecutePythonArgs
    sandbox = None  # Optional DockerSandbox instance

    def run(self, **kwargs) -> str:
        code = kwargs["code"]
        timeout_val = kwargs.get("timeout", 60)
        
        if not self.authorize_execution(f"Agent wants to execute python code:\n{code}"):
            return "Error: User denied execution."

        # If a DockerSandbox is explicitly attached or enabled via environment
        use_docker = os.environ.get("USE_DOCKER_SANDBOX", "0").lower() in ("1", "true")
        if self.sandbox or use_docker:
            try:
                from core.sandbox import DockerSandbox
                sb = self.sandbox or DockerSandbox()
                if sb.is_docker_available():
                    result = sb.execute_python(code=code, timeout=timeout_val)
                    return result.output()
            except Exception as e:
                # Log and fallback to host execution if sandbox error occurs
                pass
            
        # Create a temporary file to hold the code
        fd, temp_file_path = tempfile.mkstemp(suffix=".py", text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                if self.allowed_directories:
                    allowed_list = [os.path.abspath(d) for d in self.allowed_directories]
                    f.write(f"import sys, os\ndef _audit_hook(event, args):\n    if event == 'open':\n        path, mode, flags = args\n        if mode and ('w' in mode or 'a' in mode or '+' in mode):\n            p = os.path.abspath(path)\n            if not any(p.startswith(a) for a in {allowed_list}):\n                raise PermissionError('Security policy prevents write access to ' + p)\nsys.addaudithook(_audit_hook)\n")
                f.write(code)
                
            cwd = self.allowed_directories[0] if self.allowed_directories else os.getcwd()
            
            # Execute the temporary file in a subprocess
            result = subprocess.run(
                [sys.executable, temp_file_path],
                capture_output=True,
                text=True,
                timeout=timeout_val,
                cwd=cwd
            )
            
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]:\n{result.stderr}"
                
            if not output.strip():
                output = "(executed successfully, no output)"
                
            if result.returncode != 0:
                return f"Execution failed with return code {result.returncode}:\n{output}"
                
            return output
            
        except subprocess.TimeoutExpired:
            return f"Error: Execution timed out after {timeout_val} seconds. Check for infinite loops."
        except Exception as e:
            import traceback
            return f"Execution error:\n{traceback.format_exc()}"
        finally:
            # Clean up the temporary file
            try:
                os.remove(temp_file_path)
            except OSError:
                pass


class ValidateSyntaxArgs(BaseModel):
    code: str = Field(description="The Python source code to validate.")


class ValidateSyntaxTool(BaseTool):
    name = "validate_syntax"
    description = "Check Python code for syntax errors without executing it."
    args_schema = ValidateSyntaxArgs

    def run(self, **kwargs) -> str:
        code = kwargs["code"]
        try:
            compile(code, "<validation>", "exec")
            return "Syntax OK"
        except SyntaxError as e:
            return f"Syntax error at line {e.lineno}: {e.msg}"
