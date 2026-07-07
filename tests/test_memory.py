"""Quick smoke test for the Memory system."""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory import Memory, ShortTermStore, LongTermStore, RAGStore
from core.memory.base import MemoryStore
import tempfile
import shutil

def test_abc_contract():
    """All stores must be instances of MemoryStore."""
    assert issubclass(ShortTermStore, MemoryStore)
    assert issubclass(LongTermStore, MemoryStore)
    assert issubclass(RAGStore, MemoryStore)
    print("[PASS] ABC contract")

def test_short_term():
    st = ShortTermStore(max_entries=3)
    st.add("hello", {"role": "user"})
    st.add("hi there", {"role": "agent"})
    st.add("what's 2+2?", {"role": "user"})
    st.add("4", {"role": "agent"})

    # Should have trimmed to 3
    results = st.search("", k=10)
    assert len(results) == 3, f"Expected 3, got {len(results)}"

    # Most recent should be "4"
    assert results[-1]["content"] == "4"

    # to_prompt_str should format with roles
    prompt = st.to_prompt_str()
    assert "[agent]: 4" in prompt

    st.clear()
    assert len(st.search("")) == 0
    print("[PASS] ShortTermStore")

def test_long_term():
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "facts.json")
        lt = LongTermStore(path=path)

        lt.add("User prefers Python 3.12", {"category": "preference"})
        lt.add("Project uses FastAPI framework", {"category": "project"})
        lt.add("Database is PostgreSQL", {"category": "project"})

        # Search by keyword
        results = lt.search("python", k=2)
        assert len(results) >= 1
        assert "Python" in results[0]["content"]

        # Verify persistence
        lt2 = LongTermStore(path=path)
        assert len(lt2.facts) == 3

        lt.clear()
        assert len(lt.facts) == 0
        print("[PASS] LongTermStore")
    finally:
        shutil.rmtree(tmp)

def test_rag():
    tmp = tempfile.mkdtemp()
    try:
        doc_dir = os.path.join(tmp, "documents")
        index_path = os.path.join(tmp, "index.json")
        os.makedirs(doc_dir)

        # Create some test documents
        with open(os.path.join(doc_dir, "guide.md"), "w") as f:
            f.write("Python is a programming language. It supports async await patterns. "
                    "FastAPI is built on top of Starlette and Pydantic.")
        with open(os.path.join(doc_dir, "notes.txt"), "w") as f:
            f.write("PostgreSQL supports JSON columns and full text search. "
                    "It is an open source relational database.")

        rag = RAGStore(knowledge_dir=doc_dir, index_path=index_path, chunk_size=100, chunk_overlap=20)
        count = rag.ingest()
        assert count > 0, "Should have created chunks"

        results = rag.search("PostgreSQL database", k=2)
        assert len(results) >= 1
        assert any("PostgreSQL" in r["content"] for r in results)

        rag.clear()
        assert len(rag.chunks) == 0
        print("[PASS] RAGStore")
    finally:
        shutil.rmtree(tmp)

def test_memory_facade():
    tmp = tempfile.mkdtemp()
    try:
        mem = Memory(storage_root=tmp)

        # Add to short-term
        mem.add("short_term", "Hello!", {"role": "user"})
        mem.add("short_term", "Hi, how can I help?", {"role": "agent"})

        # Add to long-term
        mem.add("long_term", "User likes dark mode", {"category": "preference"})

        # Recall should merge all stores with content
        context = mem.recall("dark mode")
        assert "[short_term]" in context
        assert "[long_term]" in context
        assert "Hello!" in context
        assert "dark mode" in context

        # Clear specific store
        mem.clear("short_term")
        context2 = mem.recall("dark mode")
        assert "[short_term]" not in context2
        assert "[long_term]" in context2

        print("[PASS] Memory facade")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    test_abc_contract()
    test_short_term()
    test_long_term()
    test_rag()
    test_memory_facade()
    print("\n✅ All memory tests passed!")
