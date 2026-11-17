# Publication status

Target: https://github.com/Ruganji-Prince/FINRAG, explicitly authorized by the owner. The public repository was empty when inspected. No prior local .git directory was present; no history is rewritten.

This upload contains the current experimental source, the preserved original evaluation, screenshots from the earlier working UI, and incomplete reliability work. It is not a claim that the new ranking/context logic has improved accuracy. The original 41.7% holdout is retired as diagnostic evidence; a new untouched final holdout has not yet been built or run. Independent human review remains pending.

Thirty official NISR reports are represented in the original licensed snapshots. The original 839 chunks remain, with 755 source-preserving supplementary sentence/layout blocks added to the local PostgreSQL corpus by pipelines/refine.py. Those supplementary blocks require the original PDF refresh and refinement command to reproduce; they are not silently claimed to be in the old snapshots. Table layout preserves available text positions, not guaranteed semantic cell associations; rotated text can be incomplete. No BNR permissions are assumed.

The full current automated test result is recorded separately under evaluation/results/publication-tests.xml. final-tests.xml and publication-tests.xml record the current 72-pass run; earlier reports retain their historical checkpoint summaries. Lint was checked before publication. Current improved-development inference and a new final holdout remain incomplete. The original development-baseline run completed and is retained under reliability-dev-baseline.json.

The earlier completion report and screenshots are historical checkpoint evidence. Cloud-provider testing, Docker execution and public hosting remain unverified or blocked by external dependencies. No hosting fees were incurred. This repository is an experimental research prototype, not a production banking platform.

Private .env files, database credentials, local databases, model weights/cache, raw/review PDFs, runtime binaries, logs and local backups are excluded. Dataset derivatives carry NISR attribution and documented rights notes. The owner has not selected a source-code license.
