import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from unittest.mock import MagicMock

class TestE2E(BaseAgentTest):
    def setUp(self):
        super().setUp()
        self.create_mock_capability("planner", "name: planner")
        self.create_mock_capability("analyzer", "name: analyzer")
        self.create_mock_capability("researcher", "name: researcher")
        self.create_mock_capability("coder", "name: coder")
        self.create_mock_capability("writer", "name: writer")
        self.create_mock_capability("aggregator", "name: aggregator")
        
        self.agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )

    def test_full_end_to_end_analysis(self):
        # Boss Fight: Analyze this repository. Find problems. Research solutions. Implement fixes. Run tests. Generate report.
        mock_plan = {
            "tasks": [
                {"skill": "analyzer", "task": "Analyze repo", "depends_on": []},
                {"skill": "researcher", "task": "Research solutions", "depends_on": [0]},
                {"skill": "coder", "task": "Implement fixes", "depends_on": [1]},
                {"skill": "coder", "task": "Run tests", "depends_on": [2]},
                {"skill": "writer", "task": "Generate report", "depends_on": [3]}
            ]
        }
        
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Found 3 bugs"}],             # Analyzer
            [{"response": "Found fixes online"}],       # Researcher
            [{"response": "Code fixed"}],               # Coder (Implement)
            [{"response": "All tests passed"}],         # Coder (Tests)
            [{"response": "Report: bugs fixed"}],       # Writer
            [{"response": "Final E2E Dashboard"}]       # Aggregator
        ]
        
        results = self.agent.execute("Analyze repo, fix problems, write report")
        
        self.assertEqual(len(results), 6) # 5 tasks + 1 aggregator
        self.assertEqual(results[0]["skill"], "analyzer")
        self.assertEqual(results[-1]["skill"], "aggregator")
        self.assertEqual(results[-1]["result"], "Final E2E Dashboard")
