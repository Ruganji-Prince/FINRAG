# GitHub publication verification

Repository: https://github.com/Ruganji-Prince/FINRAG

Verified source commit: `bc7fdc47cbd342783873fff0718b6771e6fa4439`. This report and its evidence are added by a subsequent documentation-only commit; the application source remains identical to that verified source commit.

## Publication and history

The existing repository was cloned into a separate temporary directory outside Box with normal Git. Its original commit `050397e593e11139b2277bef8e8904899b20ac9f` and README were preserved. The source commit added 180 files, giving 181 tracked files. A second independent clone from GitHub succeeded, and every one of those 181 files matched the approved local manifest byte-for-byte by SHA256. The manifest is published as `docs/approved-release-manifest.json`.

Four verification-only files are then added: this report, the source manifest, and the two actual GitHub JUnit artifacts. The resulting tree contains 185 tracked files: 181 approved source/evidence files plus these four verification files. No force push, repository replacement or history rewrite was used. The README retains its 41.7% original holdout disclosure and unfinished-reliability-work notice.

## Exact terminal results and error diagnosis

- `git --version`: Git 2.56.1.windows.1. Git and GitHub CLI were initially missing from PATH; official portable releases were downloaded outside Box and their published SHA256 digests verified.
- `gh auth status`: authenticated as Ruganji-Prince through the Windows keyring, with repo/workflow access. No token value was displayed or copied into files.
- `git clone https://github.com/Ruganji-Prince/FINRAG.git`: exit 0, initial tree README only.
- `git add` used only approved manifest paths; staged Git blobs were compared against all 181 manifest hashes and scanned before commit.
- `git commit`: exit 0; source commit shown above.
- First `git push origin main`: exit 128. The message included `fatal: could not read Username for 'https://github.com': No such file or directory`. An inherited credential helper pointed to a nonexistent executable, and the initial local helper path lost quoting at a space. This was a helper invocation error, not failed GitHub account authorization. Only the clone's credential-helper configuration was corrected using proper argument quoting and an inherited-helper reset.
- Retried `git push origin main`: exit 0; normal fast-forward `050397e..bc7fdc4 main -> main`. `git ls-remote origin refs/heads/main` matched the local source commit.

The earlier connector upload never published a complete tree. One observed connector-transport problem was truncated tool output causing JSON parsing to fail at character 524288; raw request headers/status were not exposed, so no GitHub HTTP status is invented. A separate observed `{"detail":"Bad Request"}` occurred in automatic command approval before a fresh-install command executed. Normal approval later recovered with smaller commands. That was distinct from the Git credential-helper failure. Connector file uploads were stopped as requested; all complete source uploads used standard Git.

## Independent remote and security verification

- Fresh independent clone: exit 0; all required backend, frontend, retrieval, embedding, database, ingestion/refinement, tests, evaluation, screenshots, deployment and documentation paths present.
- 181 source files checked against the approved SHA256 manifest: zero mismatches. Original README SHA256: `e44946a10b97bfb31ac5a873c5ebfca6f516385818cb1f63930399e3e13d5272`.
- All 17 relative README links resolved in the fresh clone. The external NISR terms link returned HTTP 200. Localhost demo links are deliberately local URLs, not claims of public hosting.
- Staged configured-secret and credential-pattern scans: no findings. Private environment files, credentials, databases, virtual environments, raw/review PDFs, model weights, caches, runtime binaries and backups are excluded. Only the safe `.env.example` template is included.
- All files are below GitHub's 100 MiB file limit. Distributed text/vector snapshots contain only NISR publications with recorded CC BY 4.0 data/analysis attribution. No raw PDFs/logos or unapproved BNR documents are published.
- Source/configuration whitespace check passed with Windows line endings recognized. Historical JUnit XML contains pre-existing whitespace; its original bytes were retained rather than rewriting evaluation evidence.

## Actual CI and clean setup results

[Push workflow](https://github.com/Ruganji-Prince/FINRAG/actions/runs/44095115933): success. Lint, dependency compatibility, release scanning and PostgreSQL tests passed: 71 passed, 1 semantic test intentionally skipped. The manual job was not part of a push event.

[Manual semantic workflow](https://github.com/Ruganji-Prince/FINRAG/actions/runs/44095870772): success. Actual pinned Sentence Transformers and PostgreSQL/pgvector integration ran: **72 passed, zero failures/errors/skips**. The real JUnit artifacts are included under `evaluation/results/github-push-tests.xml` and `github-semantic-tests.xml`. CI initialized its PostgreSQL container; this does not claim that the entire application Compose stack was run locally.

Fresh independent Windows clone, new virtual environment, documented pinned core/dev dependency installation: exit 0. Pip was upgraded to documented 26.3; `pip check` reported no broken requirements. The original SQLite snapshot restored 2 documents/75 passages. Actual API requests returned documents/evidence and explicit retrieval-only mode. Fresh lightweight regression suite: **68 passed, 4 PostgreSQL/model integrations skipped**, zero failures/errors. One upstream Starlette/httpx deprecation warning remains; full remote semantic CI passed all 72 tests.

## Limits that publication does not remove

The improved reliability pipeline has not completed a new independent holdout or new end-to-end local-LLM/UI accuracy evaluation. The original 41.7% result is preserved and must not be replaced by a claim of measured improvement. Human review remains pending; BNR reuse permission has not been granted. Full Compose execution, commercial-provider billing/live behavior and public application hosting remain separate verification tasks. No hosting purchase was made. This is an experimental research prototype, not a production banking platform.
