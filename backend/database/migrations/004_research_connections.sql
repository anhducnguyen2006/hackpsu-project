-- Additive, idempotent support for relationships between saved research questions.
-- Existing research history and dataset relationships are not modified.
CREATE TABLE IF NOT EXISTS research_connections (
    id BIGSERIAL PRIMARY KEY,
    research_a_id BIGINT NOT NULL
        REFERENCES research_queries(id) ON DELETE CASCADE,
    research_b_id BIGINT NOT NULL
        REFERENCES research_queries(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL CHECK (
        relationship_type IN ('SEMANTIC_SIMILARITY', 'SHARED_DATASET')
    ),
    similarity_score DOUBLE PRECISION,
    shared_dataset_count INTEGER NOT NULL DEFAULT 0 CHECK (shared_dataset_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT research_connections_ordered_pair CHECK (research_a_id < research_b_id),
    CONSTRAINT research_connections_unique_edge
        UNIQUE (research_a_id, research_b_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_research_connections_research_a
    ON research_connections(research_a_id);

CREATE INDEX IF NOT EXISTS idx_research_connections_research_b
    ON research_connections(research_b_id);
