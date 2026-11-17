# Implementation and verification report

FinRAG was extended in place. The original source/SQLite backup and historical README were preserved. No Git history was rewritten; no Git metadata was present in the supplied folder.

| Area | Actual status |
|---|---|
| PostgreSQL/pgvector | Native PostgreSQL 16.15 / pgvector 0.8.6 tested, including restart persistence and reader privileges |
| SQLite transfer | Metadata, original 75 passages and audit copied and checked; repeated transfer made no changes |
| Schema/governance | Transactional versioned migrations, indexes, persistent registries and archived prior governance payloads |
| Semantic retrieval | Pinned real 384-dimensional vectors; keyword/vector/hybrid measured on the same 52 questions |
| Actual LLM RAG | Full-precision local model passed factual calibration and HTTP/UI checks; exact source/citation validation |
| Corpus | @DOCS@ official NISR reports, @PASSAGES@ passages; BNR sources pending rights review |
| Full automated suite | @TESTS@ tests, @FAILURES@ failures, @SKIPPED@ skipped |
| Generated-answer evaluation | @RAG_STATE@ |
| Docker/cloud/deployment | Container execution, live cloud calls/billing and public deployment explicitly unverified |

## Measured retrieval

| Configuration | Page Recall@5 | MRR@5 |
|---|---:|---:|
@RETRIEVAL@

Keyword ranking had the strongest MRR on this small, largely report-filtered development benchmark. No hybrid improvement is claimed. Reference pages/anchors were verified against original PDF bytes. Independent human relevance adjudication is pending.

## Actual generated-answer evaluation

The balanced run covers 32 questions: 24 factual, four unsupported and four cross-report/revision-sensitive cases. Actual status: @RAG_STATE@.

- Quote/citation integrity: @INTEGRITY@.
- Exact-source extractive claim support: @SUPPORT@.
- Unsupported abstention: @ABSTENTION@.
- Positive-question abstention: @POS_ABSTENTION@.
- Expected-anchor coverage diagnostic: @ANCHORS@.
- Mean server-reported response latency: @LATENCY@ ms.
- Estimated cloud API fee: @COST@ USD. Local hardware/energy are not priced.

These are not independently human-verified financial-answer accuracy scores. Exact quotation support does not prove relevance or completeness. All observed anchor/abstention diagnostics are saved in `evaluation/results/failure-cases.json`. Earlier smaller-model, context and int8 trial failures are retained and documented rather than promoted as successes.

## Remaining work

Docker execution requires a Docker-capable host. Live Gemini/OpenAI verification and billing require locally configured credentials and a new run. BNR rights need review before inclusion. Independent human/held-out evaluation, semantic entailment assessment, production authentication/TLS, PDF process isolation, monitoring and load testing remain incomplete. A native database inside Box is a development fallback, not production storage.

Reproduction: README.md, docs/postgres.md and docs/evaluation.md. Machine-readable status: docs/final-report.json. Actual HTTP, browser, database, refresh, model-artifact and evaluation evidence is saved under evaluation/results and docs/screenshots.
