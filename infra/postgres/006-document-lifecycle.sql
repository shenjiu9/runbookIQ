CREATE TABLE IF NOT EXISTS knowledge_documents (
    id text PRIMARY KEY,
    knowledge_base_id text NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    source_id text NOT NULL,
    filename text NOT NULL,
    content_type text NOT NULL DEFAULT 'application/octet-stream',
    size_bytes bigint NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    checksum text NOT NULL,
    storage_key text,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    status text NOT NULL DEFAULT 'ready' CHECK (status IN ('ready')),
    chunks_count integer NOT NULL DEFAULT 0 CHECK (chunks_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (knowledge_base_id, source_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS knowledge_documents_kb_id_uidx
    ON knowledge_documents (knowledge_base_id, id);

CREATE TABLE IF NOT EXISTS knowledge_document_object_gc (
    storage_key text PRIMARY KEY,
    queued_at timestamptz NOT NULL DEFAULT now(),
    delete_after timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE knowledge_document_object_gc
    ADD COLUMN IF NOT EXISTS delete_after timestamptz NOT NULL DEFAULT now();

CREATE OR REPLACE FUNCTION queue_deleted_knowledge_document_object()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.storage_key IS NOT NULL THEN
        INSERT INTO knowledge_document_object_gc (storage_key, delete_after)
        VALUES (OLD.storage_key, now())
        ON CONFLICT (storage_key) DO UPDATE
        SET delete_after = LEAST(
            knowledge_document_object_gc.delete_after,
            EXCLUDED.delete_after
        );
    END IF;
    RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS knowledge_documents_queue_object_gc ON knowledge_documents;
CREATE TRIGGER knowledge_documents_queue_object_gc
AFTER DELETE ON knowledge_documents
FOR EACH ROW
EXECUTE FUNCTION queue_deleted_knowledge_document_object();

CREATE TABLE IF NOT EXISTS knowledge_document_checksums (
    knowledge_base_id text NOT NULL,
    checksum text NOT NULL,
    document_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (knowledge_base_id, checksum),
    FOREIGN KEY (knowledge_base_id, document_id)
        REFERENCES knowledge_documents(knowledge_base_id, id) ON DELETE CASCADE
);

ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS document_id text;

INSERT INTO knowledge_documents (
    id, knowledge_base_id, source_id, filename, content_type, size_bytes,
    checksum, storage_key, version, status, chunks_count, created_at, updated_at
)
SELECT
    'doc-legacy-' || substr(md5(knowledge_base_id || ':' || source_id), 1, 20),
    knowledge_base_id,
    source_id,
    COALESCE(NULLIF(regexp_replace(min(source_url), '^upload://', ''), ''), min(title)),
    'application/octet-stream',
    0,
    md5(knowledge_base_id || ':' || source_id) || md5(source_id || ':' || knowledge_base_id),
    NULL,
    1,
    'ready',
    count(*)::integer,
    min(created_at),
    max(updated_at)
FROM knowledge_chunks
WHERE document_id IS NULL
GROUP BY knowledge_base_id, source_id
ON CONFLICT (knowledge_base_id, source_id) DO NOTHING;

UPDATE knowledge_chunks AS chunks
SET document_id = documents.id
FROM knowledge_documents AS documents
WHERE chunks.document_id IS NULL
  AND documents.knowledge_base_id = chunks.knowledge_base_id
  AND documents.source_id = chunks.source_id;

ALTER TABLE knowledge_chunks ALTER COLUMN document_id SET NOT NULL;

ALTER TABLE knowledge_chunks DROP CONSTRAINT IF EXISTS knowledge_chunks_document_fk;
ALTER TABLE knowledge_chunks
    ADD CONSTRAINT knowledge_chunks_document_fk
    FOREIGN KEY (knowledge_base_id, document_id)
    REFERENCES knowledge_documents(knowledge_base_id, id)
    ON DELETE CASCADE;

INSERT INTO knowledge_document_checksums (knowledge_base_id, checksum, document_id)
SELECT knowledge_base_id, checksum, id
FROM knowledge_documents
ON CONFLICT (knowledge_base_id, checksum) DO NOTHING;

CREATE INDEX IF NOT EXISTS knowledge_documents_kb_updated_idx
    ON knowledge_documents (knowledge_base_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_documents_checksum_idx
    ON knowledge_documents (knowledge_base_id, checksum);
CREATE INDEX IF NOT EXISTS knowledge_chunks_document_idx
    ON knowledge_chunks (document_id);
