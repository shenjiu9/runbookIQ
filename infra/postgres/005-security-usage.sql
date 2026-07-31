CREATE TABLE IF NOT EXISTS security_usage_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bucket_key text NOT NULL,
    action text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS security_usage_events_bucket_created_idx
    ON security_usage_events (bucket_key, created_at DESC);

CREATE INDEX IF NOT EXISTS security_usage_events_created_idx
    ON security_usage_events (created_at);
