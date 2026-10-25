-- Add an authenticated owner to research history.
-- Existing rows stay NULL. They are not assigned to anyone and stay invisible
-- to ordinary authenticated users. This migration does not rewrite embeddings,
-- primary keys, dataset identity, profiles, assessments, or foreign keys.

ALTER TABLE research_queries
ADD COLUMN IF NOT EXISTS user_sub TEXT;

COMMENT ON COLUMN research_queries.user_sub IS
    'Verified Auth0 subject (sub). NULL marks historical rows with no authenticated owner.';

CREATE INDEX IF NOT EXISTS idx_queries_owner_created
ON research_queries (user_sub, created_at DESC, id DESC)
WHERE user_sub IS NOT NULL;
