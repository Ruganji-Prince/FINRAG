# Deployment preparation verification - 2026-11-17

The application is a research prototype, not a production banking platform. There is **no verified public deployment URL**. Neon and Gemini account access/credentials remain unconfirmed; no billing or paid service has been enabled.

| Check | Actual result |
| --- | --- |
| Local Python regression/integration suite | 92 passed, zero skipped, including native PostgreSQL and semantic model |
| Linux CI Python suite | 91 passed, one optional real-model test skipped |
| Next.js security tests | 11 passed locally and in CI |
| TypeScript / production build | Passed locally and in Linux CI |
| Actual browser workflow | Six pages, GDP research, report comparison and mobile layout passed |
| GDP local RAG smoke | 9.4% with GDP report page-3 citation; 27.74 seconds on the final smoke run |
| Unsupported future statistic | Refused in 0.22 seconds; one smoke question, not a benchmark |
| Shared quota integration | 32 concurrent PostgreSQL calls yielded exactly 20 allowances; counter reads denied to gateway role |
| Compact Linux runtime | 326,459,429 bytes installed dependencies plus stage; 387,682,304 bytes peak process memory; 32 ONNX embeddings, 384 dimensions; no Torch |
| Actual Vercel function bundle / cold start | Not tested |
| Hosted Neon + Gemini queries | Not tested |
| Original holdout expected-statistic coverage | Preserved at 41.7%; no new independent accuracy claim |

Linux CI: [successful run 44140786720](https://github.com/Ruganji-Prince/FINRAG/actions/runs/44140786720), source commit `43d173d08ee3786fa804345b87823d9ada572bdd`. Main test, frontend and compact API jobs passed. The separate opt-in semantic-integration job was skipped on this push; the actual semantic test passed locally. The ONNX probe used fake hosted configuration and made no hosted database or LLM calls.

Evidence: [browser checks](../evaluation/results/next-workflow-verification.json), [unsupported smoke](../evaluation/results/next-abstention-verification.json), [Linux probe](../evaluation/results/compact-runtime-linux.json), [Python results](../evaluation/results/deployment-tests.xml), [actual screenshots](screenshots/next/overview.png). These smoke cases do not replace independent evaluation.

Publication was performed using normal Git, preserving the original README content and history. The source commit above was independently cloned from remote main: all 244 files matched the approved local manifest by SHA256. Secrets, raw PDFs, local databases, runtime caches and model weights were excluded; the allowlisted secret scan returned zero findings. The setup/readme local links were checked (25 links, zero missing targets). The subsequent evidence-only commit adds this report and the downloaded Linux probe; its final remote SHA is recorded in the publication report delivered to the owner.

Next operator actions: follow [VERCEL_SETUP](VERCEL_SETUP.md) to create Neon Free and Gemini free-tier projects, configure secrets privately, initialize the reader and quota roles, then deploy and run the hosted acceptance gate. No Upstash account is needed. The Vercel CLI was authenticated to the existing account, but no FinRAG Vercel project was created. The local Streamlit and SQLite fallback remain available.
