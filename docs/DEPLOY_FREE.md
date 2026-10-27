# Free public demo: Vercel + Render + Neon ($0)

| Piece | Host | Notes |
|---|---|---|
| React frontend | Vercel (Hobby) | Root directory `frontend`, env `VITE_API_URL` |
| FastAPI API (Docker) | Render free web service | `render.yaml` blueprint; sleeps after 15 min idle (~1 min cold start) |
| PostgreSQL + pgvector | Neon free | Region Singapore (`aws-ap-southeast-1`) to sit next to Render Singapore |
| Cache, rate limit, events, transcripts | in-process | Single instance, so the in-memory adapters are enough (`WEB_CONCURRENCY=1`) |

Public-demo hardening is built in: `LLM_DAILY_BUDGET_USD=1` (after $1/day the gateway serves the offline model), `DEMO_MODE=true` (documents can't be deleted; knowledge base capped at 25 docs), `RATE_LIMIT_PER_MINUTE=15`, and `SEED_ON_STARTUP=true` (idempotent demo data on boot).

## Steps

1. **Neon:** create a project (Postgres 16, region Singapore) and copy the connection string (`postgresql://...?sslmode=require`). pgvector is enabled automatically by the app (`CREATE EXTENSION vector`).
2. **Render:** Dashboard -> New -> **Blueprint** -> pick `helpdesk-iq`. Fill in the prompted values:
   - `DATABASE_URL`: the Neon string
   - `ANTHROPIC_API_KEY`: your key
   - `CORS_ORIGINS` / `FRONTEND_URL`: the Vercel URL from step 3. Use a placeholder first and update it after step 3; Render redeploys automatically.

   Wait for the deploy, then open `https://<service>.onrender.com/health`.
3. **Vercel:** New Project -> import `helpdesk-iq` -> Root Directory `frontend` -> Environment Variable `VITE_API_URL=https://<service>.onrender.com` -> Deploy.
4. Put the Vercel URL into Render's `CORS_ORIGINS` and `FRONTEND_URL`.
5. **Keep warm (optional):** GitHub repo -> Settings -> Variables -> `DEMO_API_URL=https://<service>.onrender.com`. The `Keep demo warm` workflow then pings it every 10 min during Indian working hours.
6. Smoke test: log in as each demo user, ask a question, raise a ticket, open the admin dashboard.

## Limits to mention if asked
- The first request after idle can take ~1 minute (free tier cold start). The keep-warm job hides this during the day.
- Uploaded files live on ephemeral disk; their chunks and embeddings persist in Neon, so answers keep working after restarts.
- The production design (EKS, RDS, ElastiCache, SQS) is in `docs/INFRA.md` and `infra/`. The free demo is intentionally the smallest footprint of the same code.
