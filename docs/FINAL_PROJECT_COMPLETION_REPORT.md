# FinRAG final project completion report

Prepared 17 November 2026 from actual local evidence. Existing functionality was extended; earlier SQLite data, snapshots, development evaluation and historical reports were preserved.

**Outcome:** genuine local PostgreSQL/semantic/LLM RAG is demonstrated with 30 official publications and 839 passages. All 72 tests pass. The project is not fully complete for bank production or reliable unrestricted answering: the new holdout exposes substantial relevance/coverage failures. Docker execution, commercial-provider verification, independent human adjudication, public hosting and GitHub publication remain explicitly unverified or externally blocked.

## Requirement audit

| Requirement | Implementation status | Verification method | Actual evidence | Outstanding limitations | Action required from user |
|---|---|---|---|---|---|
| Preserve existing implementation and evidence | Completed and verified | Regression tests; history/artifact inspection | 72 passing tests; original SQLite/snapshots and 32-case development evaluation retained | No .git history was present in supplied workspace; none was rewritten | None for the local demonstration |
| PostgreSQL, pgvector, migration, indexes and SQLite option | Completed and verified | Real native database and isolated integration tests | Migration/persistence/semantic tests; database-verification.json; 30-document restart fingerprint | Native Windows development deployment, not managed HA | Use separate operator and reader credentials |
| Docker Compose execution | Implemented but unverified | Official Compose schema validation only | compose-final-verification.json; health/resource/PID limits configured | Docker executable/engine and WSL absent; image startup and container limits not runtime-tested | Run documented Compose checks on a Docker-capable host |
| Semantic retrieval and measured hybrid ranking | Completed and verified | Real embeddings, pgvector search, HTTP modes and same-question benchmark | holdout-retrieval.json; keyword Recall@5 1.0, vector 0.6458, hybrid 0.75 | Keyword outperformed hybrid; sampled old/new library vector compatibility only | None to reproduce; improve ranking using separate development data |
| Actual local LLM RAG and source validation | Completed and verified | Pinned Qwen float32 inference; HTTP and browser checks | local-rag-calibration.json; api-verification.json; 18 generated holdout responses | Extractive quote selection; no validated free-form synthesis or broad semantic accuracy claim | Review original PDFs before relying on answers |
| Cloud Gemini/OpenAI live inference and billing | Blocked by external dependency | Mocked adapter contracts and retry/error tests | 72-test suite includes both provider contracts; environment credential check found no valid cloud key | No live commercial inference, quotas or billing verification | Configure authorized LLM_API_KEY/model and approve any paid usage before live checks |
| Provider reliability and fallback behavior | Completed and verified | Bounded retry, timeout and concurrency tests; actual healthy local path | tests/test_security.py; provider failures abstain with retained evidence | No automatic provider switching; decoding time is checked between steps | None for local mode; provision capacity before public use |
| Complete provider billing ledger | Incomplete | Usage/cost implementation review | Successful calls expose token usage; local holdout 8496 prompt/1686 completion tokens | Failed or invalid billable cloud responses are not fully accounted; hardware/energy not priced | Establish billing observability if commercial APIs are enabled |
| Expand permitted corpus to about 30 publications | Completed and verified | Original PDF SHA256/page checks and incremental re-ingestion | 30 NISR documents, 839 passages; corpus-30-verification.json; versioned v3 snapshot | All indexed publications are NISR; some release days are explicitly imputed/proxies | None for licensed NISR demonstration |
| BNR monetary, stability and annual reports | Blocked by external dependency | Source/robots and rights review recorded | docs/bnr-source-review.json; candidates excluded from index and distributed PDFs | Clear reproduction/redistribution basis not established | Obtain or verify publisher permission before indexing/redistributing |
| General financial answer relevance and completeness | Incomplete | Untuned 30-question actual HTTP/LLM holdout | holdout-rag.json; 10/24 expected-anchor coverage, 6/24 unnecessary refusals; 14 diagnostic failures retained | Wrong-measure/chart/table selections and comparison headings remain; exact-source support is not relevance | Use a separate development set and a new untouched validation set before a stronger accuracy claim |
| Quotation/citation, unsupported and injection safeguards | Completed and verified | Exact database text/page/URL checks; adversarial cases and unit tests | 100% quotation/citation integrity for emitted holdout claims; unsupported requests refused 6/6 | Heuristic defenses and a small refusal set do not prove universal security or answerability | Retain human verification for financial conclusions |
| Independent-from-tuning holdout and retrieval comparison | Completed and verified | Frozen backend before authoring; original PDF labels; actual inference | holdout-freeze.json, holdout-v1.json, holdout-rag.json, holdout-retrieval.json | Agent-authored and partly related templates; not independently human-authored or production-distribution validation | Do not reuse its scores as unbiased evidence after tuning against it |
| Human-review package | Completed and verified | Packet generation from actual answers and references | 30 shuffled provider-anonymized packets; blank ratings CSV; rubric and separate key | No completed human ratings or agreement calculation | Give packets to independent financial researchers |
| Independent human answer adjudication | Blocked by external dependency | Review package status inspection | Human-reviewed count is 0; human_verified_accuracy remains null | Requires independent reviewers; no simulated human result | Collect two independent ratings and adjudicate disagreements |
| Security controls for the research demonstration | Completed and verified | Real authenticated HTTP service plus regression/security review | Anonymous 401, authorized catalogue 200, oversized chunked request 413; audit zero known findings | Shared token only; loopback test, not public penetration testing | Keep ports private and secrets local |
| Financial-institution production hardening | Incomplete | Documented security gap review | docs/security-review.md | No enterprise SSO/RBAC, isolated PDF workers, distributed limits, restore drills, monitoring or concurrent-load qualification | Commission production security/operations work before institutional deployment |
| Operational governance and DAMA-inspired evidence | Completed and verified | Stored catalogue/history/lineage plus checksum and privilege checks | source-catalogue.json persisted; all governance checksums valid; reader cannot write after read-only flag disabled | DAMA-inspired practice only; no DAMA or banking certification | Assign institutional stewards and retention policy for real adoption |
| Existing six-page Streamlit UI and mobile readability | Completed and verified | Real Edge browser; actual answer/link/comparison and 390px viewport | docs/screenshots/verification.json and PNGs | Smoke/visual review only; no formal accessibility audit | None for local demonstration |
| Hosting feasibility assessment | Completed and verified | Current official provider documentation reviewed | docs/hosting-assessment.md; Render memory/sleep limits; HF subscription requirement; Neon database-only option | Prices and eligibility can change; no authorized cloud account provisioned | Recheck terms before selecting a host |
| Secure public deployment | Blocked by external dependency | Local/container readiness assessment | Local http://127.0.0.1:8501 verified; no public URL created | No authorized suitable host/gateway; paid subscription cannot be enabled without approval | Provide hosting authorization and an approved budget if a paid resource is needed |
| Public release content preparation | Completed and verified | Publication allowlist and configured-secret/pattern scan | scripts/prepare_release.py; release/manifest.json, secret-scan.json and ZIP | Scanning is not a guarantee against every sensitive item; no source-code license chosen | Review release manifest and choose source-code license if desired |
| Publish requested GitHub repository | Blocked by external dependency | Connected account lookup and exact target repository check | Authenticated account Ruganji-Prince; requested target returned 404; no create-repository tool available | No public repository or remote CI run created | Create empty FinRAG-Rwanda-Financial-Intelligence under the connected account, or configure authenticated Git tooling |
| README, architecture, setup, security/evaluation/failure documentation | Completed and verified | Cross-check against actual saved evidence | README.md; docs/architecture.md, postgres.md, evaluation.md, deployment.md, security-review.md, hosting-assessment.md | Fresh container/cloud setup not executed on this host | Follow explicit unverified steps on the appropriate host |
| Automated verification and CI configuration | Completed and verified | Final full native/model suite, lint, dependency check, API and browser runs | 72 passed, 0 failed/errors/skipped; lint/pip check passed; dependency audit zero findings | CI is configured but remote Actions execution is unverified | Run remote CI once an authorized repository exists |
| Final requirement/status report | Completed and verified | Generated from completion artifacts with assertions | docs/FINAL_PROJECT_COMPLETION_REPORT.md and docs/final-report.json | External dependencies and incomplete accuracy/hardening remain explicit | Address the actions in this table before stronger public claims |

## Actual measured results

| Measure | Actual result |
|---|---|
| Full automated tests | 72 passed; 0 failures, errors or skips |
| Permitted corpus | 30 official NISR publications; 839 passages |
| Holdout | 30 requests completed; 24 supported questions, 6 unsupported/adversarial requests |
| Published quotation/citation integrity | 100% for emitted claims across 18 generated responses; exact-source check, not answer accuracy |
| Unsupported-request abstention | 6/6 |
| Unnecessary supported-question abstention | 6/24 (25%) |
| Expected-anchor coverage | 10/24 (41.7%); automated heuristic |
| Mean server latency | 17.764 seconds across all 30 requests, including fast refusals |
| Recorded successful local inference usage | 8,496 prompt tokens; 1,686 completion tokens |
| Local cloud API fee | $0; hardware/energy unpriced |
| Human-verified answer accuracy | Unmeasured; zero human ratings |
| Dependency advisory audit | Zero known findings in final installed environment; initial 25 advisory entries retained |

| Holdout retrieval configuration | Page Recall@5 | MRR@5 |
|---|---:|---:|
| keyword | 1.0000 | 0.8646 |
| vector | 0.6458 | 0.2431 |
| hybrid | 0.7500 | 0.3611 |

Keyword ranked the reference pages better than vector/hybrid retrieval. The exact-page labels can penalize equivalent evidence on another page; the result still exposes the weakness of the current configuration. No post-holdout tuning was performed. Development scores from the earlier 15-report corpus are retained separately and are not promoted as holdout results.

## Failures and practical limits

Fourteen holdout diagnostics are retained: six unfiltered CPI questions unnecessarily refused; selected energy/core/fresh-product questions answered with general CPI or graph/table material; a PPI methodology question selected a table fragment; and both new comparison questions selected headings rather than the requested statistics. Quotations remained source-authentic, but authenticity did not establish relevance or completeness. These failures prevent claiming broadly reliable financial QA. See `evaluation/results/holdout-failure-cases.json` and the blank human-review package.

The model-library upgrade initially changed tokenizer return types and lower-precision CPU loading behavior. Explicit tensor-return and float32 settings restored actual factual calibration; subsequent HTTP and browser checks passed. The enlarged dropdown initially broke the browser selector; searching the virtualized options fixed the test interaction without weakening answer assertions. A persistence-check subprocess inherited server pipe handles; after verifying process ancestry, it was stopped and the restart check was rerun with safe output handles. The final before/after 30-document fingerprint matches.

## Evidence and reproduction

Run `python scripts/run_checks.py --postgres --models`, `python -m ruff check .`, `python -m pip check`, `python scripts/api_smoke.py`, `python scripts/security_smoke.py`, and `python scripts/browser_smoke.py` with the project virtual environment and native database. See `docs/acceptance.md` for exact commands, outcomes and test prerequisites. Model/provider and corpus fingerprints appear in the evaluation artifacts. All raw PDFs, private credentials, caches, databases and runtime binaries are excluded from the release bundle.

The current reliable demonstration is local at `http://127.0.0.1:8501`. No public deployment/repository URL or successful remote CI run is invented. The GitHub account connection is available, but repository creation is not exposed by its tools. No existing `.git` directory was supplied, and no repository history was rewritten.

## Ownership and next decisions

Create the named empty GitHub repository or supply authenticated Git tooling; choose a source-code license if desired; obtain BNR rights clarification; supply authorized commercial-provider credentials only if cloud testing is wanted; arrange independent financial review; and approve a host/budget before any paid provisioning. Accuracy work must use separate development material followed by a newly untouched test set. Enterprise security and operations qualification remain required for institutional production.
