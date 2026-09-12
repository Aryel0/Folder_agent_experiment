import os
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool


class ListDirectoryArgs(BaseModel):
    directory: str = Field(description="The path to the root directory to list (absolute or relative to CWD).")
    max_depth: int = Field(default=3, description="Maximum depth to recurse into subdirectories.")


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List the contents of a directory as an indented tree structure."
    args_schema = ListDirectoryArgs

    def run(self, **kwargs) -> str:
        directory = kwargs["directory"]
        max_depth = kwargs.get("max_depth", 3)

        if not os.path.isdir(directory):
            return f"Error: Directory '{directory}' not found."

        lines = [f"{directory}/"]
        _build_tree(directory, lines, prefix="", depth=0, max_depth=max_depth)
        return "\n".join(lines)


class GetFileInfoArgs(BaseModel):
    file_path: str = Field(description="The path to the target file (absolute or relative to CWD).")


class GetFileInfoTool(BaseTool):
    name = "get_file_info"
    description = "Return metadata about a single file: size, extension, and line count."
    args_schema = GetFileInfoArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]

        if not os.path.isfile(file_path):
            return f"Error: File '{file_path}' not found."

        size = os.path.getsize(file_path)
        ext = os.path.splitext(file_path)[1] or "(none)"
        try:
            with open(file_path, "r", errors="replace") as f:
                line_count = sum(1 for _ in f)
        except Exception:
            line_count = "unknown"

        return (
            f"File: {file_path}\n"
            f"  Size: {_human_size(size)}\n"
            f"  Extension: {ext}\n"
            f"  Lines: {line_count}"
        )


# -- Module-level helpers (not tools) ----------------------------------------

def _build_tree(directory: str, lines: list, prefix: str, depth: int, max_depth: int):
    """Recursively build a tree representation of a directory."""
    if depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        lines.append(f"{prefix}[permission denied]")
        return

    entries = [e for e in entries if not e.startswith(".") and e != "__pycache__"]

    dirs = [e for e in entries if os.path.isdir(os.path.join(directory, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(directory, e))]

    for f in files:
        fpath = os.path.join(directory, f)
        size = os.path.getsize(fpath)
        lines.append(f"{prefix}├── {f}  ({_human_size(size)})")

    for d in dirs:
        dpath = os.path.join(directory, d)
        lines.append(f"{prefix}├── {d}/")
        _build_tree(dpath, lines, prefix=prefix + "│   ", depth=depth + 1, max_depth=max_depth)


def _human_size(num_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
