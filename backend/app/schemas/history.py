from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HistoryListItem(BaseModel):
    id: UUID
    request_id: str
    session_id: str | None
    question: str
    created_at: datetime


class HistorySourceItem(BaseModel):
    file_id: str
    chunk_index: int
    score: float
    snippet: str


class HistoryDetail(BaseModel):
    id: UUID
    request_id: str
    session_id: str | None
    question: str
    answer: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime
    sources: list[HistorySourceItem]


class SessionTurnItem(BaseModel):
    id: UUID
    question: str
    answer: str
    created_at: datetime
