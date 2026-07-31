ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS display_name text,
    ADD COLUMN IF NOT EXISTS logo_url text,
    ADD COLUMN IF NOT EXISTS primary_color text NOT NULL DEFAULT '#0F766E',
    ADD COLUMN IF NOT EXISTS welcome_title text,
    ADD COLUMN IF NOT EXISTS welcome_message text;

UPDATE organizations
SET display_name = name
WHERE display_name IS NULL OR btrim(display_name) = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'organizations_primary_color_format'
    ) THEN
        ALTER TABLE organizations
            ADD CONSTRAINT organizations_primary_color_format
            CHECK (primary_color ~ '^#[0-9A-Fa-f]{6}$')
            NOT VALID;
    END IF;
END
$$;
