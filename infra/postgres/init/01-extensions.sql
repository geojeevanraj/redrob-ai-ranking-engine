-- Runs automatically on first DB container start (docker-entrypoint-initdb.d).
-- Enables the pgvector extension so future sprints can store embeddings.
-- NOTE: No business tables are created here — schema is owned by Alembic.

CREATE EXTENSION IF NOT EXISTS vector;
