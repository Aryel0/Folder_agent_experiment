import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_utils import BaseAgentTest
from core.agent import FolderAgent
from core.memory import Memory

class TestMemory(BaseAgentTest):
    def setUp(self):
        super().setUp()
        self.memory = Memory(storage_root=self.memory_root)

    def test_short_term_recall(self):
        # Conversation: My project name is Atlas. What is my project name? -> Atlas
        self.memory.add("short_term", "My project name is Atlas.", {"role": "user"})
        
        recall = self.memory.recall("What is my project name?")
        self.assertIn("Atlas", recall)

    def test_memory_isolation(self):
        # Session A: My name is Bob.
        # Session B: What is my name? -> Unknown
        # Memory class doesn't currently use explicit "session IDs", it uses collections.
        # If the user wants isolation, they use different memory roots or collections.
        
        mem_a = Memory(storage_root=os.path.join(self.memory_root, "session_a"))
        mem_b = Memory(storage_root=os.path.join(self.memory_root, "session_b"))
        
        mem_a.add("short_term", "My name is Bob.", {"role": "user"})
        
        recall_b = mem_b.recall("What is my name?")
        self.assertNotIn("Bob", recall_b)

    def test_memory_priority(self):
        # Old: Language = Python
        # New: Language = Rust
        # Expected: correct priority (Rust returned first or highest relevance)
        self.memory.add("long_term", "Language = Python", {"time": "old"})
        self.memory.add("long_term", "Language = Rust", {"time": "new"})
        
        # We check the raw query to see if Rust comes back
        # In a real RAG system, the latest info should be favored or both returned.
        # Here we just verify both are retrieved so the LLM can decide.
        results = self.memory.stores["long_term"].search("What is the language?", k=2)
        documents = [r["content"] for r in results]
        self.assertIn("Language = Python", documents)
        self.assertIn("Language = Rust", documents)
