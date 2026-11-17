CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
 id SERIAL PRIMARY KEY, title TEXT NOT NULL, organization TEXT NOT NULL,
 publication_date TEXT NOT NULL, source_url TEXT NOT NULL, document_type TEXT NOT NULL,
 landing_url TEXT NOT NULL, usage_notes TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
 retrieved_at TEXT NOT NULL, status TEXT NOT NULL, embedding_model TEXT NOT NULL,
 quality_json TEXT NOT NULL, path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (
 id SERIAL PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 page INTEGER NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL,
 embedding vector(384) NOT NULL, UNIQUE(document_id, content_hash));
CREATE TABLE IF NOT EXISTS audit (
 id SERIAL PRIMARY KEY, occurred_at TEXT NOT NULL, source_url TEXT NOT NULL,
 status TEXT NOT NULL, detail TEXT NOT NULL);
