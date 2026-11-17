CREATE TABLE IF NOT EXISTS governance_records (
 registry_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 recorded_at TEXT NOT NULL, owner TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS data_transfers (
 source_sha256 TEXT PRIMARY KEY, source_kind TEXT NOT NULL, completed_at TEXT NOT NULL,
 detail_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS embedding_runs (
 run_id TEXT PRIMARY KEY, model_id TEXT NOT NULL, started_at TEXT NOT NULL,
 completed_at TEXT, chunk_count INTEGER NOT NULL, status TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chunks_document_page ON chunks(document_id,page);
CREATE INDEX IF NOT EXISTS documents_filters ON documents(organization,document_type,publication_date);
CREATE INDEX IF NOT EXISTS documents_source ON documents(source_url);
CREATE INDEX IF NOT EXISTS audit_status_time ON audit(status,occurred_at);
