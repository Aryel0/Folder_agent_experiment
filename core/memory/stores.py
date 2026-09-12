from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from core.memory.base import MemoryStore


# ---------------------------------------------------------------------------
# Short-term memory — in-memory conversation buffer
# ---------------------------------------------------------------------------

class ShortTermStore(MemoryStore):
    """In-memory conversation buffer for the current session.

    Entries are kept in insertion order and trimmed with FIFO once
    *max_entries* is exceeded.  search() returns the most recent entries
    (no keyword filtering — short-term is purely recency-based).
    """

    def __init__(self, max_entries: int = 50):
        """Initialize the short-term conversation buffer.
        
        Args:
            max_entries (int): The maximum number of entries to keep before purging old ones (default: 50).
        """
        self.max_entries = max_entries
        self.buffer: list[dict] = []

    def add(self, content: str, metadata: dict | None = None) -> None:
        entry = {
            "content": content,
            "metadata": metadata or {},
        }
        self.buffer.append(entry)

        # FIFO trim
        if len(self.buffer) > self.max_entries:
            self.buffer = self.buffer[-self.max_entries:]

    def search(self, query: str, k: int = 10) -> list[dict]:
        """Return the last *k* conversation entries (ignores query).
        
        Args:
            query (str): Ignored for short-term store, as it relies purely on recency.
            k (int): The number of recent entries to retrieve (default: 10).
            
        Returns:
            list[dict]: A list of recent conversation entries.
        """
        return self.buffer[-k:]

    def clear(self) -> None:
        self.buffer.clear()

    def to_prompt_str(self, query: str = "", k: int = 10) -> str:
        entries = self.search(query, k)
        lines = []
        for e in entries:
            role = e["metadata"].get("role", "unknown")
            lines.append(f"[{role}]: {e['content']}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Long-term memory — persistent JSON-backed fact store
# ---------------------------------------------------------------------------

class LongTermStore(MemoryStore):
    """Persistent fact store backed by a JSON file.

    Facts are stored with an optional *category* (e.g. "user", "project",
    "preference") and a timestamp.  search() uses keyword substring
    matching, ranking results by the number of query-term hits.
    """

    def __init__(self, path: str = "memory/long_term/facts.json"):
        """Initialize the persistent long-term fact store.
        
        Args:
            path (str): The file path where facts are stored and loaded from in JSON format.
        """
        self.path = Path(path)
        self.facts: list[dict] = []
        self.load()

    # -- MemoryStore interface -----------------------------------------------

    def add(self, content: str, metadata: dict | None = None) -> None:
        meta = metadata or {}
        entry = {
            "content": content,
            "category": meta.get("category", "general"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": meta,
        }
        self.facts.append(entry)
        self.save()

    def search(self, query: str, k: int = 5) -> list[dict]:
        if not query:
            # No query → return the most recent facts
            return self.facts[-k:]

        query_terms = _tokenize(query)
        scored: list[tuple[float, dict]] = []

        for fact in self.facts:
            fact_terms = _tokenize(fact["content"])
            hits = sum(1 for t in query_terms if t in fact_terms)
            if hits > 0:
                scored.append((hits, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:k]]

    def clear(self) -> None:
        self.facts.clear()
        if self.path.exists():
            self.path.unlink()

    # -- Persistence ---------------------------------------------------------

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.facts, indent=2, ensure_ascii=False))

    def load(self) -> None:
        if self.path.exists():
            try:
                self.facts = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self.facts = []





# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase and split text into a list of alphanumeric word tokens.
    
    Args:
        text (str): The input string to tokenize.
        
    Returns:
        list[str]: The extracted word tokens.
    """
    return re.findall(r"\w+", text.lower())
