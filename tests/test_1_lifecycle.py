import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
import os

class TestCoreLifecycle(BaseAgentTest):
    def test_startup_clean(self):
        # Goal: Agent can initialize cleanly.
        # Add a dummy capability to discover
        self.create_mock_capability(
            name="dummy_cap", 
            manifest_content="name: dummy_cap\ndescription: Test capability",
            prompt_content="Test prompt"
        )
        
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )
        
        # Verify Model loads
        self.assertEqual(agent.model, "mock-model")
        
        # Verify Tools discovered (ToolRegistry auto_discovers core tools)
        self.assertGreater(len(agent.registry.tools), 0, "Tools should be discovered")
        
        # Verify Capabilities discovered
        self.assertIn("dummy_cap", agent.capabilities)
        self.assertEqual(agent.capabilities["dummy_cap"]["manifest"]["name"], "dummy_cap")
        
        # Verify Memory initialized
        self.assertIsNotNone(agent.memory)

    def test_missing_component(self):
        # Goal: Test missing manifest logs warning but continues running
        # Create a capability WITHOUT a manifest
        cap_dir = os.path.join(self.capabilities_root, "broken_cap")
        os.makedirs(cap_dir, exist_ok=True)
        with open(os.path.join(cap_dir, "prompt.md"), "w") as f:
            f.write("Broken prompt")
            
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )
        
        # Agent should start successfully but NOT load the broken capability
        self.assertNotIn("broken_cap", agent.capabilities)
