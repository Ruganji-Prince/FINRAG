# Deployment and reproduction

The locally verified database path is native PostgreSQL 16.15 with pgvector 0.8.6 on Windows, not a Docker container. Docker and WSL are absent. Compose was checked against the official schema and the pinned image tag was verified in Docker Registry; these checks do not establish successful container execution. See `docs/postgres.md` for exact installation, roles, migration and runtime commands.

The optional `app` Compose profile includes schema migration, API and frontend services. The default database service remains independently runnable. On a Docker-capable host:

```powershell
docker compose up -d db
docker compose --profile app up --build -d
# Seed the already-migrated database through the writer profile:
docker compose --profile app run --rm migrate python -m pipelines.snapshot restore data/prebuilt-semantic-index.json
```

The `migrate` service initializes schema using the writer role. API credentials have only reader privileges and automatic DDL is disabled. The image installs the pinned semantic CPU dependencies by default; build with `INSTALL_SEMANTIC=false` for a lightweight image. The local-model/embedding cache is a persistent volume. The frontend reaches `http://api:8000` internally. Published ports bind to loopback. The Compose templates interpolate passwords into database URLs, so use URL-safe generated password values. For passwords containing URL-reserved characters, supply separately encoded service database URLs without changing the raw database password.

The `.dockerignore` excludes `.env*`, `.runtime`, model caches, raw/review PDFs and local backups. The image runs as an unprivileged user. Database passwords belong in local/container secret management. The private native profile is not an image asset. Cloud credentials are optional and have not been live-tested unless final verification explicitly says otherwise.

For the tested native setup, run `python scripts/native_postgres.py start`, then `python scripts/configure_native.py`, then `python scripts/start.py`. The configuration helper preserves any locally configured cloud key. It otherwise selects the local provider. The Python launcher avoids changing Windows PowerShell execution policy. Use project virtual-environment Python for all commands.

The full local model requires several GB of download/storage and memory; initial startup is slower than warmed inference. Downloads are pinned to immutable revisions. A bounded resumable range downloader verifies the large model artifact against the publisher LFS SHA256 when ordinary downloads stall. Optional model dependencies are pinned in `requirements-embeddings.txt`. The CPU-only build avoids paid API requirements, but local hardware/energy costs are not included in API fee figures.

The existing lightweight SQLite mode remains available. The original two-report snapshot is unchanged. `data/prebuilt-index-v2.json` provides a separate 15-report lexical index; `data/prebuilt-semantic-index.json` contains real semantic vectors with the pinned model identity. Restore into a matching model configuration. Never relabel hash vectors as semantic vectors.

Source refresh is operator-triggered via `python -m pipelines.ingest data/manifest.json` under the writer profile. Failures preserve prior data and audit history. No scheduled scraping is enabled. NISR reuse follows its published terms and per-document review; BNR candidates awaiting rights clarification are not silently indexed or redistributed.

Affordable hosting requires a service with sufficient memory for the chosen model, a persistent pgvector database and separate API/frontend processes. Provider plans and deployment URLs have not been verified; no public deployment is claimed. Before public use, add authentication, TLS, PDF process isolation, distributed request limits, protected secrets, monitoring, backup/restore procedures and storage outside a synchronized Box directory. The native cluster inside the project is a development fallback, not a production storage recommendation.

Live browser checks use `requirements-browser.txt` and Edge (or `python -m playwright install chromium`). Start the real services, run `python scripts/browser_smoke.py`, and inspect saved screenshots. A passing browser script is not accessibility certification or a load test.

## Final container and public-demo controls

The final Compose file additionally configures memory/CPU/PID limits and health checks for the database, API and Streamlit. API public mode and server-side shared-token forwarding are configurable. Container runtime verification remains unperformed because this machine has neither Docker nor WSL. Run on a Docker-capable host with at least the configured memory budget:

```powershell
docker compose config --quiet
docker compose up -d db
docker compose --profile app up --build -d
docker compose --profile app run --rm migrate python -m pipelines.snapshot restore data/prebuilt-semantic-index-v3.json
docker compose ps
curl.exe --fail http://127.0.0.1:8000/health
```

Generate unique URL-safe admin/writer/reader passwords in a private `.env`; the placeholder passwords are not deployment credentials. For an authenticated API, also set `PUBLIC_MODE=true` and a unique `API_ACCESS_TOKEN` of at least 32 characters. Use the same token only on the server-side frontend, never in client JavaScript. Browser requests reach Streamlit; Streamlit adds the API authorization header. For direct API checks send `Authorization: Bearer TOKEN` from a secure client, without recording tokens in shared shell history.

Confirm anonymous data/docs calls return 401, authorized catalogue access succeeds, all three search modes return source pages, original-PDF refresh works through the writer, and a named-volume restart preserves document/hash/governance fingerprints. Review logs for model download errors and test actual local inference. Database/API ports remain loopback-only. Do not delete named volumes to troubleshoot initialization. The resource limits and startup health settings are configured values, not measured container capacity.

Public hosting is blocked pending account authorization, suitable resources and tested gateway/TLS controls. See [hosting assessment](hosting-assessment.md) for current provider constraints. No public endpoint, subscription, billing account or URL was created. The reliable verified demonstration remains local. Source-code licensing is an owner decision; data derivatives carry separate NISR attribution.
