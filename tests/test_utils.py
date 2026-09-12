import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

class BaseAgentTest(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for safe testing
        self.test_dir = tempfile.mkdtemp()
        self.memory_root = os.path.join(self.test_dir, "memory")
        self.capabilities_root = os.path.join(self.test_dir, "capabilities")
        os.makedirs(self.memory_root)
        os.makedirs(self.capabilities_root)

        # We will mock ollama.generate and ollama.chat to avoid slow LLM calls during structural tests
        self.ollama_generate_patcher = patch('ollama.generate')
        self.mock_ollama_generate = self.ollama_generate_patcher.start()
        
        self.ollama_chat_patcher = patch('ollama.chat')
        self.mock_ollama_chat = self.ollama_chat_patcher.start()

    def tearDown(self):
        self.ollama_generate_patcher.stop()
        self.ollama_chat_patcher.stop()
        shutil.rmtree(self.test_dir)

    def create_mock_capability(self, name, manifest_content, prompt_content="Mock prompt", tools_content='{"tools":[]}'):
        cap_dir = os.path.join(self.capabilities_root, name)
        os.makedirs(cap_dir, exist_ok=True)
        
        with open(os.path.join(cap_dir, "manifest.yaml"), "w") as f:
            f.write(manifest_content)
            
        config_content = "{}"
        if name == "planner" or "json" in name:
            config_content = "output_type: json\n"
            
        with open(os.path.join(cap_dir, "config.yaml"), "w") as f:
            f.write(config_content)
            
        with open(os.path.join(cap_dir, "prompt.md"), "w") as f:
            f.write(prompt_content)
        with open(os.path.join(cap_dir, "tools.json"), "w") as f:
            f.write(tools_content)
        return cap_dir
