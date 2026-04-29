import asyncio
import logging
import math
import time
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.db_models import QARecord, QASource
from app.services.dashscope_client import DashScopeClient
from app.services.session_metrics import session_metrics_store
from app.services.vector_store import VectorStore


logger = logging.getLogger(__name__)
token_logger = logging.getLogger("app.token")
llm_semaphore = asyncio.Semaphore(get_settings().max_llm_concurrency)


class RagService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.vector_store = VectorStore()
        self.client = DashScopeClient()

    async def stream_answer(self, question: str, session_id: str | None, db: AsyncSession) -> AsyncGenerator[dict, None]:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        if self._should_block(question):
            refusal = "抱歉，这个请求不符合安全与合规要求，我不能提供帮助。"
            yield {"event": "sources", "data": []}
            yield {"event": "token", "data": refusal}
            await self._save_record(db, request_id, session_id, question, refusal, [], start)
            yield {"event": "meta", "data": {"request_id": request_id, "latency_ms": int((time.perf_counter() - start) * 1000)}}
            yield {"event": "done", "data": {"ok": True}}
            return

        retrieval_query = await self._rewrite_for_retrieval(question)
        embeddings, embedding_tokens = await self.client.embed_texts([retrieval_query])
        query_embedding = embeddings[0]
        hits = self.vector_store.search_hybrid(
            query_text=retrieval_query,
            query_embedding=query_embedding,
            top_k=self.settings.retrieve_top_k,
            dense_candidate_k=self.settings.retrieve_top_k,
        )
        hits, rerank_tokens = await self._rerank_hits(
            query_embedding=query_embedding,
            hits=hits,
            final_top_k=self.settings.rerank_top_k,
        )
        if not hits:
            fallback = "我在知识库中没有检索到足够信息，请先补充相关文档后再试。"
            yield {"event": "sources", "data": []}
            yield {"event": "token", "data": fallback}
            await self._save_record(db, request_id, session_id, question, fallback, [], start)
            yield {"event": "meta", "data": {"request_id": request_id, "latency_ms": int((time.perf_counter() - start) * 1000)}}
            yield {"event": "done", "data": {"ok": True}}
            return

        context = "\n\n".join([f"[{idx + 1}] {item['content']}" for idx, item in enumerate(hits)])
        history_messages = await self._load_session_history(db=db, session_id=session_id)
        system_prompt = (
            "You are a customer support assistant. Answer based on provided context and recent conversation history. "
            "Refuse illegal, unsafe, or unrelated requests."
        )
        user_prompt = f"Context:\n{context}\n\nQuestion:\n{question}"
        messages = [{"role": "system", "content": system_prompt}, *history_messages, {"role": "user", "content": user_prompt}]

        yield {"event": "sources", "data": hits}

        parts: list[str] = []
        usage_prompt_tokens = 0
        usage_completion_tokens = 0
        async with llm_semaphore:
            async for chunk in self.client.stream_chat(messages):
                token = chunk.get("token")
                usage = chunk.get("usage", {}) or {}
                usage_prompt_tokens = max(int(usage.get("prompt_tokens", 0)), usage_prompt_tokens)
                usage_completion_tokens = max(int(usage.get("completion_tokens", 0)), usage_completion_tokens)
                if token:
                    parts.append(token)
                    yield {"event": "token", "data": token}

        answer = "".join(parts).strip()
        latency_ms = await self._save_record(db, request_id, session_id, question, answer, hits, start)
        prompt_tokens = usage_prompt_tokens or (len(user_prompt) // 4)
        completion_tokens = usage_completion_tokens or (len(answer) // 4)

        session_metrics_store.add_usage(
            session_id=session_id,
            embedding_tokens=embedding_tokens,
            rerank_tokens=rerank_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        logger.info(
            "chat_completed",
            extra={
                "extra_data": {
                    "request_id": request_id,
                    "session_id": session_id,
                    "latency_ms": latency_ms,
                    "hit_count": len(hits),
                    "score_min": min([h.get("score", 0.0) for h in hits], default=0.0),
                    "score_max": max([h.get("score", 0.0) for h in hits], default=0.0),
                }
            },
        )
        token_logger.info(
            "token_usage",
            extra={
                "extra_data": {
                    "request_id": request_id,
                    "session_id": session_id,
                    "embedding_tokens": embedding_tokens,
                    "rerank_tokens": rerank_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": embedding_tokens + rerank_tokens + prompt_tokens + completion_tokens,
                }
            },
        )
        yield {
            "event": "meta",
            "data": {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "embedding_tokens": embedding_tokens,
                "rerank_tokens": rerank_tokens,
                "total_tokens": embedding_tokens + rerank_tokens + prompt_tokens + completion_tokens,
            },
        }
        yield {"event": "done", "data": {"ok": True}}

    async def _rewrite_for_retrieval(self, question: str) -> str:
        if not self.settings.enable_query_rewrite:
            return question
        try:
            rewritten = await self.client.rewrite_query(question)
            return rewritten if rewritten.strip() else question
        except Exception:
            logger.warning("query_rewrite_failed", extra={"extra_data": {"reason": "fallback_to_original"}})
            return question

    async def _save_record(
        self,
        db: AsyncSession,
        request_id: str,
        session_id: str | None,
        question: str,
        answer: str,
        hits: list[dict],
        start: float,
    ) -> int:
        latency_ms = int((time.perf_counter() - start) * 1000)
        qa_record = QARecord(
            request_id=request_id,
            session_id=session_id,
            question=question,
            answer=answer,
            latency_ms=latency_ms,
            prompt_tokens=len(question) // 4,
            completion_tokens=len(answer) // 4,
        )
        db.add(qa_record)
        await db.flush()
        for hit in hits:
            db.add(
                QASource(
                    qa_record_id=qa_record.id,
                    file_id=str(hit.get("metadata", {}).get("file_id", "")),
                    chunk_index=int(hit.get("metadata", {}).get("chunk_index", 0)),
                    score=float(hit.get("score", 0.0)),
                    snippet=hit.get("content", ""),
                )
            )
        await db.commit()
        return latency_ms

    def _should_block(self, question: str) -> bool:
        risky_keywords = ["绕过", "越狱", "破解", "恶意代码", "违规", "色情", "暴力", "赌博"]
        q = question.lower()
        return any(token in q for token in risky_keywords)

    async def _load_session_history(self, db: AsyncSession, session_id: str | None) -> list[dict]:
        if not session_id:
            return []
        stmt = (
            select(QARecord)
            .where(QARecord.session_id == session_id)
            .order_by(desc(QARecord.created_at))
            .limit(self.settings.conversation_history_turns)
        )
        rows = (await db.execute(stmt)).scalars().all()
        history = list(reversed(rows))
        messages: list[dict] = []
        for row in history:
            if row.question:
                messages.append({"role": "user", "content": row.question})
            if row.answer:
                messages.append({"role": "assistant", "content": row.answer})
        return messages

    async def _rerank_hits(self, query_embedding: list[float], hits: list[dict], final_top_k: int) -> tuple[list[dict], int]:
        if not hits:
            return [], 0
        candidates = hits[: max(final_top_k, self.settings.top_k)]
        candidate_docs = [item.get("content", "")[: self.settings.embedding_max_chunk_chars] for item in candidates]
        try:
            candidate_embeddings, rerank_tokens = await self.client.embed_texts(candidate_docs)
        except Exception:
            return candidates[:final_top_k], 0

        for idx, item in enumerate(candidates):
            rerank_score = self._cosine_similarity(query_embedding, candidate_embeddings[idx])
            item["rerank_score"] = rerank_score
            item["score"] = rerank_score
        reranked = sorted(candidates, key=lambda row: row.get("rerank_score", 0.0), reverse=True)[:final_top_k]
        return reranked, rerank_tokens

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=False))
        norm_left = math.sqrt(sum(a * a for a in left))
        norm_right = math.sqrt(sum(b * b for b in right))
        if norm_left <= 1e-12 or norm_right <= 1e-12:
            return 0.0
        return dot / (norm_left * norm_right)
