.PHONY: setup dev-api dev-web seed test e2e up down logs lint

setup:            ## install backend venv + frontend deps
	cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm install

dev-api:          ## FastAPI on :8000 (SQLite, in-memory cache/queue, mock LLM unless a key is set)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-web:          ## React on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

seed:             ## demo users, policies and tickets (local dev)
	cd backend && .venv/bin/python -m app.seed

test:             ## unit + integration tests
	cd backend && .venv/bin/ruff check app tests && .venv/bin/pytest
	cd frontend && npm run typecheck && npm test

up:               ## full stack: postgres+pgvector, redis, mongo, api, 2 workers, web, prometheus, grafana
	cp -n .env.example .env || true
	docker compose up -d --build --wait
	docker compose exec -T api python -m app.seed

e2e:              ## Playwright against the docker stack
	cd frontend && BASE_URL=http://localhost:8080 npx playwright test

down:
	docker compose down

logs:
	docker compose logs -f api worker
