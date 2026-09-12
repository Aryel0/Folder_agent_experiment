import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from unittest.mock import MagicMock

class TestPlanner(BaseAgentTest):
    def setUp(self):
        super().setUp()
        # Create planner and other capabilities for routing
        self.create_mock_capability("planner", "name: planner")
        self.create_mock_capability("summarizer", "name: summarizer")
        self.create_mock_capability("researcher", "name: researcher")
        self.create_mock_capability("writer", "name: writer")
        
        self.agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )

    def test_simple_routing(self):
        # Goal: Input 'Summarize this text' -> planner -> summarizer
        
        # Mock planner response
        mock_plan = {
            "tasks": [
                {"skill": "summarizer", "task": "Summarize the text", "depends_on": []}
            ]
        }
        
        # When agent executes, it will first consult planner (which uses generate)
        # Then it executes summarizer (which uses generate)
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "This is the summary."}]
        ]
        
        results = self.agent.execute("Summarize this text")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["skill"], "summarizer")
        self.assertEqual(results[0]["result"], "This is the summary.")

    def test_multi_capability_routing(self):
        # Input 'Research topic X and write a report' -> researcher, then writer
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "Research X", "depends_on": []},
                {"skill": "writer", "task": "Write report on X", "depends_on": [0]}
            ]
        }
        
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Research data"}],
            [{"response": "Final report"}]
        ]
        
        results = self.agent.execute("Research topic X and write a report")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["skill"], "researcher")
        self.assertEqual(results[1]["skill"], "writer")

    def test_no_capability_needed(self):
        # Input 'What is 2+2?' -> direct response (or chat/fallback)
        mock_plan = {
            "tasks": [
                {"skill": "chat", "task": "Answer what is 2+2", "depends_on": []}
            ]
        }
        self.create_mock_capability("chat", "name: chat")
        self.agent.register_capabilities(self.capabilities_root)
        
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "4"}]
        ]
        results = self.agent.execute("What is 2+2?")
        self.assertEqual(results[0]["skill"], "chat")
        
    def test_unknown_capability(self):
        # Planner outputs an unknown skill
        mock_plan = {
            "tasks": [
                {"skill": "unknown_skill", "task": "Do something", "depends_on": []}
            ]
        }
        
        # The agent should log a warning, retry, and eventually fail cleanly if max retries exceeded
        # We mock it to fail 3 times
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": json.dumps(mock_plan)}],
            [{"response": json.dumps(mock_plan)}]
        ]
        
        with self.assertRaises(ValueError) as context:
            self.agent.execute("Do something weird")
            
        self.assertIn("Planner failed to generate a valid plan", str(context.exception))
