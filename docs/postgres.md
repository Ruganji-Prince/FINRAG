# PostgreSQL operations and verified migration

The existing SQLite database and original index remain intact. A consistent pre-upgrade SQLite backup and source archive were created locally in `data/backups/` (ignored by Git). Original README documentation is preserved in `docs/history/README-mvp.md`. There was no `.git` directory or Git executable in the supplied workspace; no repository history was rewritten.

## Docker Compose (configured; not executed here)

Docker and WSL are absent from this Windows environment. The Compose definition uses `pgvector/pgvector:0.8.6-pg16`, persistent named storage, a loopback-only port, health checks and separate admin/writer/reader roles. Docker execution must still be verified on a Docker-capable machine.

Set `POSTGRES_PASSWORD`, `FINRAG_WRITER_PASSWORD`, and `FINRAG_READER_PASSWORD` in a private `.env`, then run `docker compose up -d db`. `POSTGRES_PASSWORD` belongs to `finrag_admin`; the ingestion account `finrag` is not a superuser. Set the writer DATABASE_URL to `postgresql://finrag:WRITER_PASSWORD@localhost:5432/finrag` for operator commands. Query-serving should receive only `postgresql://finrag_reader:READER_PASSWORD@localhost:5432/finrag`, with `AUTO_MIGRATE=false`. URL-encode reserved password characters.

The initialization script runs only on a new volume. Existing volumes need explicit administrative role grants/password rotation; never delete a volume to change credentials. Apply `python -m backend.migrate` with the writer account before starting the read-only API. Schema migrations use an advisory transaction lock, version records and file checksums. A changed already-applied migration fails closed. Upgrades preserve tables; automatic destructive downgrades are not provided. Back up before upgrades. SQL assets must retain their deployed line endings because checksums currently cover exact file bytes.

## Native Windows verification fallback (executed here)

A real PostgreSQL 16.15 / pgvector 0.8.6 cluster was installed under `.runtime/` from conda-forge, following the upstream pgvector conda installation option. It uses SCRAM passwords, loopback port 55432 and private generated writer/reader credentials. No Windows service was registered. The native package lock is `docs/native-postgres-win64.lock.txt`.

To reproduce on Windows, download standalone micromamba using its official installation instructions, then run:

```powershell
.runtime\micromamba.exe create --prefix .runtime\postgres --channel conda-forge postgresql=16.15 pgvector=0.8.6 --yes
.venv\Scripts\python.exe scripts/native_postgres.py start
```

Lifecycle commands: `python scripts/native_postgres.py status` or `stop`. Stopping affects only this project cluster. For production, use managed storage or Docker volumes; the project-local cluster inside a Box folder is a development convenience, not a production database storage design.

The private `.env.native-postgres` contains writer credentials for operator commands. `python scripts/configure_native.py` selects read-only PostgreSQL semantic serving in `.env` while preserving any configured cloud credentials. Without a cloud key it selects the real local model. The operator profile is never committed.

```powershell
python scripts/run_profile.py native -m backend.migrate
python scripts/run_profile.py native -m pipelines.migrate_sqlite --source data/finrag.db
python scripts/run_profile.py native -m pipelines.reembed
python scripts/run_profile.py native -m pipelines.ingest data/manifest.json
python scripts/run_checks.py --postgres --models
```

The SQLite transfer opens the source read-only, fingerprints its logical rows, copies documents/chunks/audit and any persisted governance records transactionally, verifies every original passage and page, and records the source-to-target document ID mapping. Repeating the same transfer is a no-op. Existing governance conflicts fail for manual reconciliation. Governance originally stored as project JSON is seeded into the database; it was not falsely counted as pre-existing SQLite rows.

Re-embedding computes vectors before publishing. A single transaction checks source/model consistency, changes only selected chunks/documents, and records an embedding-run lineage entry. It preserves original text, IDs, pages and PDF hashes. The model identifier includes the immutable Hugging Face revision. An interrupted vector computation leaves the old model searchable. Do not run competing ingestion/reindex maintenance jobs without scheduling them serially.

GIN indexes support English full-text search; HNSW supports cosine vectors. Metadata and document/page indexes cover filtering and evidence lookup. Small test corpora can legitimately use sequential scans even when indexes exist. The database-verification artifact records actual schema versions, dimensions and index names. Persistence was verified by stopping and restarting PostgreSQL with all 15 reports and 499 passages intact. The reader role was also denied writes after its default read-only transaction flag was disabled, proving actual privilege separation.

## Lightweight mode

Use `python scripts/run_profile.py sqlite -m pipelines.snapshot restore` and the original lightweight commands. This preserves the original two-report index and SQLite functionality. To serve SQLite while `.env` selects PostgreSQL, launch both backend and frontend through an explicit SQLite profile, or set `.env` values from `.env.example`. No paid API or semantic model is required in this mode.

Prebuilt snapshots omit raw PDF files. A subsequent real ingestion refresh now restores missing/corrupt cached PDFs and their paths without duplicating indexed documents or passages. This is necessary before original-PDF hash/page/anchor verification on a fresh snapshot installation.
