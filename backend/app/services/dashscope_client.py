import json
from collections.abc import AsyncGenerator

import httpx

from app.core.config import get_settings


class DashScopeClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.headers = {"Authorization": f"Bearer {self.settings.dashscope_api_key}"}

    async def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], int]:
        url = f"{self.settings.dashscope_base_url}/embeddings"
        body = {"model": self.settings.dashscope_embedding_model, "input": texts}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=self.headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]
        usage = data.get("usage", {})
        token_count = int(usage.get("total_tokens", 0))
        return embeddings, token_count

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[dict, None]:
        url = f"{self.settings.dashscope_base_url}/chat/completions"
        body = {
            "model": self.settings.dashscope_llm_model,
            "messages": messages,
            "stream": True,
            "enable_thinking": self.settings.dashscope_enable_thinking,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, headers=self.headers, json=body) as resp:
                resp.raise_for_status()
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    content = line[5:].strip()
                    if content == "[DONE]":
                        break
                    payload = json.loads(content)
                    choices = payload.get("choices", [])
                    if not choices:
                        if payload.get("usage"):
                            yield {"token": None, "usage": payload.get("usage", {})}
                        continue
                    delta = choices[0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        yield {"token": token, "usage": payload.get("usage", {})}

    async def rewrite_query(self, question: str) -> str:
        if not question.strip():
            return question
        url = f"{self.settings.dashscope_base_url}/chat/completions"
        model = self.settings.query_rewrite_model or self.settings.dashscope_llm_model
        max_chars = max(self.settings.query_rewrite_max_chars, 50)
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You rewrite user questions for retrieval only. Keep original intent, add key entities, keep concise.",
                },
                {
                    "role": "user",
                    "content": f"Rewrite for retrieval in Chinese. Return one line only, <= {max_chars} chars.\nQuestion: {question}",
                },
            ],
            "stream": False,
            "temperature": 0.2,
            "enable_thinking": self.settings.dashscope_enable_thinking,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self.headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return question
        message = choices[0].get("message", {}) or {}
        content = (message.get("content", "") or "").strip()
        if not content:
            return question
        return content[:max_chars]

    async def rerank_texts(self, query: str, documents: list[str]) -> tuple[list[float], int]:
        if not query.strip() or not documents:
            return [], 0
        url = f"{self.settings.dashscope_base_url}/rerank"
        body = {
            "model": self.settings.dashscope_rerank_model,
            "query": query,
            "documents": documents,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=self.headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        output = data.get("output", {}) or {}
        results = output.get("results", []) or []
        scores = [0.0] * len(documents)
        for item in results:
            idx = int(item.get("index", -1))
            if 0 <= idx < len(scores):
                scores[idx] = float(item.get("relevance_score", 0.0))
        usage = data.get("usage", {}) or {}
        token_count = int(usage.get("total_tokens", usage.get("input_tokens", 0)) or 0)
        return scores, token_count
