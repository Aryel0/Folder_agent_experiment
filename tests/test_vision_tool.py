import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.tools.base import BaseTool
from core.tools.executor import ToolRegistry
from core.tools.registery.vision import AnalyzeImageTool, AnalyzeImageArgs
from core.agent import FolderAgent
from tests.test_utils import BaseAgentTest


class TestVisionTool(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.auto_discover("core/tools/registery")

    def test_tool_discovery(self):
        """Verify that analyze_image is auto-discovered by ToolRegistry."""
        self.assertIn("analyze_image", self.registry.tools)
        tool = self.registry.get("analyze_image")
        self.assertEqual(tool.name, "analyze_image")
        self.assertEqual(tool.__class__.__name__, "AnalyzeImageTool")
        self.assertIsInstance(tool, BaseTool)

    def test_tool_schema_to_ollama(self):
        """Verify the Ollama tool definition generated from Pydantic schema."""
        tool = self.registry.get("analyze_image")
        definition = tool.to_ollama_tool()
        self.assertEqual(definition["type"], "function")
        self.assertEqual(definition["function"]["name"], "analyze_image")
        params = definition["function"]["parameters"]
        self.assertIn("image_path", params["properties"])
        self.assertIn("question", params["properties"])
        self.assertIn("image_path", params["required"])

    def test_nonexistent_image(self):
        """Verify error handling when the image file does not exist."""
        tool = self.registry.get("analyze_image")
        res = tool.run(image_path="non_existent_file_12345.png")
        self.assertIn("not found", res)

    def test_unsupported_extension(self):
        """Verify error handling when a non-image file is provided."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an image")
            temp_path = f.name
        try:
            tool = self.registry.get("analyze_image")
            res = tool.run(image_path=temp_path)
            self.assertIn("Unsupported image format", res)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_security_policy_enforcement(self):
        """Verify that security restrictions prevent reading outside allowed directories."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png data")
            temp_path = f.name
        try:
            restricted_registry = ToolRegistry(allowed_directories=["/some/allowed/dir"])
            restricted_registry.auto_discover("core/tools/registery")
            tool = restricted_registry.get("analyze_image")
            res = tool.run(image_path=temp_path)
            self.assertIn("Security policy prevents accessing files", res)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("core.tools.registery.vision.ollama.chat")
    def test_successful_ollama_chat_call(self, mock_chat):
        """Verify that AnalyzeImageTool correctly calls ollama.chat with the image."""
        mock_chat.return_value = {
            "message": {
                "role": "assistant",
                "content": "This is a chart showing user growth."
            }
        }
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png content")
            temp_path = f.name

        try:
            tool = self.registry.get("analyze_image")
            result = tool.run(image_path=temp_path, question="What chart is this?")
            self.assertEqual(result, "This is a chart showing user growth.")

            mock_chat.assert_called_once()
            call_kwargs = mock_chat.call_args[1]
            self.assertEqual(call_kwargs["messages"][0]["content"], "What chart is this?")
            self.assertEqual(call_kwargs["messages"][0]["images"], [str(os.path.abspath(temp_path))])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("core.tools.registery.vision.ollama.chat")
    def test_model_not_found_handling(self, mock_chat):
        """Verify helpful error messages when the vision model is missing."""
        mock_chat.side_effect = Exception("model 'llama3.2-vision:latest' not found, try pulling it first")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake jpg content")
            temp_path = f.name

        try:
            tool = self.registry.get("analyze_image")
            result = tool.run(image_path=temp_path)
            self.assertIn("Ensure an Ollama vision model is pulled", result)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestVisionCapability(BaseAgentTest):
    def test_vision_capability_registration(self):
        """Verify that FolderAgent discovers and registers the vision capability."""
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root="capabilities"
        )
        self.assertIn("vision", agent.capabilities)
        vision_cap = agent.capabilities["vision"]
        self.assertEqual(vision_cap["manifest"]["Name"], "Vision")
        self.assertIn("analyze_image", vision_cap["context"]["tools"]["tools"])
        self.assertTrue(len(vision_cap["context"]["prompt"]) > 0)


if __name__ == "__main__":
    unittest.main()
