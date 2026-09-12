import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from core.tools.registery.files import WriteFileTool
from core.tools.registery.python_exec import ExecutePythonTool

class TestSecurity(BaseAgentTest):
    def setUp(self):
        super().setUp()
        self.sandbox_dir = os.path.join(self.test_dir, "workspace")
        os.makedirs(self.sandbox_dir)
        
        self.agent = FolderAgent(
            model_name="mock-model",
            memory_root=self.memory_root,
            capabilities_root=self.capabilities_root,
            allowed_directories=[self.sandbox_dir]
        )

    def test_protected_file_write(self):
        # Attempt to modify core/agent.py -> Denied
        write_tool = self.agent.registry.tools.get("write_file")
        result = write_tool.run(file_path="core/agent.py", content="hack")
        self.assertIn("Security policy prevents", result)

    def test_allowed_directory_write(self):
        # Attempt to modify workspace/test.py -> Allowed
        write_tool = self.agent.registry.tools.get("write_file")
        safe_path = os.path.join(self.sandbox_dir, "test.py")
        result = write_tool.run(file_path=safe_path, content="print('hello')")
        self.assertIn("Successfully wrote", result)
        self.assertTrue(os.path.exists(safe_path))

    def test_path_traversal(self):
        # Attempt workspace/../../core/agent.py -> Denied
        write_tool = self.agent.registry.tools.get("write_file")
        sneaky_path = os.path.join(self.sandbox_dir, "..", "..", "core", "agent.py")
        result = write_tool.run(file_path=sneaky_path, content="hack")
        self.assertIn("Security policy prevents", result)

    def test_python_sandbox_escape(self):
        # Try open() outside sandbox via python exec
        py_tool = self.agent.registry.tools.get("execute_python")
        
        # We must mock the authorize prompt
        py_tool.authorize_execution = lambda p: True
        
        code = '''
with open("../../../core/agent.py", "w") as f:
    f.write("hacked")
'''
        result = py_tool.run(code=code)
        self.assertIn("PermissionError", result)
        self.assertIn("Security policy prevents", result)
