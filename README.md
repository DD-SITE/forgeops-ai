# ForgeOps AI — Engineering Intelligence & Autonomous Incident Copilot

ForgeOps AI is a full-stack engineering copilot that combines document ingestion, hybrid RAG, agentic workflows, external engineering tools, and human approval for write operations.

## What is implemented

- Next.js 16 + TypeScript frontend
- FastAPI backend with Clerk authentication and workspace RBAC
- PostgreSQL + pgvector
- Redis-backed ingestion queue
- MinIO/S3-compatible document storage
- PDF/DOCX/Markdown/TXT parsing
- Structure-aware chunking and local embeddings
- Hybrid semantic + PostgreSQL full-text retrieval
- Reciprocal-rank fusion + deterministic reranking
- Grounded Gemini answers with source citations
- LangGraph agent workflow with PostgreSQL checkpoint persistence
- Query expansion and structured action planning
- GitHub issue creation tool
- Optional incident API lookup tool
- Human-in-the-loop approval / reject / edit flow
- Agent run and action audit records
- SSE agent execution streaming
- Redis rate limiting
- OpenTelemetry + Sentry hooks
- Docker Compose local/prod-style stack
- GitHub Actions CI
- Pytest/Vitest/Playwright-ready structure

## Architecture

```text
Next.js
   |
   | Clerk session token
   v
FastAPI
   |
   +--> PostgreSQL + pgvector + FTS
   +--> Redis ingestion queue / rate limits
   +--> MinIO / S3
   |
   +--> LangGraph
          |
          +--> query expansion
          +--> hybrid retrieval
          +--> incident tool
          +--> GitHub tool -- approval required
          +--> grounded response + citations
          |
          +--> PostgreSQL checkpoint
```

## Local setup

Prerequisites:

- Node.js 24 LTS
- Python 3.12
- uv
- Docker Desktop
- Git

Copy the environment template:

```bash
cp .env.example .env
cp apps/web/.env.local.example apps/web/.env.local  # if you create one
```

Fill in Clerk and Gemini values.

Start infrastructure:

```bash
docker compose up -d postgres redis minio minio-init
```

Run database migrations:

```bash
cd services/api
uv sync
uv run alembic upgrade head
cd ../..
```

Start API:

```bash
cd services/api
uv run fastapi dev app/main.py
```

Start ingestion worker in a second terminal:

```bash
cd services/api
uv run python -m app.worker.main
```

Start frontend:

```bash
cd apps/web
npm ci
npm run dev
```

Open:

- http://localhost:3000
- http://localhost:8000/docs
- http://localhost:9001

## All-in-Docker mode

```bash
docker compose --profile app up --build
```

The profile starts PostgreSQL, Redis, MinIO, migrations, API, worker, and Next.js.

## Agent API

Create a run:

```http
POST /api/v1/workspaces/{workspace_id}/agent/runs
{
  "query": "Why did payment-service start returning 5xx errors after the latest deployment?"
}
```

Streaming:

```http
POST /api/v1/workspaces/{workspace_id}/agent/runs/stream
```

Approval:

```http
POST /api/v1/workspaces/{workspace_id}/agent/runs/{run_id}/approval
{
  "decision": "approve"
}
```

For an edit decision, send the edited action payload:

```json
{
  "decision": "edit",
  "payload": {
    "action_type": "github_create_issue",
    "repository": "owner/repository",
    "title": "Payment API 5xx after deployment",
    "body": "..."
  }
}
```

## External tools

GitHub:

```dotenv
GITHUB_TOKEN=
GITHUB_DEFAULT_REPOSITORY=owner/repository
```

Incident API:

```dotenv
INCIDENT_API_URL=https://your-internal-api.example.com/incidents/search
INCIDENT_API_TOKEN=
```

The GitHub tool is never executed directly from an LLM output. The graph interrupts before the write operation and resumes only after an authenticated workspace member approves it.

## Production checklist

Before public deployment:

1. Replace development secrets.
2. Use a managed PostgreSQL instance.
3. Use managed Redis.
4. Use private object storage and short-lived presigned URLs.
5. Configure Clerk production keys and authorized parties.
6. Set `LANGGRAPH_AES_KEY` for encrypted checkpoints.
7. Configure Sentry and OpenTelemetry.
8. Configure HTTPS and secure CORS origins.
9. Put the API behind a reverse proxy/WAF.
10. Restrict GitHub token permissions to the required repositories.
11. Run `alembic upgrade head` as a deployment migration step.
12. Run the CI suite before every deployment.

## Testing

Backend:

```bash
cd services/api
uv sync --dev
uv run ruff check app tests
uv run pytest
```

Frontend:

```bash
cd apps/web
npm ci
npm run lint
npm run build
```

## Important implementation note

The original project roadmap called for a large production system. The uploaded implementation already contained the foundation, authentication, workspaces, storage, ingestion, embeddings, vector search, and basic grounded Q&A. The completion pack adds the remaining runtime capabilities without deleting those existing features.
