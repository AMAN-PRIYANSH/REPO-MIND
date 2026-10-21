-- CP4: code chunks and their embeddings (ADR-007). One row per (chunk, chunk variant,
-- embedding model). The vector column has no fixed dimension so two embedding models can
-- share the table; every search filters on embedding_model, so distances are only ever
-- computed between vectors of one model (and one dimension).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vt_schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS {table} (
    chunk_id        text NOT NULL,
    variant         text NOT NULL,
    embedding_model text NOT NULL,
    range_key       text NOT NULL,
    module          text NOT NULL DEFAULT '',
    version         text NOT NULL DEFAULT '',
    package         text NOT NULL DEFAULT '',
    symbol          text NOT NULL DEFAULT '',
    candidate_id    text NOT NULL DEFAULT '',
    content_sha256  text NOT NULL DEFAULT '',
    embedding       vector NOT NULL,
    PRIMARY KEY (chunk_id, variant, embedding_model)
);

CREATE INDEX IF NOT EXISTS {table}_scope_idx ON {table} (embedding_model, variant, range_key);
