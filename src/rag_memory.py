# src/rag_memory.py
import threading
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
from config import VAULT_PATH

_BASE = Path(__file__).parent.parent   # project root

# ── Module-level singletons: loaded once per process, shared by all agents ───
_chroma_client: chromadb.PersistentClient | None = None
_embedder: SentenceTransformer | None = None

# Locks for double-checked locking on singleton init
_singleton_lock = threading.Lock()

# Index gate: prevents concurrent agents from running _incremental_index
# simultaneously (ChromaDB SQLite does not support concurrent writes).
_index_lock   = threading.Lock()
_indexed_once = False   # True once the first full index pass completes


def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        with _singleton_lock:
            if _chroma_client is None:   # double-checked locking
                _chroma_client = chromadb.PersistentClient(path=str(_BASE / "chroma_db"))
    return _chroma_client


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        with _singleton_lock:
            if _embedder is None:        # double-checked locking
                _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


class RAGMemory:
    def __init__(self):
        # Re-use the process-level singletons — no model reload per agent
        self.client     = _get_chroma_client()
        self.collection = self.client.get_or_create_collection("trading_brain")
        self.embedder   = _get_embedder()
        self.vault_root = Path(VAULT_PATH)
        self._incremental_index()

    # ── Internal index helpers ────────────────────────────────────────────────

    def _do_index(self):
        """
        Scan the vault and (re-)index new or modified markdown files.
        MUST be called inside _index_lock to serialise ChromaDB writes.

        Text is truncated to 2 000 chars before embedding — all-MiniLM-L6-v2
        has a hard 512-token (~400-word) limit; anything beyond is silently
        dropped by the transformer, so embedding more wastes time without
        improving retrieval quality.
        """
        for md_file in self.vault_root.rglob("*.md"):
            try:
                file_mtime = md_file.stat().st_mtime
            except OSError:
                continue
            doc_id = str(md_file)

            existing = self.collection.get(ids=[doc_id], include=["metadatas"])
            if existing["ids"]:
                old_mtime = existing["metadatas"][0].get("mtime", 0)
                if file_mtime <= old_mtime:
                    continue           # unchanged — skip
                self.collection.delete(ids=[doc_id])   # stale entry — re-index

            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")[:2000]
            except OSError:
                continue
            embedding = self.embedder.encode(text).tolist()
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                ids=[doc_id],
                metadatas=[{"path": doc_id, "mtime": file_mtime}],
            )

    def _incremental_index(self):
        """
        Index new/modified vault notes.  Runs at most ONCE per process on
        first call; subsequent agents skip (index is already current).
        Serialised by _index_lock so parallel agent initialisations cannot
        trigger concurrent ChromaDB writes.
        """
        global _indexed_once
        with _index_lock:
            if _indexed_once:
                return
            self._do_index()
            _indexed_once = True

    def refresh(self):
        """
        Force a fresh incremental scan — call this after the orchestrator has
        written a batch of vault files mid-run so agents started later see them.
        """
        with _index_lock:
            self._do_index()
            # Keep _indexed_once = True so subsequent agent __init__ calls still skip.

    # ── Public retrieval ──────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 8) -> str:
        query_emb = self.embedder.encode(query).tolist()
        results   = self.collection.query(query_embeddings=[query_emb], n_results=top_k)
        return (
            "\n\n---\n\n".join(results["documents"][0])
            if results["documents"]
            else "No relevant memory found."
        )
