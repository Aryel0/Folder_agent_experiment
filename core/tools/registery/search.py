import os
import re
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool


class SearchInFileArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file to search in.")
    pattern: str = Field(description="The regular expression or literal string pattern to search for.")
    case_sensitive: bool = Field(default=True, description="Whether the search should be case-sensitive.")


class SearchInFileTool(BaseTool):
    name = "search_in_file"
    description = "Search for a regex or literal pattern in a single file. Do NOT use this just to read a file, use read_file instead."
    args_schema = SearchInFileArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        pattern = kwargs["pattern"]
        case_sensitive = kwargs.get("case_sensitive", True)

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
        except re.error:
            compiled = re.compile(re.escape(pattern), 0 if case_sensitive else re.IGNORECASE)

        try:
            with open(file_path, "r", errors="replace") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return f"Error: File '{file_path}' not found."
        except Exception as e:
            return f"Error reading file '{file_path}': {e}"

        matches = []
        for line_num, line in enumerate(lines, start=1):
            if compiled.search(line):
                matches.append(f"  L{line_num}: {line.rstrip()}")

        if not matches:
            return f"No matches for '{pattern}' in {file_path}."
        return f"{file_path} ({len(matches)} matches):\n" + "\n".join(matches)


class SearchInDirectoryArgs(BaseModel):
    directory: str = Field(description="The absolute path to the root directory to search.")
    pattern: str = Field(description="The regex or literal pattern to match.")
    extensions: Optional[List[str]] = Field(default=None, description="List of file extensions to filter by (e.g. ['.py', '.md']).")
    case_sensitive: bool = Field(default=True, description="Whether the search is case-sensitive.")


class SearchInDirectoryTool(BaseTool):
    name = "search_in_directory"
    description = "Recursively search for a pattern across all files in a directory. DO NOT use this tool to read known files or check if a file exists. Use this ONLY for recursive pattern matching across unknown structures."
    args_schema = SearchInDirectoryArgs

    def run(self, **kwargs) -> str:
        directory = kwargs["directory"]
        pattern = kwargs["pattern"]
        extensions = kwargs.get("extensions")
        case_sensitive = kwargs.get("case_sensitive", True)

        if not os.path.isdir(directory):
            return f"Error: Directory '{directory}' not found."

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
        except re.error:
            compiled = re.compile(re.escape(pattern), 0 if case_sensitive else re.IGNORECASE)

        results = []
        for root, _dirs, files in os.walk(directory):
            _dirs[:] = [d for d in _dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in sorted(files):
                if extensions and not any(fname.endswith(ext) for ext in extensions):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="replace") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                matches = []
                for line_num, line in enumerate(lines, start=1):
                    if compiled.search(line):
                        matches.append(f"  L{line_num}: {line.rstrip()}")
                if matches:
                    results.append(f"{fpath} ({len(matches)} matches):\n" + "\n".join(matches))

        if not results:
            return f"No matches for '{pattern}' in {directory}."
        return "\n\n".join(results)
