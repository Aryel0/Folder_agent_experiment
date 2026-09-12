import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tests.test_utils import BaseAgentTest
from core.upgrade.learning_agent import LearningFolderAgent
from unittest.mock import MagicMock

class TestLearningAgent(BaseAgentTest):
    def setUp(self):
        super().setUp()
        self.create_mock_capability("planner", "name: planner")
        self.create_mock_capability("researcher", "name: researcher")
        
        self.agent = LearningFolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root
        )

    def test_improvement_proposal(self):
        # Provide failed execution -> Learning agent proposes change.
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "A", "depends_on": []}
            ]
        }
        
        # We simulate the execute task failing, then reflect_on_execution is called
        # mock_ollama_generate must return plan, then task failure, then reflection proposal
        self.mock_ollama_generate.side_effect = [
            {"response": json.dumps({"selected_capability": "planner"})},
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Error: something failed"}],
            [{"response": "Learning: We should retry with different parameters."}]
        ]
        
        results = self.agent.execute("Do A")
        self.assertEqual(results[0]["result"], "Error: something failed")
        
        # Verify that memory has stored the lesson
        lessons = self.agent.memory.recall("lessons")
        self.assertIsNotNone(lessons)
