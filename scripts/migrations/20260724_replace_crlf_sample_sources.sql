\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM knowledge_chunks
        WHERE knowledge_base_id = 'platform'
          AND source_id IN (
              'src-d0ddef69082afff0',
              'src-fc5c92d441c484ab',
              'src-ecc35d05aefe91f2'
          )
    ) THEN
        RAISE EXCEPTION
            'normalized sample sources already exist; refusing to create duplicates';
    END IF;
END
$$;

DELETE FROM knowledge_chunks
WHERE knowledge_base_id = 'platform'
  AND source_id IN (
      'src-16ac57b71ab9cda7',
      'src-142e699586615cec',
      'src-fd002f96fab7aea6'
  );

COMMIT;
