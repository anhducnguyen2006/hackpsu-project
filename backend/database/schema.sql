CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Research history
CREATE TABLE research_queries (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    embedding VECTOR(384),
    embedding_model TEXT,
    user_sub TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Unique dataset catalog
CREATE TABLE datasets (
    id BIGSERIAL PRIMARY KEY,
    repository TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT,
    description TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (repository, external_id)
);

-- 3. Search result relationships
CREATE TABLE query_dataset_matches (
    query_id BIGINT REFERENCES research_queries(id),
    dataset_id BIGINT REFERENCES datasets(id),
    rank INTEGER,
    relevance_score DOUBLE PRECISION,
    explanation TEXT,
    PRIMARY KEY (query_id, dataset_id)
);

-- 4. Relationships between saved research questions
CREATE TABLE research_connections (
    id BIGSERIAL PRIMARY KEY,
    research_a_id BIGINT NOT NULL REFERENCES research_queries(id) ON DELETE CASCADE,
    research_b_id BIGINT NOT NULL REFERENCES research_queries(id) ON DELETE CASCADE,
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

CREATE INDEX idx_research_connections_research_a
ON research_connections(research_a_id);

CREATE INDEX idx_research_connections_research_b
ON research_connections(research_b_id);

-- 5. Reusable statistical profiles
CREATE TABLE dataset_profiles (
    id BIGSERIAL PRIMARY KEY,
    dataset_id BIGINT REFERENCES datasets(id),
    source_version TEXT NOT NULL,
    profiler_version TEXT NOT NULL,
    resource_key TEXT NOT NULL DEFAULT '',
    profile JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT dataset_profiles_resource_version_key
        UNIQUE (dataset_id, resource_key, source_version, profiler_version)
);

-- 6. Question-specific assessments
CREATE TABLE research_assessments (
    id BIGSERIAL PRIMARY KEY,
    query_id BIGINT REFERENCES research_queries(id),
    dataset_id BIGINT REFERENCES datasets(id),
    profile_id BIGINT REFERENCES dataset_profiles(id),
    model TEXT NOT NULL,
    assessment_version TEXT NOT NULL,
    cache_key TEXT,
    assessment JSONB NOT NULL,
    suitability_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_queries_created
ON research_queries(created_at DESC);

CREATE INDEX idx_queries_owner_created
ON research_queries (user_sub, created_at DESC, id DESC)
WHERE user_sub IS NOT NULL;

CREATE INDEX idx_queries_embedding_model
ON research_queries(embedding_model)
WHERE embedding IS NOT NULL;

CREATE INDEX idx_queries_embedding_cosine
ON research_queries
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;

CREATE INDEX idx_assessments_query
ON research_assessments(query_id);

CREATE UNIQUE INDEX uq_assessments_cache_key
ON research_assessments(cache_key)
WHERE cache_key IS NOT NULL;
