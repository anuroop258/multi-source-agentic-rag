from __future__ import annotations
from pathlib import Path
from typing import Any
from collections import Counter
import threading

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

class HybridRetriever:
    """Local Chroma dense retrieval + BM25 sparse retrieval + RRF + CrossEncoder."""
    def __init__(self, persist_dir: Path, collection_name: str = "rag_documents"):
        import chromadb
        self.persist_dir = str(persist_dir)
        self.collection_name = collection_name
        # The API serves requests from a thread pool; Chroma + BM25 rebuilds must not interleave.
        self._lock = threading.RLock()
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        # Load transformer weights lazily: merely opening the UI or checking the
        # collection count should not trigger large first-run downloads.
        self.embedder = None
        self.reranker = None
        self._bm25 = None
        self._bm25_ids: list[str] = []
        self._bm25_docs: list[str] = []
        self._bm25_meta: list[dict] = []
        self._rebuild_sparse_index()

    def _ensure_models(self) -> None:
        if self.embedder is None or self.reranker is None:
            from sentence_transformers import SentenceTransformer, CrossEncoder
            if self.embedder is None:
                self.embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
            if self.reranker is None:
                self.reranker = CrossEncoder(RERANKER_MODEL, device="cpu")

    def _rebuild_sparse_index(self) -> None:
        from rank_bm25 import BM25Okapi
        raw = self.collection.get(include=["documents", "metadatas"])
        self._bm25_ids = raw.get("ids") or []
        self._bm25_docs = raw.get("documents") or []
        self._bm25_meta = raw.get("metadatas") or []
        valid = [(i, d) for i, d in enumerate(self._bm25_docs) if d]
        if not valid:
            self._bm25 = None
            return
        self._bm25_ids = [self._bm25_ids[i] for i, _ in valid]
        self._bm25_docs = [d for _, d in valid]
        self._bm25_meta = [self._bm25_meta[i] or {} for i, _ in valid]
        self._bm25 = BM25Okapi([d.lower().split() for d in self._bm25_docs])

    def _add_chunks_unlocked(self, chunks: list[Any], batch_size: int = 32, replace_sources: list[str] | None = None) -> int:
        replace_sources = list(dict.fromkeys(replace_sources or []))
        if not chunks:
            # A newly uploaded but text-empty file should not leave stale passages indexed.
            for source in replace_sources:
                self.collection.delete(where={"source": source})
            if replace_sources:
                self._rebuild_sparse_index()
            return 0
        self._ensure_models()
        # Embed new content before deleting old content so a model/download failure
        # does not destroy a previously working index for the same source file.
        prepared = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            texts = [c.text for c in batch]
            vectors = self.embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
            prepared.append((batch, vectors))
        for source in replace_sources:
            self.collection.delete(where={"source": source})
        added = 0
        for batch, vectors in prepared:
            self.collection.upsert(
                ids=[c.chunk_id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[c.metadata for c in batch],
                embeddings=vectors,
            )
            added += len(batch)
        self._rebuild_sparse_index()
        return added

    def _search_unlocked(self, query: str, k: int = 5, candidates: int = 15) -> list[dict]:
        query = query.strip()
        if not query or self.collection.count() == 0:
            return []
        self._ensure_models()
        query_vector = self.embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)[0].tolist()
        dense_raw = self.collection.query(
            query_embeddings=[query_vector],
            n_results=min(max(candidates, k), self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        dense = []
        for i, doc_id in enumerate((dense_raw.get("ids") or [[]])[0]):
            dense.append({
                "id": doc_id,
                "text": (dense_raw.get("documents") or [[]])[0][i],
                "metadata": (dense_raw.get("metadatas") or [[]])[0][i] or {},
                "distance": (dense_raw.get("distances") or [[]])[0][i],
            })
        sparse = []
        if self._bm25 is not None:
            scores = self._bm25.get_scores(query.lower().split())
            ranked = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)[:candidates]
            sparse = [
                {"id": self._bm25_ids[i], "text": self._bm25_docs[i], "metadata": self._bm25_meta[i], "bm25": float(scores[i])}
                for i in ranked if scores[i] > 0
            ]
        fused = {}
        for results in (dense, sparse):
            for rank, item in enumerate(results, start=1):
                entry = fused.setdefault(item["id"], {**item, "rrf_score": 0.0})
                entry["rrf_score"] += 1.0 / (60 + rank)
        pool = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)[:max(k * 3, k)]
        if not pool:
            return []
        pairs = [(query, item["text"]) for item in pool]
        scores = self.reranker.predict(pairs, show_progress_bar=False)
        ranked_items = sorted(zip(scores, pool), key=lambda pair: float(pair[0]), reverse=True)
        results = []
        for score, item in ranked_items[:k]:
            results.append({
                "id": item["id"],
                "text": item["text"],
                "metadata": item["metadata"],
                "rerank_score": float(score),
                "rrf_score": float(item["rrf_score"]),
            })
        return results

    def count(self) -> int:
        return int(self.collection.count())

    def _clear_unlocked(self) -> None:
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._rebuild_sparse_index()

    def add_chunks(self, chunks, batch_size: int = 32, replace_sources=None) -> int:
        with self._lock:
            return self._add_chunks_unlocked(chunks, batch_size, replace_sources)

    def search(self, query: str, k: int = 5, candidates: int = 15) -> list[dict]:
        with self._lock:
            return self._search_unlocked(query, k, candidates)

    def clear(self) -> None:
        with self._lock:
            self._clear_unlocked()

    def sources(self) -> dict[str, int]:
        """Indexed chunk count per source file name."""
        with self._lock:
            raw = self.collection.get(include=["metadatas"])
        counts = Counter((m or {}).get("source", "unknown") for m in (raw.get("metadatas") or []))
        return dict(counts)

    def delete_source(self, source: str) -> None:
        with self._lock:
            self.collection.delete(where={"source": source})
            self._rebuild_sparse_index()
