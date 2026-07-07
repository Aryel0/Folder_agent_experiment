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
# RAG memory — chunk-and-retrieve over a knowledge directory
# ---------------------------------------------------------------------------

class RAGStore(MemoryStore):
    """Retrieval-augmented generation over a directory of documents.

    Documents (.md, .txt) are split into overlapping chunks and indexed
    with TF-IDF-style keyword scoring.  No external embedding model or
    vector DB is required.

    If the knowledge directory doesn't exist or is empty, all operations
    silently return empty results.
    """

    def __init__(
        self,
        knowledge_dir: str = "memory/rag/documents",
        index_path: str = "memory/rag/index.json",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """Initialize the RAG (Retrieval-Augmented Generation) memory store.
        
        Args:
            knowledge_dir (str): Directory containing raw document files (.md, .txt) to ingest.
            index_path (str): File path where the chunk index is saved and loaded.
            chunk_size (int): The character length of each chunk during text splitting.
            chunk_overlap (int): The number of overlapping characters between consecutive chunks.
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.index_path = Path(index_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks: list[dict] = []
        self.load()

    # -- MemoryStore interface -----------------------------------------------

    def add(self, content: str, metadata: dict | None = None) -> None:
        """Manually add a single chunk to the RAG store.
        
        Note: Prefer using `ingest()` for bulk loading documents from the knowledge directory.
        
        Args:
            content (str): The text content of the chunk.
            metadata (dict | None): Optional metadata (e.g., 'source' filename).
        """
        meta = metadata or {}
        self.chunks.append({
            "id": len(self.chunks),
            "source": meta.get("source", "manual"),
            "content": content,
            "metadata": meta,
        })
        self.save()

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self.chunks or not query:
            return []

        query_terms = _tokenize(query)
        # document frequencies (for IDF)
        doc_count = len(self.chunks)
        df: Counter = Counter()
        for chunk in self.chunks:
            unique_terms = set(_tokenize(chunk["content"]))
            for t in unique_terms:
                df[t] += 1

        scored: list[tuple[float, dict]] = []
        for chunk in self.chunks:
            chunk_terms = _tokenize(chunk["content"])
            term_freq = Counter(chunk_terms)
            score = 0.0
            for qt in query_terms:
                tf = term_freq.get(qt, 0)
                idf = math.log((doc_count + 1) / (df.get(qt, 0) + 1)) + 1
                score += tf * idf
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:k]]

    def clear(self) -> None:
        self.chunks.clear()
        if self.index_path.exists():
            self.index_path.unlink()

    # -- Ingestion -----------------------------------------------------------

    def ingest(self) -> int:
        """Read all documents from the knowledge_dir, chunk them, and build the index.
        
        Scans for .md and .txt files, splits their contents into overlapping chunks,
        and saves the resulting index to disk.
        
        Returns:
            int: The total number of chunks created and indexed.
        """
        if not self.is_available():
            return 0

        self.chunks.clear()
        chunk_id = 0

        for file_path in sorted(self.knowledge_dir.iterdir()):
            if file_path.suffix not in (".md", ".txt"):
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            for chunk_text in self._split_text(text):
                self.chunks.append({
                    "id": chunk_id,
                    "source": file_path.name,
                    "content": chunk_text.strip(),
                    "metadata": {"source": file_path.name},
                })
                chunk_id += 1

        self.save()
        return len(self.chunks)

    def is_available(self) -> bool:
        """Check if the knowledge directory exists and contains any files.
        
        Returns:
            bool: True if the directory exists and is non-empty, False otherwise.
        """
        if not self.knowledge_dir.exists():
            return False
        return any(self.knowledge_dir.iterdir())

    # -- Persistence ---------------------------------------------------------

    def save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(self.chunks, indent=2, ensure_ascii=False))

    def load(self) -> None:
        if self.index_path.exists():
            try:
                self.chunks = json.loads(self.index_path.read_text())
            except (json.JSONDecodeError, OSError):
                self.chunks = []

    # -- Internal ------------------------------------------------------------

    def _split_text(self, text: str) -> list[str]:
        """Split a large text into smaller overlapping chunks based on character count.
        
        Args:
            text (str): The raw text to split.
            
        Returns:
            list[str]: A list of text chunks.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += self.chunk_size - self.chunk_overlap
        return chunks


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
