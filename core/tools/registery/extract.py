import os
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool


class ExtractFilesArgs(BaseModel):
    file_paths: List[str] = Field(description="A list of absolute file paths to read and concatenate.")


class ExtractFilesTool(BaseTool):
    name = "extract_files"
    description = "Read and concatenate the contents of multiple files, labeled by path. Useful for batch reading."
    args_schema = ExtractFilesArgs

    def run(self, **kwargs) -> str:
        file_paths = kwargs["file_paths"]
        sections = []
        for fpath in file_paths:
            if not os.path.isfile(fpath):
                sections.append(f"=== {fpath} ===\n[Error: file not found]")
                continue
            try:
                with open(fpath, "r", errors="replace") as f:
                    content = f.read()
                sections.append(f"=== {fpath} ===\n{content}")
            except Exception as e:
                sections.append(f"=== {fpath} ===\n[Error: {e}]")

        return "\n\n".join(sections)


class ExtractSectionsArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file.")
    start_line: int = Field(description="First line to extract (1-indexed, inclusive).")
    end_line: int = Field(description="Last line to extract (1-indexed, inclusive).")


class ExtractSectionsTool(BaseTool):
    name = "extract_sections"
    description = "Extract a specific range of lines from a file by line number."
    args_schema = ExtractSectionsArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        start_line = kwargs["start_line"]
        end_line = kwargs["end_line"]

        if not os.path.isfile(file_path):
            return f"Error: File '{file_path}' not found."

        try:
            with open(file_path, "r", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading '{file_path}': {e}"

        total = len(lines)
        start_line = max(1, start_line)
        end_line = min(total, end_line)

        if start_line > total:
            return f"Error: start_line {start_line} exceeds file length ({total} lines)."

        extracted = lines[start_line - 1 : end_line]
        numbered = [f"L{start_line + i}: {line.rstrip()}" for i, line in enumerate(extracted)]
        return f"{file_path} [L{start_line}-L{end_line}]:\n" + "\n".join(numbered)


class ExtractByPatternArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file.")
    start_pattern: str = Field(description="Substring to match the starting line of the block to extract.")
    end_pattern: Optional[str] = Field(default=None, description="Substring to match the ending line. If omitted, extracts to end of file.")


class ExtractByPatternTool(BaseTool):
    name = "extract_by_pattern"
    description = "Extract content from a file starting at a line matching a pattern. Useful for extracting functions, classes, or config blocks."
    args_schema = ExtractByPatternArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        start_pattern = kwargs["start_pattern"]
        end_pattern = kwargs.get("end_pattern")

        if not os.path.isfile(file_path):
            return f"Error: File '{file_path}' not found."

        try:
            with open(file_path, "r", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading '{file_path}': {e}"

        capturing = False
        result = []

        for i, line in enumerate(lines, start=1):
            if not capturing and start_pattern in line:
                capturing = True
            if capturing:
                result.append(f"L{i}: {line.rstrip()}")
                if end_pattern and end_pattern in line and len(result) > 1:
                    break

        if not result:
            return f"No match for '{start_pattern}' in {file_path}."

        return f"{file_path}:\n" + "\n".join(result)
