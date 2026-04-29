import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.db_models import QARecord
from app.schemas.history import HistoryDetail, HistoryListItem, HistorySourceItem, SessionTurnItem
from app.services.session_metrics import session_metrics_store


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list", response_model=list[HistoryListItem])
async def list_history(session_id: str | None = Query(default=None), db: AsyncSession = Depends(get_db)) -> list[HistoryListItem]:
    stmt = select(QARecord)
    if session_id:
        stmt = stmt.where(QARecord.session_id == session_id)
    result = await db.execute(stmt.order_by(QARecord.created_at.desc()).limit(100))
    rows = result.scalars().all()
    return [
        HistoryListItem(
            id=row.id,
            request_id=row.request_id,
            session_id=row.session_id,
            question=row.question,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/session/{session_id}", response_model=list[SessionTurnItem])
async def session_history(session_id: str, db: AsyncSession = Depends(get_db)) -> list[SessionTurnItem]:
    result = await db.execute(
        select(QARecord).where(QARecord.session_id == session_id).order_by(QARecord.created_at.asc()).limit(200)
    )
    rows = result.scalars().all()
    return [SessionTurnItem(id=row.id, question=row.question, answer=row.answer, created_at=row.created_at) for row in rows]


@router.get("/{record_id}", response_model=HistoryDetail)
async def history_detail(record_id: str, db: AsyncSession = Depends(get_db)) -> HistoryDetail:
    record_uuid = uuid.UUID(record_id)
    result = await db.execute(select(QARecord).options(selectinload(QARecord.sources)).where(QARecord.id == record_uuid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="history not found")
    return HistoryDetail(
        id=row.id,
        request_id=row.request_id,
        session_id=row.session_id,
        question=row.question,
        answer=row.answer,
        latency_ms=row.latency_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        created_at=row.created_at,
        sources=[
            HistorySourceItem(
                file_id=item.file_id,
                chunk_index=item.chunk_index,
                score=item.score,
                snippet=item.snippet,
            )
            for item in row.sources
        ],
    )


@router.delete("/{record_id}")
async def delete_history(record_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    record_uuid = uuid.UUID(record_id)
    await db.execute(delete(QARecord).where(QARecord.id == record_uuid))
    await db.commit()
    return {"ok": True}


@router.delete("/session/{session_id}")
async def clear_session_history(session_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    token_stats = session_metrics_store.pop(session_id)
    logger.info(
        "session_completed",
        extra={
            "extra_data": {
                "session_id": session_id,
                "request_count": token_stats.request_count,
                "embedding_tokens": token_stats.embedding_tokens,
                "rerank_tokens": token_stats.rerank_tokens,
                "prompt_tokens": token_stats.prompt_tokens,
                "completion_tokens": token_stats.completion_tokens,
                "total_tokens": token_stats.total_tokens,
            }
        },
    )
    await db.execute(delete(QARecord).where(QARecord.session_id == session_id))
    await db.commit()
    return {"ok": True}
