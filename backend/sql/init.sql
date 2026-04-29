CREATE TABLE IF NOT EXISTS tjk_files (
    id UUID PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'processed',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tjk_qa_records (
    id UUID PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(128),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tjk_qa_sources (
    id UUID PRIMARY KEY,
    qa_record_id UUID NOT NULL REFERENCES tjk_qa_records(id) ON DELETE CASCADE,
    file_id VARCHAR(64) NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    snippet TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tjk_qa_records_session_created_at
    ON tjk_qa_records(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tjk_files_created_at
    ON tjk_files(created_at DESC);
