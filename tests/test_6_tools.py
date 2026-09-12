import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from core.tools.executor import ToolRegistry
from core.tools.base import BaseTool
import os

class MockFailTool(BaseTool):
    name = "mock_fail"
    description = "Fails always"
    
    def run(self, **kwargs) -> str:
        return "Permission denied"

class TestToolSystem(BaseAgentTest):
    def test_tool_discovery(self):
        # We check if ToolRegistry loads basic tools
        registry = ToolRegistry()
        registry.auto_discover("core/tools/registery")
        self.assertGreater(len(registry.tools), 0)

    def test_missing_tool(self):
        # Capability requests database.delete
        self.create_mock_capability(
            "bad_tool_cap",
            "name: bad_tool_cap",
            "prompt",
            '{"tools": ["database.delete"]}'
        )
        
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )
        
        # When agent executes, ToolRegistry will try to find "database.delete"
        # It shouldn't crash, but it should just not include it in the tools list sent to LLM.
        # Actually, let's see how get_ollama_tools behaves.
        ollama_tools = agent.registry.get_ollama_tools(["database.delete"])
        self.assertEqual(len(ollama_tools), 0)

    def test_tool_failure_propagation(self):
        # Tool returns Permission denied
        registry = ToolRegistry()
        registry.register(MockFailTool())
        
        results = registry.execute_tool_calls([
            {"function": {"name": "mock_fail", "arguments": {}}}
        ])
        
        self.assertEqual(results[0]["result"], "Permission denied")
