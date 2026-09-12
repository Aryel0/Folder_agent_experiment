import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
import os

class TestCapabilityRegistry(BaseAgentTest):
    def test_capability_discovery(self):
        self.create_mock_capability(
            name="test_capability", 
            manifest_content="name: test_capability\ndescription: A test capability"
        )
        
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )
        self.assertIn("test_capability", agent.capabilities)

    def test_invalid_manifest(self):
        # Invalid yaml manifest (e.g. malformed)
        self.create_mock_capability(
            name="invalid_cap", 
            manifest_content="name: [invalid yaml"
        )
        
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )
        
        # Capability should be rejected (not in registry) but no crash
        self.assertNotIn("invalid_cap", agent.capabilities)

    def test_duplicate_capability_name(self):
        # Two folders, but same manifest name (if the system groups by manifest name)
        # Note: FolderAgent currently uses the folder name as the capability name: cap_name = path.name.lower()
        # So "coder" and "coder_backup" will be registered as separate capabilities.
        # Let's verify that behavior.
        self.create_mock_capability(name="coder", manifest_content="name: coder")
        self.create_mock_capability(name="coder_backup", manifest_content="name: coder")
        
        agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )
        
        self.assertIn("coder", agent.capabilities)
        self.assertIn("coder_backup", agent.capabilities)
