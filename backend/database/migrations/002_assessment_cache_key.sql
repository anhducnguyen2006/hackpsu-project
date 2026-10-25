-- Add exact-input assessment caching without recreating or deleting data.
ALTER TABLE research_assessments
ADD COLUMN IF NOT EXISTS cache_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_assessments_cache_key
ON research_assessments(cache_key)
WHERE cache_key IS NOT NULL;
