import logging
import time
import uuid

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.kb import router as kb_router
from app.core.config import get_settings
from app.core.logging import configure_logging


settings = get_settings()
configure_logging(level=settings.log_level, reduce_noise=settings.reduce_noise_logs)
logger = logging.getLogger(__name__)
app = FastAPI(title="Intelligent CS Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(kb_router, prefix="/kb", tags=["knowledge-base"])
app.include_router(history_router, prefix="/history", tags=["history"])


@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "request_completed",
        extra={
            "extra_data": {
                "request_id": request_id,
                "latency_ms": latency_ms,
            }
        },
    )
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
