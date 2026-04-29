from dataclasses import dataclass


@dataclass
class SessionTokenStats:
    request_count: int = 0
    embedding_tokens: int = 0
    rerank_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.embedding_tokens + self.rerank_tokens + self.prompt_tokens + self.completion_tokens


class SessionMetricsStore:
    def __init__(self) -> None:
        self._stats: dict[str, SessionTokenStats] = {}

    def add_usage(
        self,
        session_id: str | None,
        embedding_tokens: int,
        rerank_tokens: int,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        if not session_id:
            return
        current = self._stats.get(session_id, SessionTokenStats())
        current.request_count += 1
        current.embedding_tokens += max(embedding_tokens, 0)
        current.rerank_tokens += max(rerank_tokens, 0)
        current.prompt_tokens += max(prompt_tokens, 0)
        current.completion_tokens += max(completion_tokens, 0)
        self._stats[session_id] = current

    def pop(self, session_id: str) -> SessionTokenStats:
        return self._stats.pop(session_id, SessionTokenStats())


session_metrics_store = SessionMetricsStore()
