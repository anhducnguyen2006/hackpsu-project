CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Research history
CREATE TABLE research_queries (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    embedding VECTOR(384),
    embedding_model TEXT,
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

-- 4. Reusable statistical profiles
CREATE TABLE dataset_profiles (
    id BIGSERIAL PRIMARY KEY,
    dataset_id BIGINT REFERENCES datasets(id),
    source_version TEXT NOT NULL,
    profiler_version TEXT NOT NULL,
    profile JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(dataset_id, source_version, profiler_version)
);

-- 5. Question-specific assessments
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

CREATE INDEX idx_assessments_query
ON research_assessments(query_id);

CREATE UNIQUE INDEX uq_assessments_cache_key
ON research_assessments(cache_key)
WHERE cache_key IS NOT NULL;
