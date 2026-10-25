-- Distinguish statistical profiles for different files of one dataset version.
-- Existing UCI rows keep resource_key '' so their current cache identity still matches.
-- This does not change vector(384), dataset uniqueness, or research-query ownership.
-- Safe after 004_research_query_owner.sql. Idempotent for a second apply attempt.

ALTER TABLE dataset_profiles
ADD COLUMN IF NOT EXISTS resource_key TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN dataset_profiles.resource_key IS
    'Stable file identity and checksum. Empty string means the dataset has one native table, as UCI does.';

DO $$
DECLARE
    constraint_name text;
BEGIN
    -- Drop the pre-005 uniqueness that did not include resource_key.
    SELECT con.conname INTO constraint_name
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    WHERE rel.relname = 'dataset_profiles'
      AND con.contype = 'u'
      AND pg_get_constraintdef(con.oid) NOT LIKE '%resource_key%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE dataset_profiles DROP CONSTRAINT %I', constraint_name);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE rel.relname = 'dataset_profiles'
          AND con.conname = 'dataset_profiles_resource_version_key'
    ) THEN
        ALTER TABLE dataset_profiles
        ADD CONSTRAINT dataset_profiles_resource_version_key
        UNIQUE (dataset_id, resource_key, source_version, profiler_version);
    END IF;
END $$;
