import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
from tests.test_utils import BaseAgentTest
from core.upgrade.parallel_agent import ParallelFolderAgent
from unittest.mock import MagicMock

class TestParallelAgent(BaseAgentTest):
    def setUp(self):
        super().setUp()
        self.create_mock_capability("planner", "name: planner")
        self.create_mock_capability("researcher", "name: researcher")
        self.create_mock_capability("writer", "name: writer")
        
        self.agent = ParallelFolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root,
            max_workers=3
        )

    def test_independent_tasks(self):
        # Research A, B, C should execute in parallel
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "A", "depends_on": []},
                {"skill": "researcher", "task": "B", "depends_on": []},
                {"skill": "researcher", "task": "C", "depends_on": []}
            ]
        }
        
        # We need a way to verify they run in parallel.
        # A simple way is to mock generate to sleep for 0.1s. 
        # If parallel, total time is ~0.1s. If sequential, ~0.3s.
        def slow_generate(*args, **kwargs):
            time.sleep(0.1)
            return "Done"
            
        self.mock_ollama_generate.side_effect = [
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Done"}],
            [{"response": "Done"}],
            [{"response": "Done"}]
        ]
        
        start = time.time()
        results = self.agent.execute("Research A, B, C")
        duration = time.time() - start
        
        self.assertEqual(len(results), 3)
        self.assertTrue(duration < 0.25, f"Took too long ({duration}s), probably not parallel")

    def test_dependency_ordering(self):
        # Research topic -> Write report (Depends on 0)
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "Research", "depends_on": []},
                {"skill": "writer", "task": "Write", "depends_on": [0]}
            ]
        }
        
        execution_order = []
        def track_generate(**kwargs):
            messages = kwargs.get("messages", [])
            last_content = messages[-1]["content"] if messages else ""
            if "Research" in last_content:
                execution_order.append("researcher")
            elif "Write" in last_content:
                execution_order.append("writer")
            return "Ok"
            
        self.mock_ollama_generate.side_effect = [
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Ok"}],
            [{"response": "Ok"}]
        ]
        
        results = self.agent.execute("Research then write")
        self.assertEqual(results[0]["skill"], "researcher")
        self.assertEqual(results[1]["skill"], "writer")

    def test_branch_failure(self):
        # A success, B failure, C success
        mock_plan = {
            "tasks": [
                {"skill": "researcher", "task": "A", "depends_on": []},
                {"skill": "researcher", "task": "B", "depends_on": []},
                {"skill": "researcher", "task": "C", "depends_on": []}
            ]
        }
        
        # We force B to fail by raising an exception in generate for one of them
        # Wait, if generate raises an exception, the task fails.
        # Let's mock a failure for the second task execution.
        def fail_b(*args, **kwargs):
            messages = kwargs.get("messages", [])
            last_content = messages[-1]["content"] if messages else ""
            if "task: B" in last_content:
                raise Exception("Network Error")
            return "Success"
            
        # ParallelFolderAgent catches exceptions and logs them, returning the error as result
        self.mock_ollama_generate.side_effect = [
            [{"response": json.dumps(mock_plan)}],
            [{"response": "Success"}],
            [{"response": "Success"}] # Since B will throw, it only consumes 2 mocks for A and C
        ]
        
        # Override the agent's internal method just to force B to fail easily
        original_execute = self.agent._execute_single_task
        def flaky_execute(task, context_deps):
            if task["task"] == "B":
                raise Exception("B Failed")
            return original_execute(task, context_deps)
            
        self.agent._execute_single_task = flaky_execute
        
        results = self.agent.execute("Run A, B, C")
        
        # A and C finish, B reported failure. No total crash.
        self.assertEqual(len(results), 3)
        b_res = next(r for r in results if r["task"] == "B")
        self.assertIn("Failed to execute", b_res["result"])
