#!/usr/bin/env sh
set -eu

dimensions="${RUNBOOKIQ_EMBEDDING_DIMENSIONS:-768}"
case "$dimensions" in
  ''|*[!0-9]*)
    echo "RUNBOOKIQ_EMBEDDING_DIMENSIONS must be a positive integer" >&2
    exit 1
    ;;
esac
if [ "$dimensions" -lt 1 ] || [ "$dimensions" -gt 2000 ]; then
  echo "RUNBOOKIQ_EMBEDDING_DIMENSIONS must be between 1 and 2000 for this HNSW index" >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id text PRIMARY KEY,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO knowledge_bases (id, name, description)
VALUES (
    'platform',
    '平台工程知识库',
    'Kubernetes、运行手册与事故复盘'
)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id text NOT NULL,
    knowledge_base_id text NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    title text NOT NULL,
    section_path text NOT NULL,
    content text NOT NULL,
    parent_content text,
    source_url text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(${dimensions}) NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', title || ' ' || section_path || ' ' || content)
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (knowledge_base_id, id)
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_kb_idx
    ON knowledge_chunks (knowledge_base_id);
CREATE INDEX IF NOT EXISTS knowledge_chunks_source_idx
    ON knowledge_chunks (knowledge_base_id, source_id);
CREATE INDEX IF NOT EXISTS knowledge_chunks_fts_idx
    ON knowledge_chunks USING gin (search_vector);
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
SQL
