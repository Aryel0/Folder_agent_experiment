import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
# pyrefly: ignore [missing-import]
import ollama

from core.tools.base import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}


class AnalyzeImageArgs(BaseModel):
    image_path: str = Field(
        description="The path to the image file to analyze (absolute or relative to current working directory)."
    )
    question: str = Field(
        default="Describe what is in this image in detail, including any visible text, diagrams, structures, or notable objects.",
        description="The specific question, instruction, or focus for the visual analysis.",
    )


class AnalyzeImageTool(BaseTool):
    name = "analyze_image"
    description = (
        "Inspect and analyze an image file (e.g., diagrams, charts, screenshots, photos, documents) "
        "using a vision model, returning a textual description or answer."
    )
    args_schema = AnalyzeImageArgs

    def run(self, **kwargs) -> str:
        raw_path = kwargs["image_path"]
        question = kwargs.get("question") or "Describe what is in this image in detail."

        # Security policy check
        if not self.is_path_allowed(raw_path):
            return "Error: Security policy prevents accessing files outside of allowed directories."

        path = Path(raw_path).resolve()
        if not path.is_file():
            return f"Error: Image file '{raw_path}' not found."

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return (
                f"Error: Unsupported image format '{path.suffix}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        vision_model = os.environ.get("OLLAMA_VISION_MODEL", "llama3.2-vision:latest")

        try:
            logger.info(f"Analyzing image '{path}' with vision model '{vision_model}'")
            response = ollama.chat(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": question,
                        "images": [str(path)],
                    }
                ],
            )
            msg = response["message"] if isinstance(response, dict) else response.message
            content = msg.get("content", "") if isinstance(msg, dict) else msg.content
            return content.strip() if content else "Vision model returned an empty response."
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Error during image analysis: {err_msg}")
            if "not found" in err_msg.lower() or "model" in err_msg.lower():
                return (
                    f"Error running vision model '{vision_model}': {err_msg}. "
                    f"Ensure an Ollama vision model is pulled (e.g. `ollama run llama3.2-vision` or set OLLAMA_VISION_MODEL)."
                )
            return f"Error analyzing image '{raw_path}': {err_msg}"
