-- Database schema for the application (PostgreSQL)
-- Generated from SQLModel classes
-- Note: Tables are auto-created by the ORM on startup.
--       Run this script manually only if needed.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- Application tables
-- ============================================================

-- Users
CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Chat sessions
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- LangGraph threads (checkpointing)
CREATE TABLE IF NOT EXISTS thread (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- LangGraph AsyncPostgresSaver checkpoint tables
-- These are auto-created by langgraph-checkpoint-postgres,
-- listed here for reference and manual setup.
-- ============================================================

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_path TEXT NOT NULL DEFAULT '',
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- ============================================================
-- mem0 long-term memory tables (pgvector)
-- These are auto-created by mem0 on first use,
-- listed here for faster startup and manual setup.
-- ============================================================

CREATE TABLE IF NOT EXISTS langchain_pg_collection (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    cmetadata JSONB
);

CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
    id VARCHAR(255) PRIMARY KEY,
    collection_id UUID REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector(1536),
    document TEXT,
    cmetadata JSONB
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);
CREATE INDEX IF NOT EXISTS idx_session_user_id ON session(user_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_embedding_collection ON langchain_pg_embedding(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_name ON langchain_pg_collection(name);

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_embedding_vector ON langchain_pg_embedding
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
