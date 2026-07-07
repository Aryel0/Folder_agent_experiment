from __future__ import annotations
from abc import ABC, abstractmethod
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ValidationError
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseTool(ABC):
    """Abstract base class that every tool must inherit from.

    Subclasses must define:
        name (str): Unique identifier the LLM uses to call this tool.
        description (str): Human-readable explanation sent to the LLM.
        args_schema (type[BaseModel]): A Pydantic model defining the tool's arguments.

    Subclasses must implement:
        run(**kwargs) -> str: The actual tool execution logic.
    """

    name: str = ""
    description: str = ""
    args_schema: type[BaseModel] = None

    @abstractmethod
    def run(self, **kwargs) -> str:
        """Execute the tool with validated arguments."""
        ...

    def validate(self, kwargs: dict) -> dict:
        """Validate incoming arguments against the Pydantic args_schema.

        Returns a cleaned dict of arguments ready for ``run()``.
        Raises ``ValueError`` with a clear message that can be sent
        back to the LLM so it can self-correct.
        """
        if self.args_schema is None:
            return kwargs

        try:
            model = self.args_schema(**kwargs)
            return model.model_dump()
        except ValidationError as e:
            raise ValueError(str(e))

    def to_ollama_tool(self) -> dict:
        """Generate an Ollama-compatible tool definition from the Pydantic schema."""
        if self.args_schema is None:
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }

        schema = self.args_schema.model_json_schema()
        properties = {}
        required = schema.get("required", [])

        for field_name, field_info in schema.get("properties", {}).items():
            prop = {
                "type": field_info.get("type", "string"),
                "description": field_info.get("description", field_name.replace("_", " ")),
            }
            # Handle Pydantic's anyOf for Optional fields
            if "anyOf" in field_info:
                for option in field_info["anyOf"]:
                    if option.get("type") != "null":
                        prop["type"] = option.get("type", "string")
                        break
            properties[field_name] = prop

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
