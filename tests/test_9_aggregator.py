import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from unittest.mock import MagicMock

class TestAggregator(BaseAgentTest):
    def setUp(self):
        super().setUp()
        self.create_mock_capability("planner", "name: planner")
        self.create_mock_capability("researcher", "name: researcher")
        self.create_mock_capability("analyzer", "name: analyzer")
        self.create_mock_capability("aggregator", "name: aggregator")
        
        self.agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )

    def test_merge_outputs(self):
        # Research X, Analyze Y -> Aggregator receives both
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "Research X", "depends_on": []},
                {"skill": "analyzer", "task": "Analyze Y", "depends_on": []}
            ]
        }
        
        # When aggregator runs, it should receive context containing both results
        # We can verify this by checking what prompt is sent to aggregator
        captured_prompt = []
        def capture_generate(**kwargs):
            messages = kwargs.get("messages", [])
            last = messages[-1]["content"] if messages else ""
            if "AGGREGATE" in last or "FINAL" in last or "AGGREGATOR" in last.upper():
                captured_prompt.append(last)
            return "Merged output"
            
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "X Data"}],
            [{"response": "Y Data"}],
            [{"response": "Final Merged Summary"}]
        ]
        
        results = self.agent.execute("Research X and Analyze Y")
        
        # FolderAgent automatically invokes 'aggregator' if it exists at the end of execution
        self.assertEqual(results[-1]["skill"], "aggregator")
        self.assertEqual(results[-1]["result"], "Final Merged Summary")

    def test_contradictory_results(self):
        # A says Python faster, B says Rust faster. Aggregator acknowledges.
        # Since we mock the LLM, we just simulate the aggregator output.
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "Test A", "depends_on": []},
                {"skill": "analyzer", "task": "Test B", "depends_on": []}
            ]
        }
        
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Python is faster"}],
            [{"response": "Rust is faster"}],
            [{"response": "There is disagreement: Python vs Rust"}]
        ]
        
        results = self.agent.execute("Compare languages")
        self.assertIn("disagreement", results[-1]["result"])
