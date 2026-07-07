import os
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from core.tools.base import BaseTool


class ReadFileArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file to read.")


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the entire content of a file and return it as a string."
    args_schema = ReadFileArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        try:
            with open(file_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: File '{file_path}' not found."
        except Exception as e:
            return f"Error reading file '{file_path}': {str(e)}"


class WriteFileArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file to write to.")
    content: str = Field(description="The string content to write into the file.")


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file, overwriting any existing content."
    args_schema = WriteFileArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        content = kwargs["content"]
        try:
            with open(file_path, "w") as file:
                file.write(content)
            return f"Successfully wrote to '{file_path}'."
        except Exception as e:
            return f"Error writing to file '{file_path}': {str(e)}"


class AppendToFileArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file to append to.")
    content: str = Field(description="The string content to append to the file.")


class AppendToFileTool(BaseTool):
    name = "append_to_file"
    description = "Append content to the end of an existing file."
    args_schema = AppendToFileArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        content = kwargs["content"]
        try:
            with open(file_path, "a") as file:
                file.write(content)
            return f"Successfully appended to '{file_path}'."
        except Exception as e:
            return f"Error appending to file '{file_path}': {str(e)}"


class DeleteFileArgs(BaseModel):
    file_path: str = Field(description="The absolute path to the file to delete.")


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file from the filesystem."
    args_schema = DeleteFileArgs

    def run(self, **kwargs) -> str:
        file_path = kwargs["file_path"]
        try:
            os.remove(file_path)
            return f"Successfully deleted '{file_path}'."
        except FileNotFoundError:
            return f"Error: File '{file_path}' not found."
        except Exception as e:
            return f"Error deleting file '{file_path}': {str(e)}"