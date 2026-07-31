CREATE TABLE IF NOT EXISTS organizations (
    id text PRIMARY KEY,
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    display_name text,
    logo_url text,
    primary_color text NOT NULL DEFAULT '#0F766E',
    welcome_title text,
    welcome_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id text PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_memberships (
    organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS tenant_domains (
    domain text PRIMARY KEY,
    organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tenant_domains_organization_idx
    ON tenant_domains (organization_id);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash text PRIMARY KEY,
    csrf_hash text NOT NULL,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS csrf_hash text;
DELETE FROM auth_sessions WHERE csrf_hash IS NULL;
ALTER TABLE auth_sessions ALTER COLUMN csrf_hash SET NOT NULL;

CREATE INDEX IF NOT EXISTS auth_sessions_user_idx
    ON auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry_idx
    ON auth_sessions (expires_at);

CREATE TABLE IF NOT EXISTS tenant_knowledge_bases (
    organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    knowledge_base_id text NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, knowledge_base_id),
    UNIQUE (knowledge_base_id)
);

CREATE INDEX IF NOT EXISTS tenant_knowledge_bases_organization_idx
    ON tenant_knowledge_bases (organization_id);
