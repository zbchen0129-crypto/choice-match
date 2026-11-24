CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE import_runs (
 id uuid PRIMARY KEY, dataset text NOT NULL, input_hash text NOT NULL,
 record_count integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE candidates (
 id text PRIMARY KEY, dataset text NOT NULL, domain text NOT NULL,
 name text NOT NULL, synthetic boolean NOT NULL, historical boolean NOT NULL,
 payload jsonb NOT NULL, import_id uuid REFERENCES import_runs(id)
);
CREATE INDEX candidates_dataset ON candidates(dataset);
CREATE TABLE rental_details (
 candidate_id text PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
 bedrooms numeric, cats_allowed boolean, monthly_lower_bound bigint NOT NULL CHECK(monthly_lower_bound>=0),
 costs_complete boolean NOT NULL
);
CREATE TABLE sources (
 candidate_id text REFERENCES candidates(id) ON DELETE CASCADE,
 source_id text NOT NULL, body text NOT NULL, source_date date NOT NULL,
 content_hash text NOT NULL, metadata jsonb NOT NULL,
 PRIMARY KEY(candidate_id,source_id)
);
CREATE TABLE chunks (
 id bigserial PRIMARY KEY, candidate_id text NOT NULL, source_id text NOT NULL,
 ordinal integer NOT NULL, start_offset integer NOT NULL, end_offset integer NOT NULL,
 body text NOT NULL, content_hash text NOT NULL,
 embedding vector(1536), embedding_model text,
 search_document tsvector GENERATED ALWAYS AS (to_tsvector('english',body)) STORED,
 FOREIGN KEY(candidate_id,source_id) REFERENCES sources(candidate_id,source_id) ON DELETE CASCADE,
 UNIQUE(candidate_id,source_id,ordinal)
);
CREATE INDEX chunks_search ON chunks USING gin(search_document);
CREATE INDEX chunks_candidate ON chunks(candidate_id);
-- Exact vector search is deliberate at this scale; avoids approximate-recall loss.
CREATE TABLE evidence (
 id text PRIMARY KEY, candidate_id text NOT NULL, source_id text NOT NULL,
 topic text NOT NULL, direction text NOT NULL CHECK(direction IN ('support','risk')),
 quote text NOT NULL, conditions text NOT NULL, source_hash text NOT NULL,
 extractor_version text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(candidate_id,source_id) REFERENCES sources(candidate_id,source_id) ON DELETE CASCADE
);
CREATE TABLE query_embeddings (
 cache_key text PRIMARY KEY, model text NOT NULL, query text NOT NULL,
 embedding vector(1536) NOT NULL
);
