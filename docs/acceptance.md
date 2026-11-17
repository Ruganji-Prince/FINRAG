# Rerun and review the final evidence

The final completion report is [FINAL_PROJECT_COMPLETION_REPORT.md](FINAL_PROJECT_COMPLETION_REPORT.md). Earlier 15-report reports remain under `history/`; development metrics are preserved and are not holdout scores.

Executed locally:

| Command/check | Actual result | Artifact |
|---|---|---|
| `python scripts/run_checks.py --postgres --models` | 72 passed, zero failed/skipped; repeated final run 16.60 s | `evaluation/results/final-tests.xml` |
| `python -m ruff check .` | Passed | Final verification log/report |
| `python -m pip check` | No broken requirements | Final verification log/report |
| `python -m pip_audit --format json --output evaluation/results/dependency-audit-upgraded.json` | Zero known vulnerability findings after upgrades | Audit JSON; initial findings retained separately |
| `python scripts/api_smoke.py` | Actual local LLM answer, unsupported refusal and two-source comparison passed; 30 documents/839 passages | `api-verification.json` |
| `python scripts/security_smoke.py` | Separate real HTTP process: anonymous data/docs requests 401, authenticated catalogue 200, oversized chunked body 413 | `security-http-verification.json` |
| `python scripts/browser_smoke.py` | All six pages, actual generated answer/source links, precise comparison and mobile viewport passed in Edge | `docs/screenshots/verification.json`, PNGs |
| `python -m evaluation.evaluate_rag --dataset evaluation/datasets/holdout-v1.json --output-name holdout-rag --api-url http://127.0.0.1:8000` | 30/30 completed; accuracy limits retained | `holdout-rag.json`, `holdout-failure-cases.json` |
| Holdout keyword/vector/hybrid comparison | Same 30 questions/filters, actual semantic retrieval | `holdout-retrieval.json` |
| Original PDF hash/page and incremental ingestion checks | 30 hashes/page counts verified; all unchanged documents skipped | `corpus-30-verification.json` |
| Native database stop/start and fingerprint comparison | See final 30-document persistence artifact | `persistence-30-verification.json` |
| Compose official schema validation | Passed; container runtime not executed | `compose-final-verification.json` |
| `python scripts/prepare_release.py` | Allowlisted ZIP and secret scan; rebuild after final documentation | `release/manifest.json`, `release/secret-scan.json` |

`python` above means the project `.venv` interpreter. Real PostgreSQL tests require a dedicated `_test` database. The local runner derives that URL from private native credentials; on another host supply `FINRAG_TEST_PG_URL`. `--models` enables actual semantic integration rather than silently counting a skipped model test as a pass. Do not run migration tests against production.

The first browser rerun failed because the enlarged Streamlit dropdown virtualized options; the smoke script now types a search term before selecting. The patched model-library calibration initially failed because Transformers changed chat-template return type; it was fixed with an explicit tensor return. Automatic lower-precision loading also caused slow CPU inference, so float32 is explicit. The successful actual calibration and later API/browser runs verify the final behavior. No test expectation was weakened to hide a failure.

Docker engine/container tests, live commercial-provider inference/billing, external hosting, remote GitHub workflows, human answer adjudication and production concurrency/security exercises were not executed. No generated metric is a substitute for those checks.
