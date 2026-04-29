import chromadb
from chromadb.api.models.Collection import Collection
from rank_bm25 import BM25Okapi

from app.core.config import get_settings


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = chromadb.PersistentClient(path=settings.vector_persist_dir)
        self.collection: Collection = self.client.get_or_create_collection(name=settings.vector_collection)
        self._bm25_index: BM25Okapi | None = None
        self._bm25_ids: list[str] = []
        self._bm25_docs: list[str] = []
        self._bm25_metas: list[dict] = []

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self.collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        self._invalidate_bm25()

    def search(self, query_embedding: list[float], top_k: int) -> list[dict]:
        result = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]
        return [
            {
                "id": ids[idx],
                "content": docs[idx],
                "metadata": metas[idx] or {},
                "score": float(dists[idx]) if idx < len(dists) else 0.0,
            }
            for idx in range(len(docs))
        ]

    def search_hybrid(
        self,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
        dense_candidate_k: int,
    ) -> list[dict]:
        dense_hits = self.search(query_embedding=query_embedding, top_k=max(top_k, dense_candidate_k))
        bm25_hits = self._search_bm25(query_text=query_text, top_k=max(top_k, dense_candidate_k))
        return self._merge_hybrid(dense_hits=dense_hits, bm25_hits=bm25_hits, top_k=top_k)

    def delete_by_file_id(self, file_id: str) -> None:
        self.collection.delete(where={"file_id": file_id})
        self._invalidate_bm25()

    def get_chunk(self, file_id: str, chunk_index: int) -> dict | None:
        doc_id = f"{file_id}_{chunk_index}"
        result = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
        ids = result.get("ids", [])
        if not ids:
            return None
        docs = result.get("documents", [])
        metas = result.get("metadatas", [])
        return {
            "id": ids[0] if ids else doc_id,
            "content": docs[0] if docs else "",
            "metadata": metas[0] if metas else {},
        }

    def _search_bm25(self, query_text: str, top_k: int) -> list[dict]:
        self._ensure_bm25_index()
        if not self._bm25_index or not self._bm25_docs:
            return []
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []
        raw_scores = self._bm25_index.get_scores(query_tokens)
        ranking = sorted(enumerate(raw_scores), key=lambda item: item[1], reverse=True)[:top_k]
        return [
            {
                "id": self._bm25_ids[idx],
                "content": self._bm25_docs[idx],
                "metadata": self._bm25_metas[idx] or {},
                "score": float(score),
            }
            for idx, score in ranking
            if score > 0
        ]

    def _merge_hybrid(self, dense_hits: list[dict], bm25_hits: list[dict], top_k: int) -> list[dict]:
        dense_scores = {item["id"]: 1.0 / (1.0 + max(float(item.get("score", 0.0)), 0.0)) for item in dense_hits}
        bm25_scores = {item["id"]: float(item.get("score", 0.0)) for item in bm25_hits}
        dense_norm = self._normalize_scores(dense_scores)
        bm25_norm = self._normalize_scores(bm25_scores)
        merged: dict[str, dict] = {}
        for item in dense_hits + bm25_hits:
            item_id = item["id"]
            merged[item_id] = {
                "id": item_id,
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}) or {},
                "dense_score": dense_norm.get(item_id, 0.0),
                "bm25_score": bm25_norm.get(item_id, 0.0),
            }
        for item in merged.values():
            item["hybrid_score"] = (
                self.settings.hybrid_dense_weight * item["dense_score"]
                + self.settings.hybrid_bm25_weight * item["bm25_score"]
            )
        ranked = sorted(merged.values(), key=lambda row: row["hybrid_score"], reverse=True)[:top_k]
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "metadata": row["metadata"],
                "score": row["hybrid_score"],
                "dense_score": row["dense_score"],
                "bm25_score": row["bm25_score"],
            }
            for row in ranked
        ]

    def _ensure_bm25_index(self) -> None:
        if self._bm25_index is not None:
            return
        data = self.collection.get(include=["documents", "metadatas"])
        ids = data.get("ids", []) or []
        docs = data.get("documents", []) or []
        metas = data.get("metadatas", []) or []
        if not ids or not docs:
            self._bm25_index = None
            self._bm25_ids = []
            self._bm25_docs = []
            self._bm25_metas = []
            return
        tokenized_docs = [self._tokenize(doc) for doc in docs]
        tokenized_docs = [tokens if tokens else ["_"] for tokens in tokenized_docs]
        self._bm25_index = BM25Okapi(tokenized_docs)
        self._bm25_ids = ids
        self._bm25_docs = docs
        self._bm25_metas = metas

    def _invalidate_bm25(self) -> None:
        self._bm25_index = None
        self._bm25_ids = []
        self._bm25_docs = []
        self._bm25_metas = []

    def _normalize_scores(self, scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        values = list(scores.values())
        min_score = min(values)
        max_score = max(values)
        if max_score - min_score < 1e-9:
            return {k: 1.0 for k in scores}
        return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

    def _tokenize(self, text: str) -> list[str]:
        stripped = (text or "").strip().lower()
        if not stripped:
            return []
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in stripped)
        if has_cjk:
            return [ch for ch in stripped if not ch.isspace()]
        return [token for token in stripped.split() if token]
