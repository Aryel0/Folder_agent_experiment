import sys
import io
import traceback
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool


class ExecutePythonArgs(BaseModel):
    code: str = Field(description="The Python source code to execute.")
    timeout: int = Field(default=10, description="Maximum execution time in seconds.")


class ExecutePythonTool(BaseTool):
    name = "execute_python"
    description = "Execute a Python code snippet in a sandboxed environment and return its stdout output or error traceback."
    args_schema = ExecutePythonArgs

    def run(self, **kwargs) -> str:
        code = kwargs["code"]
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_out = io.StringIO()
        captured_err = io.StringIO()

        try:
            sys.stdout = captured_out
            sys.stderr = captured_err

            exec_globals = {"__builtins__": __builtins__}
            exec(code, exec_globals)

            stdout_val = captured_out.getvalue()
            stderr_val = captured_err.getvalue()

            result = ""
            if stdout_val:
                result += stdout_val
            if stderr_val:
                result += f"\n[stderr]:\n{stderr_val}"
            if not result.strip():
                result = "(executed successfully, no output)"
            return result

        except Exception:
            return f"Execution error:\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


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
