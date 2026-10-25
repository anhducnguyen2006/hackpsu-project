-- Verify the existing vector column is compatible with the local embedding model.
-- This migration never drops or rewrites existing research history.
ALTER TABLE research_queries
ADD COLUMN IF NOT EXISTS embedding VECTOR(384);

ALTER TABLE research_queries
ADD COLUMN IF NOT EXISTS embedding_model TEXT;

DO $$
DECLARE
    embedding_type TEXT;
BEGIN
    SELECT format_type(attribute.atttypid, attribute.atttypmod)
    INTO embedding_type
    FROM pg_attribute AS attribute
    JOIN pg_class AS relation ON relation.oid = attribute.attrelid
    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE relation.relname = 'research_queries'
      AND namespace.nspname = current_schema()
      AND attribute.attname = 'embedding'
      AND NOT attribute.attisdropped;

    IF embedding_type <> 'vector(384)' THEN
        RAISE EXCEPTION
            'research_queries.embedding is %, expected vector(384); existing history was preserved and requires a manual migration',
            embedding_type;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_queries_embedding_model
ON research_queries(embedding_model)
WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_queries_embedding_cosine
ON research_queries
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
