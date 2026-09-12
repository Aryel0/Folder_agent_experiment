import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from unittest.mock import MagicMock

class TestContracts(BaseAgentTest):
    def setUp(self):
        super().setUp()
        
        # Capability that expects JSON output
        self.create_mock_capability("planner", "name: planner")
        self.create_mock_capability("chat", "name: chat")
        self.create_mock_capability(
            "json_cap",
            "name: json_cap\noutput_type: json"
        )
        
        self.agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )

    def test_input_validation(self):
        # Give bad input
        # Agent might not explicitly validate user_input if it's just a string,
        # but if we had strict types, we would test it here.
        # Let's test that providing empty string doesn't crash but is handled gracefully.
        
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": '{"tasks": [{"skill": "chat", "task": "empty", "depends_on": []}]}'}],
            [{"response": "Handled empty input"}]
        ]
        
        results = self.agent.execute(" ")
        self.assertEqual(len(results), 1)

    def test_output_validation(self):
        # Capability returns wrong format (expects JSON, gets plain text)
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": '{"tasks": [{"skill": "json_cap", "task": "do json", "depends_on": []}]}'}],
            [{"response": "hello I am not json"}]
        ]
        
        # The agent should catch the JSON decode error (or attempt to extract)
        # In FolderAgent post_process: json.loads(self._extract_json(output))
        # If it fails, it will raise json.decoder.JSONDecodeError
        # Let's see if it catches it.
        with self.assertRaises(json.decoder.JSONDecodeError):
            self.agent.execute("Do json thing")
