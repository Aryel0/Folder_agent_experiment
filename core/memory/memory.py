from __future__ import annotations

from core.memory.base import MemoryStore
from core.memory.stores import ShortTermStore, LongTermStore, RAGStore


class Memory:
    """Unified memory manager.

    Manages a dict of MemoryStore backends and treats them all through
    the same interface.  The agent interacts only with this facade.

    Default stores: short_term, long_term, rag.
    Add custom backends at any time via register().
    """

    def __init__(self, storage_root: str = "memory"):
        """Initialize the unified memory manager and its default backend stores.
        
        Args:
            storage_root (str): The root directory for persistent memory stores (default: "memory").
        """
        self.storage_root = storage_root
        self.stores: dict[str, MemoryStore] = {}

        # Register the three default backends
        self.register("short_term", ShortTermStore())
        self.register("long_term", LongTermStore(
            path=f"{storage_root}/long_term/facts.json",
        ))
        self.register("rag", RAGStore(
            knowledge_dir=f"{storage_root}/rag/documents",
            index_path=f"{storage_root}/rag/index.json",
        ))

    # -- Store management ----------------------------------------------------

    def register(self, name: str, store: MemoryStore) -> None:
        """Register a memory backend under the given name.
        
        Args:
            name (str): The identifier name for the store.
            store (MemoryStore): An instantiated backend that implements the MemoryStore interface.
        """
        self.stores[name] = store

    def unregister(self, name: str) -> None:
        """Remove a memory backend by name.
        
        Args:
            name (str): The identifier name of the store to remove.
        """
        self.stores.pop(name, None)

    def get_store(self, name: str) -> MemoryStore | None:
        """Get a specific backend by name.
        
        Args:
            name (str): The identifier name of the store.
            
        Returns:
            MemoryStore | None: The registered memory store, or None if not found.
        """
        return self.stores.get(name)

    # -- Unified operations --------------------------------------------------

    def add(self, store_name: str, content: str, metadata: dict | None = None) -> None:
        """Write to a specific store by name.

        Args:
            store_name: Which backend to write to (e.g. "short_term").
            content: The text to store.
            metadata: Optional key-value pairs passed to the backend.
        """
        store = self.stores.get(store_name)
        if store is None:
            raise KeyError(f"Unknown memory store: {store_name!r}")
        store.add(content, metadata)

    def recall(self, query: str = "", k: int = 5) -> str:
        """Query ALL registered stores and merge results into a prompt string.

        Each store's output is labelled with its name so the agent can
        distinguish short-term context from long-term facts from RAG.
        
        Args:
            query (str): The search term or context query (default: "").
            k (int): Maximum number of results to retrieve per store (default: 5).
            
        Returns:
            str: A formatted string concatenating results from all registered stores.
        """
        parts: list[str] = []
        for name, store in self.stores.items():
            result = store.to_prompt_str(query, k)
            if result.strip():
                parts.append(f"[{name}]\n{result}")
        return "\n\n".join(parts)

    def clear(self, store_name: str | None = None) -> None:
        """Clear a specific store, or all stores if no name is given.
        
        Args:
            store_name (str | None): The specific store name to clear, or None to clear all (default: None).
        """
        if store_name:
            store = self.stores.get(store_name)
            if store:
                store.clear()
        else:
            for store in self.stores.values():
                store.clear()

    # -- Persistence helpers -------------------------------------------------

    def save(self) -> None:
        """Persist stores that support it (long-term, rag).
        
        Iterates through all registered stores and calls their `save()` method if it exists.
        """
        for store in self.stores.values():
            if hasattr(store, "save"):
                store.save()

    def load(self) -> None:
        """Load persistent stores from disk.
        
        Iterates through all registered stores and calls their `load()` method if it exists.
        """
        for store in self.stores.values():
            if hasattr(store, "load"):
                store.load()

    def ingest_knowledge(self) -> int:
        """Trigger RAG ingestion if a RAGStore is registered.
        
        Returns:
            int: The number of document chunks ingested and indexed, or 0 if no RAG store is registered.
        """
        rag = self.stores.get("rag")
        if rag and hasattr(rag, "ingest"):
            return rag.ingest()
        return 0
