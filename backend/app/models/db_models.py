import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "tjk_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="processed")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QARecord(Base):
    __tablename__ = "tjk_qa_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("idx_tjk_qa_records_created_at_desc", created_at.desc()),
        Index("idx_tjk_qa_records_session_created_at_desc", session_id, created_at.desc()),
        Index("idx_tjk_qa_records_session_created_at_id", session_id, created_at.desc(), id),
    )

    sources: Mapped[list["QASource"]] = relationship(back_populates="qa_record", cascade="all, delete-orphan")


class QASource(Base):
    __tablename__ = "tjk_qa_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qa_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tjk_qa_records.id", ondelete="CASCADE"))
    __table_args__ = (Index("idx_tjk_qa_sources_qa_record_id", qa_record_id),)
    file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)

    qa_record: Mapped[QARecord] = relationship(back_populates="sources")
