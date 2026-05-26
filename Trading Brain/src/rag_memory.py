# src/rag_memory.py
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
import os
from config import VAULT_PATH

class RAGMemory:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="chroma_db")
        self.collection = self.client.get_or_create_collection("trading_brain")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vault_root = Path(VAULT_PATH)
        self._incremental_index()   # Only index new/changed files
    
    def _incremental_index(self):
        for md_file in self.vault_root.rglob("*.md"):
            file_mtime = md_file.stat().st_mtime
            doc_id = str(md_file)
            # Only re-index if file is new or changed
            if not self.collection.get(ids=[doc_id])['ids']:
                text = md_file.read_text(encoding="utf-8")[:8000]
                embedding = self.embedder.encode(text).tolist()
                self.collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    ids=[doc_id],
                    metadatas=[{"path": doc_id, "mtime": file_mtime}]
                )
    
    def retrieve(self, query: str, top_k: int = 8) -> str:
        query_emb = self.embedder.encode(query).tolist()
        results = self.collection.query(query_embeddings=[query_emb], n_results=top_k)
        return "\n\n---\n\n".join(results["documents"][0]) if results["documents"] else "No relevant memory found."