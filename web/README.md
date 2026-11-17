# FinRAG web workspace

Next.js frontend with six features, invitation-code sessions and a server-only FastAPI gateway. This supplements the existing Streamlit app. Experimental research prototype; original holdout expected-statistic coverage **41.7%**.

Use Node 24. Run `npm ci`, `npm test`, `npm run typecheck`, `npm run build`. Copy `.env.example` into ignored `.env.local` and fill secrets privately. Never use NEXT_PUBLIC_ for secrets. `npm run dev` binds loopback. Hosted setup and account instructions: [VERCEL_SETUP](../docs/VERCEL_SETUP.md).

A real API and database are required; the interface does not fabricate responses when configuration is missing. No Upstash account is needed. Production quotas use a restricted PostgreSQL function, and local in-memory quotas are forbidden on Vercel. The quota role cannot read the financial corpus.
