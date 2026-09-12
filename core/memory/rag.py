from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except (ImportError, RuntimeError):
    CHROMA_AVAILABLE = False

from core.memory.base import MemoryStore
from core.memory.stores import _tokenize


class RAGStore(MemoryStore):
    """Retrieval-augmented generation over a directory of documents.

    Uses a Hybrid Search approach:
    1. Lexical Search (TF-IDF keyword matching)
    2. Semantic Search (ChromaDB vector embeddings)
    """

    def __init__(
        self,
        knowledge_dir: str = "memory/rag/documents",
        index_path: str = "memory/rag/index.json",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        chroma_db_dir: str = "memory/rag/chroma_db",
    ):
        """Initialize the Hybrid RAG memory store (TF-IDF + ChromaDB).
        
        Args:
            knowledge_dir (str): Directory containing raw document files (.md, .txt) to ingest.
            index_path (str): File path where the chunk index is saved and loaded.
            chunk_size (int): The character length of each chunk during text splitting.
            chunk_overlap (int): The number of overlapping characters between consecutive chunks.
            chroma_db_dir (str): Directory to store the persistent ChromaDB database.
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.index_path = Path(index_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks: list[dict] = []
        self.load()
        
        self.chroma_client = None
        self.chroma_collection = None
        if CHROMA_AVAILABLE:
            try:
                # Initialize persistent client
                db_path = Path(chroma_db_dir)
                db_path.mkdir(parents=True, exist_ok=True)
                self.chroma_client = chromadb.PersistentClient(path=str(db_path))
                
                # Use Ollama's highly optimized embedding model
                ollama_ef = embedding_functions.OllamaEmbeddingFunction(
                    model_name="nomic-embed-text",
                    url="http://localhost:11434/api/embeddings"
                )
                self.chroma_collection = self.chroma_client.get_or_create_collection(
                    name="rag_knowledge",
                    embedding_function=ollama_ef
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to initialize ChromaDB: {e}")
                self.chroma_client = None

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

        # 1. TF-IDF Search (Lexical)
        query_terms = _tokenize(query)
        doc_count = len(self.chunks)
        df: Counter = Counter()
        for chunk in self.chunks:
            unique_terms = set(_tokenize(chunk["content"]))
            for t in unique_terms:
                df[t] += 1

        tf_idf_scored: list[tuple[float, dict]] = []
        for chunk in self.chunks:
            chunk_terms = _tokenize(chunk["content"])
            term_freq = Counter(chunk_terms)
            score = 0.0
            for qt in query_terms:
                tf = term_freq.get(qt, 0)
                idf = math.log((doc_count + 1) / (df.get(qt, 0) + 1)) + 1
                score += tf * idf
            if score > 0:
                tf_idf_scored.append((score, chunk))

        tf_idf_scored.sort(key=lambda x: x[0], reverse=True)
        top_tf_idf = [item for _, item in tf_idf_scored[:k]]
        
        # 2. ChromaDB Search (Semantic)
        top_chroma = []
        if self.chroma_collection:
            try:
                results = self.chroma_collection.query(
                    query_texts=[query],
                    n_results=min(k, len(self.chunks))
                )
                if results and results.get("documents") and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                    ids = results["ids"][0]
                    
                    for doc, meta, doc_id in zip(docs, metas, ids):
                        top_chroma.append({
                            "id": doc_id,
                            "source": meta.get("source", "chroma"),
                            "content": doc,
                            "metadata": meta
                        })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"ChromaDB search failed: {e}")

        # 3. Merge and Deduplicate (Hybrid)
        merged_results = []
        seen_contents = set()
        
        # We interleave the results to balance lexical and semantic hits
        max_len = max(len(top_tf_idf), len(top_chroma))
        for i in range(max_len):
            if i < len(top_chroma):
                c_item = top_chroma[i]
                if c_item["content"] not in seen_contents:
                    seen_contents.add(c_item["content"])
                    merged_results.append(c_item)
            if i < len(top_tf_idf):
                t_item = top_tf_idf[i]
                if t_item["content"] not in seen_contents:
                    seen_contents.add(t_item["content"])
                    merged_results.append(t_item)
                    
            if len(merged_results) >= k:
                break
                
        return merged_results[:k]

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
        if self.chroma_collection:
            try:
                existing = self.chroma_collection.get()
                if existing and existing.get("ids"):
                    self.chroma_collection.delete(ids=existing["ids"])
            except Exception:
                pass
                
        chunk_id = 0
        chroma_documents = []
        chroma_metadatas = []
        chroma_ids = []

        for file_path in sorted(self.knowledge_dir.iterdir()):
            if file_path.suffix not in (".md", ".txt"):
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            for chunk_text in self._split_text(text):
                cleaned_text = chunk_text.strip()
                if not cleaned_text:
                    continue
                    
                self.chunks.append({
                    "id": chunk_id,
                    "source": file_path.name,
                    "content": cleaned_text,
                    "metadata": {"source": file_path.name},
                })
                
                if self.chroma_collection:
                    chroma_documents.append(cleaned_text)
                    chroma_metadatas.append({"source": file_path.name})
                    chroma_ids.append(f"chunk_{chunk_id}")
                    
                chunk_id += 1

        if self.chroma_collection and chroma_documents:
            # Batch add to avoid hitting limits
            batch_size = 100
            for i in range(0, len(chroma_documents), batch_size):
                self.chroma_collection.add(
                    documents=chroma_documents[i:i+batch_size],
                    metadatas=chroma_metadatas[i:i+batch_size],
                    ids=chroma_ids[i:i+batch_size]
                )

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
