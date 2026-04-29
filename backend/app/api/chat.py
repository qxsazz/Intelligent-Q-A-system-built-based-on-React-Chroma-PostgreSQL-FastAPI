import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.session import get_db
from app.schemas.chat import ChatRequest
from app.services.rag_service import RagService


router = APIRouter()
rag_service = RagService()


@router.post("/ask")
async def ask(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> EventSourceResponse:
    async def event_generator() -> AsyncGenerator[dict, None]:
        async for event in rag_service.stream_answer(req.question, req.session_id, db):
            yield {"event": event["event"], "data": json.dumps(event["data"], ensure_ascii=False)}

    return EventSourceResponse(event_generator())
