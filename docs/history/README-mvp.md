# FinRAG - Rwanda Financial Intelligence Assistant

An independent, evidence-first financial research portfolio project. FinRAG ingests official public PDFs, preserves page provenance, retrieves supporting passages, and exposes a FastAPI backend with a six-page Streamlit workspace. It is not affiliated with or endorsed by the National Bank of Rwanda (BNR) or the National Institute of Statistics of Rwanda (NISR).

**Working local MVP:** 2 official NISR reports, 75 indexed passages, a paid-API-free retrieval demonstration, document comparison, catalogue, data quality/audit dashboards, and reproducible evaluation. PostgreSQL/pgvector and configurable LLM adapters are implemented; their live infrastructure paths have not been verified in this environment. See [acceptance status](docs/acceptance.md) for the remaining scope.

## Why this project

Financial researchers need to find reported figures, check reference periods and distinguish source facts from interpretation. FinRAG demonstrates ingestion, validation, hybrid retrieval design, provenance, governance and transparent evaluation. It supports central-banking research and financial analysis without executing banking transactions or giving personalized investment instructions.

## Quick start

Python 3.14.2 was verified on Windows. In a terminal opened in this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Restore the licensed prebuilt index; no website or LLM API required.
.\.venv\Scripts\python.exe -m pipelines.snapshot restore
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

If `python` opens the Microsoft Store, use `C:\Python314\python.exe` for the first command on this machine. An environment and populated index have already been created in the supplied workspace. In a second terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open **http://127.0.0.1:8501**. API documentation: **http://127.0.0.1:8000/docs**. `python scripts/start.py` (using the project virtual environment) starts both processes in hidden windows and writes logs to `data/`. A PowerShell launcher is also provided, but this machine blocks script execution; the Python launcher works without changing that policy. Avoid starting duplicate processes on the same ports. On Linux/macOS, use `.venv/bin/python` in place of the Windows executable.

The default mode is SQLite, lexical hash vectors and **retrieval-only evidence**. It does not generate an LLM answer. Query examples: "What does the GDP report say about agriculture?" or select the 2025 annual report and ask about financial services. Reference year and publication year are different: the 2025 report was published in 2026. Chat retains a session transcript; follow-up questions are processed independently.

## Architecture

```mermaid
flowchart LR
    Sources[Curated official PDF URLs] --> ETL[Download, validate, hash, extract by page]
    ETL --> Index[Chunk and embed]
    Index --> PG[(PostgreSQL: pgvector + full-text)]
    Index --> Demo[(SQLite: lexical demo)]
    UI[Streamlit] --> API[FastAPI]
    API --> Retrieve[Read-only hybrid retrieval + filters]
    PG --> Retrieve
    Demo --> Retrieve
    Retrieve --> Gate[Evidence and year gates]
    Gate --> Output[Linked passages or grounded LLM response]
```

Details: [architecture](docs/architecture.md), [governance registry](docs/governance.json), [deployment](docs/deployment.md).

## Official sources and corpus

Discovery sources: [BNR Publications](https://www.bnr.rw/Publications), [Monetary Policy](https://www.bnr.rw/MonetaryPolicy), [Financial Stability](https://www.bnr.rw/FinancialStability), and [NISR publications](https://statistics.gov.rw/statistical-publications).

The verified initial corpus contains NISR **GDP National Accounts 2025** and **GDP National Accounts Q2 2026**. Both PDFs state CC BY 4.0 on page 2. Their titles, source and landing URLs, publisher, publication date, retrieval timestamp, usage notes and original SHA256 hashes are preserved. Month-only publication dates use day 01 and explicitly identify that imputation. The prebuilt derived index includes attribution and the [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/). Raw PDFs are cached locally and ignored by Git. No confidential or customer data is used.

The corpus is deliberately smaller than the requested 15-30 reports. BNR reports, broader topics, source-license review and a larger independent benchmark remain work to complete; no broad financial coverage is claimed.

Re-download and ingest from the curated manifest:

```powershell
.\.venv\Scripts\python.exe -m pipelines.ingest data/manifest.json
```

The pipeline checks official HTTPS hosts, robots.txt, HTTP errors, download size and extraction quality. Redirects are refused. It paces downloads, preserves numeric text, rejects low-quality/scanned PDFs for OCR review, removes duplicate document/chunk hashes and writes an audit log. Document/chunk inserts are atomic. Failed refreshes never wipe the existing corpus. PDF is the supported MVP format. Table layouts are flattened; do not infer table-cell relationships without consulting the PDF.

## PostgreSQL and semantic retrieval

Copy `.env.example` to `.env` and set strong passwords, then:

```powershell
docker compose up -d db
```

Set these values in `.env` with your actual URL-encoded passwords:

```dotenv
DATABASE_URL=postgresql://finrag:YOUR_PASSWORD@localhost:5432/finrag
QUERY_DATABASE_URL=postgresql://finrag_reader:YOUR_READER_PASSWORD@localhost:5432/finrag
```

Run ingestion again or restore the hash snapshot into PostgreSQL. Tables, GIN full-text and HNSW vector indexes are initialized by ingestion. Queries use read-only transactions and the separate reader role. CI defines a disposable PostgreSQL integration test. Docker and PostgreSQL were not available locally, so successful PostgreSQL execution is not claimed.

For semantic vectors, install `requirements-embeddings.txt`, set `EMBEDDING_BACKEND=sentence-transformers`, and reingest into a **fresh database**. The optional package set is pinned but unverified here; Python 3.12 may be needed for torch wheel compatibility. All-MiniLM-L6-v2 uses 384 dimensions. Model identifiers prevent incompatible indexes being searched. The hash prebuilt index is usable only with `hash` mode. PostgreSQL combines vector and full-text ranking with reciprocal rank fusion; SQLite combines lexical overlap with hash-vector cosine and loads the small corpus into memory.

## Optional LLM generation

Defaults require no API key. For generation set `LLM_PROVIDER=openai` or `gemini`, `LLM_API_KEY` and a compatible `LLM_MODEL` in `.env`. Keep `.env` private. Provider adapters use the official chat-completions / generateContent APIs, treat retrieved passages as untrusted data, request structured responses and validate citation identifiers. Missing keys, provider failures and invalid citations produce explicit abstention with reviewable evidence. Live provider calls are not verified; mocked tests cover invalid reference handling. Citation checks do not establish claim faithfulness.

Set optional input/output prices per million tokens to estimate cost; prices are operator inputs, not live pricing. Current/latest conditions abstain because the static corpus is incomplete. Retrieval gates are conservative heuristics and can both miss paraphrases and admit partially relevant evidence.

## Application and API

The UI provides Home, AI Research Assistant, Compare Reports, Document Library, Data Quality and Evaluation. Comparisons retrieve each selected report independently, display linked evidence and warn about differing periods. There is no automatic causal interpretation across annual and quarterly figures.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Runtime mode |
| `POST /ask` | Evidence or configured grounded answer |
| `POST /search` | Ranked, filterable passages |
| `POST /compare` | Two-report evidence comparison |
| `GET /documents` | Provenance catalogue |
| `GET /quality` | Counts, extraction checks and audit |
| `GET /governance` | Rules, registry, catalogue and lineage |
| `GET /evaluation` | Last saved measured run |

```json
{"question":"What does the GDP report say about agriculture?","k":5,"filters":{"organization":"NISR","document_id":1}}
```

Automatic OpenAPI includes bounded input schemas and structured evidence/answer responses. Questions are not persisted. The localhost API uses per-process rate limits and generic error responses. Add authentication, TLS, PDF isolation, distributed quotas and operational controls before public exposure.

## Tests and measured evaluation

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluation/results/tests.xml
.\.venv\Scripts\python.exe -m evaluation.run
```

The latest local suite passed **38 tests**, with **1 PostgreSQL integration test skipped** because no service was configured. One upstream Starlette/httpx deprecation warning remains. Tests cover parsing, malformed/scanned PDFs, metadata, unsafe URLs, chunking, duplicates, audit, read-only storage, retrieval, filters, citations, unsupported questions, provider failures, API responses, rate limits, frontend rendering and offline snapshot restoration. Temporary fixtures are synthetic and isolated from the official corpus.

The 40-case development benchmark uses authored official-PDF page labels; independent human verification is pending. Its measured latest run in SQLite/hash/no-LLM mode:

| Metric | Measured result |
|---|---:|
| Page Recall@5 | 0.96875 |
| MRR@5 | 0.93750 |
| Citation referential integrity | 1.00000 |
| Unsupported abstention (8 cases) | 1.00000 |
| Human-verified answer accuracy | Not measured |
| LLM answer faithfulness | Not measured |

Latency, corpus/dataset hashes, model identity and per-case diagnostics are in [saved results](evaluation/results/latest.json). These small-corpus retrieval scores are not evidence of general financial-answer accuracy. Earlier failed runs remain in the results directory. The weak initial lexical gate admitted unsupported questions; tightening it improved abstention but missed a relevant deflator passage. Explicit-year validation also fixed a period-leakage test. See [evaluation methodology and limitations](docs/evaluation.md).

## Actual application screenshots

![Home dashboard](docs/screenshots/home.png)
![Research assistant with official source passages](docs/screenshots/assistant.png)

Additional actual screenshots: [comparison](docs/screenshots/comparison.png), [library](docs/screenshots/library.png), [quality](docs/screenshots/quality.png), [evaluation](docs/screenshots/evaluation.png). The [browser smoke script](scripts/browser_smoke.py) verifies the live UI/API connection and saves screenshots. See deployment documentation for optional browser dependencies.

## Repository and reproducibility

- `backend/`: settings, validated schemas, database, embeddings, retrieval and APIs.
- `pipelines/`: curated PDF ingestion and licensed snapshot export/restore.
- `app/`: Streamlit research workspace.
- `evaluation/`: benchmark, runner and actual saved results.
- `tests/`: deterministic fixtures and integration tests.
- `docs/`: architecture, governance, deployment, acceptance and screenshots.
- `.github/workflows/ci.yml`: Python tests plus a pgvector service; remote execution is unverified.

Core/runtime dependencies are pinned in `requirements.txt`; formatting tools, browser checks and semantic embeddings have separate pinned requirement files. The checked main dependency set was installed successfully in the local environment. The project has not been pushed to GitHub or publicly deployed; no deployment link is claimed. See [deployment instructions](docs/deployment.md) for Docker and affordable hosting approaches, subject to actual infrastructure limits.

## Limitations and next improvements

Expand curated BNR/NISR coverage to 15-30 reports, independently review benchmark labels, validate PostgreSQL/semantic/provider paths on provisioned infrastructure, add cross-report contradictions and held-out evaluation, isolate PDF processing, extract structured tables, and add reviewed OCR. Additional governance work includes model revision pinning, stewardship review and source-change monitoring. No synthetic data is presented as institutional evidence and no accuracy improvement is claimed beyond the saved development runs.
