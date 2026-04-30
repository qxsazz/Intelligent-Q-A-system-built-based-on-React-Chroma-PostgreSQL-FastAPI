from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "intelligent-cs-agent"
    environment: str = "dev"
    log_level: str = "INFO"
    reduce_noise_logs: bool = True

    dashscope_api_key: str = ""
    dashscope_embedding_model: str = "text-embedding-v3"
    dashscope_llm_model: str = "qwen3.6-plus"
    dashscope_rerank_model: str = "bge-reranker-base"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_enable_thinking: bool = False
    enable_query_rewrite: bool = True
    query_rewrite_model: str = "qwen3.6-plus"
    query_rewrite_max_chars: int = 200

    pg_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_test"
    vector_persist_dir: str = "./data/chroma"
    vector_collection: str = "tjk_kb_docs"
    upload_dir: str = "./data/uploads"
    max_llm_concurrency: int = 5
    top_k: int = 5
    retrieve_top_k: int = 10
    rerank_top_k: int = 5
    enable_rerank: bool = True
    min_relevance_for_context: float = 0.6
    enable_balanced_retrieval: bool = True
    per_file_top_n: int = 2
    balanced_candidate_factor: int = 4
    hybrid_dense_weight: float = 0.6
    hybrid_bm25_weight: float = 0.4
    conversation_history_turns: int = 4
    chunk_size: int = 700
    chunk_overlap: int = 100
    embedding_batch_size: int = 8
    embedding_max_chunk_chars: int = 1800
    max_upload_mb: int = 120
    max_pdf_pages: int = 1200
    max_pdf_chars: int = 20_000_000
    max_chunks_per_file: int = 30000

    def ensure_dirs(self) -> None:
        Path(self.vector_persist_dir).mkdir(parents=True, exist_ok=True)
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
