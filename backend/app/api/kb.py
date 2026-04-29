import uuid
from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.db_models import FileRecord
from app.services.ingest_service import IngestService
from app.services.vector_store import VectorStore


router = APIRouter()
ingest_service = IngestService()
vector_store = VectorStore()
settings = get_settings()


@router.post("/upload")
async def upload_file(file: UploadFile, db: AsyncSession = Depends(get_db)) -> dict:
    record = await ingest_service.save_and_ingest(file, db)
    return {
        "id": str(record.id),
        "file_name": record.file_name,
        "chunk_count": record.chunk_count,
        "status": record.status,
    }


@router.get("/list")
async def list_files(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(FileRecord).order_by(FileRecord.created_at.desc()))
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "file_name": row.file_name,
            "file_size": row.file_size,
            "status": row.status,
            "chunk_count": row.chunk_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.delete("/{file_id}")
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    file_uuid = uuid.UUID(file_id)
    result = await db.execute(select(FileRecord).where(FileRecord.id == file_uuid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="file not found")

    vector_store.delete_by_file_id(file_id=file_id)
    await db.execute(delete(FileRecord).where(FileRecord.id == file_uuid))
    await db.commit()
    return {"ok": True}


@router.get("/file/{file_id}")
async def get_source_file(file_id: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    file_uuid = uuid.UUID(file_id)
    result = await db.execute(select(FileRecord).where(FileRecord.id == file_uuid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="file not found")

    upload_dir = Path(settings.upload_dir)
    matches = list(upload_dir.glob(f"{file_id}_*"))
    if not matches:
        raise HTTPException(status_code=404, detail="source file missing on disk")

    source_path = matches[0]
    media_type = None
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        media_type = "application/pdf"
    elif suffix == ".txt":
        media_type = "text/plain; charset=utf-8"
    elif suffix == ".md":
        media_type = "text/markdown; charset=utf-8"
    elif suffix == ".csv":
        media_type = "text/csv; charset=utf-8"
    elif suffix == ".xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return FileResponse(path=source_path, media_type=media_type, filename=row.file_name)


@router.get("/file/{file_id}/preview")
async def preview_source_file(
    file_id: str,
    chunk_index: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    file_uuid = uuid.UUID(file_id)
    result = await db.execute(select(FileRecord).where(FileRecord.id == file_uuid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="file not found")

    upload_dir = Path(settings.upload_dir)
    matches = list(upload_dir.glob(f"{file_id}_*"))
    if not matches:
        raise HTTPException(status_code=404, detail="source file missing on disk")

    source_path = matches[0]
    suffix = source_path.suffix.lower()
    snippet = ""
    if chunk_index is not None:
        chunk = vector_store.get_chunk(file_id=file_id, chunk_index=chunk_index)
        if chunk:
            snippet = chunk.get("content", "")

    escaped_name = escape(row.file_name)
    escaped_snippet = escape(snippet or "未找到对应召回片段。")
    escaped_chunk = escape(str(chunk_index) if chunk_index is not None else "-")

    html = f"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>召回片段预览 - {escaped_name}</title>
    <style>
      body {{ font-family: "Segoe UI", Arial, sans-serif; background:#f8fafc; color:#111827; margin:0; }}
      .wrap {{ max-width:1100px; margin:0 auto; padding:16px; }}
      .card {{ background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px; margin-bottom:12px; }}
      .meta {{ color:#6b7280; font-size:13px; margin-bottom:8px; }}
      .snippet {{ white-space:pre-wrap; background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:12px; line-height:1.6; }}
      h2 {{ margin:0 0 8px 0; }}
      h3 {{ margin:0 0 8px 0; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h2>召回片段截图视图</h2>
        <div class="meta">文件：{escaped_name} | chunk_index: {escaped_chunk}</div>
        <div class="snippet">{escaped_snippet}</div>
      </div>
    </div>
  </body>
</html>
"""
    return HTMLResponse(content=html)
