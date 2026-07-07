from __future__ import annotations

from abc import ABC, abstractmethod


class MemoryStore(ABC):
    """Single interface for all memory backends.

    Every memory type (short-term, long-term, RAG, or any future backend)
    implements this contract so the Memory facade can manage them uniformly.
    """

    @abstractmethod
    def add(self, content: str, metadata: dict | None = None) -> None:
        """Store a piece of information.

        Args:
            content: The text to store.
            metadata: Optional key-value pairs (e.g. role, category, source).
        """
        ...

    @abstractmethod
    def search(self, query: str, k: int = 5) -> list[dict]:
        """Retrieve the most relevant entries.

        Args:
            query: The search query (can be empty for recency-based stores).
            k: Maximum number of results to return.

        Returns:
            List of dicts with at least a "content" key.
            Example: [{"content": "...", "metadata": {...}}]
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries from this store."""
        ...

    def to_prompt_str(self, query: str = "", k: int = 5) -> str:
        """Format search results as a string for prompt injection.

        This default implementation joins the content of each result with
        newlines. Backends can override for custom formatting.
        """
        results = self.search(query, k)
        return "\n".join(r["content"] for r in results)
