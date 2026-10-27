# 7-minute demo script

Before the call: `make up` (or `make dev-api` + `make dev-web`), log in once as each role, and keep tabs open for the app, `http://localhost:8000/docs` and the code (`services/llm/gateway.py`).

| Time | Do this | Say this |
|---|---|---|
| 0:00 | Show the README table | "HelpdeskIQ is an AI copilot for an internal IT/HR helpdesk. I built it to show how I integrate LLM APIs into a production-style full-stack app: FastAPI, React/TypeScript, Postgres + pgvector, Redis, Docker, K8s and Terraform." |
| 0:40 | Log in as **Employee** and click "How many sick leave days do I get?" | "The answer streams over Server-Sent Events. Before calling the model I retrieve the most relevant policy chunks with hybrid search, so the answer is grounded and cited." |
| 1:20 | Expand **sources**, point at the model/tokens/cost/latency line | "Every response shows which model answered, the tokens used, the cost and the latency. All of it is recorded per call." |
| 1:50 | Ask the same question again and point at the **cache hit** badge | "The second time costs $0. The cache key is the normalised question plus the retrieved chunk IDs, so it's shared across users and invalidates itself when documents change." |
| 2:20 | Ask "What's the cafeteria menu?" | "Nothing relevant was retrieved, so we don't call the LLM at all. That saves cost and avoids a made-up answer." |
| 2:40 | Type a message with an email or phone number | "PII is redacted before anything leaves our system for a third-party model." |
| 3:00 | Type "Ignore all previous instructions..." | "A prompt-injection guard blocks it, and retrieved documents are wrapped and marked as data, not instructions." |
| 3:20 | Tickets, then **New ticket** ("VPN down, can't work, urgent") | "Creating a ticket returns immediately. The API publishes an event and a worker triages it with the cheaper Haiku model using structured JSON output, validated with Pydantic." |
| 4:10 | Sign in as **Agent** and show the AI-suggested reply; change status | "Agents get a drafted reply. Role-based access: employees only see their own tickets, enforced in the API, not just the UI." |
| 4:50 | Sign in as **Admin** and open AI usage & cost | "This is cost governance: spend, cache hit rate, p50/p95 latency and fallbacks by model and task. The same numbers go to Prometheus for alerting." |
| 5:30 | Open `gateway.py` | "This is the core: one gateway with caching, retries with exponential backoff and jitter, a provider fallback chain (Claude, then Azure OpenAI, then mock), and cost accounting. Providers are a Strategy; adding Gemini is one class and one line in the factory." |
| 6:10 | Show `docker-compose.yml`, `infra/k8s`, `infra/terraform/aws`, `.github/workflows/ci.yml` | "Locally it runs as the full stack in Compose. For AWS: EKS with HPA and PDB, RDS Postgres with pgvector, ElastiCache, S3, SQS with a DLQ, Secrets Manager and IRSA. CI runs lint, 29 backend tests, frontend tests, Playwright E2E, Trivy image scans and an OIDC-based deploy behind manual approval." |
| 6:50 | Close | "Happy to go deeper into any part: the cost model, the failure handling, or how I'd scale it." |

**If something breaks live:** set `LLM_PROVIDER=mock` and restart. Everything works offline. That's also a good moment to talk about graceful degradation.
