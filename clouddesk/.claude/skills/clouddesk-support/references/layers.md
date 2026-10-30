# Layering rules

From CLAUDE.md §4.2. Enforced by review and tests. A dependency that violates this table is a
refactor, not a shortcut.

| Layer | Folder | Responsibility | MUST NOT |
|---|---|---|---|
| API | `backend/app/api/` | HTTP, validation, auth, RBAC, background tasks | contain business rules |
| Services | `backend/app/services/` | orchestrate repos + graph | talk HTTP |
| Repositories | `backend/app/repositories/` | all SQL via SQLAlchemy | call LLMs |
| Core | `backend/app/core/` | config, llm factory, security, logging, redis, guardrails, observability, database | import `agents/` |
| Tools | `backend/app/tools/` | `@tool` functions + `ToolPolicy` + `ToolRegistry` | bypass the registry |
| Agents | `agents/` | state, graph, nodes, specialists, rules, prompts | write SQL directly (use repositories) |
| RAG | `rag/` | chunking, vector store, hybrid retrieval, ingest | know about tickets |
| Memory | `memory/` | short-term (Redis) + long-term (DB) facades | store secrets |
| Integrations | `integrations/` | Protocols + mock adapters + MCP server | be imported by `core` |
| Frontend | `frontend/` | pages, components, typed API client | hold the service-role key |

## Folder layout

```text
backend/app/   main.py · api/ · core/ · middleware/ · models/entities.py · schemas/ · repositories/ · services/ · tools/
agents/        state.py · graph.py · checkpointer.py · rules.py · prompts.py · nodes/ · specialists/
rag/           chunking.py · vector_store.py · retriever.py · ingest.py
memory/        short_term.py · long_term.py · memory_service.py
integrations/  protocols.py · mock/services.py · factory.py · mcp/server.py · mcp/client_example.py
frontend/      app/ (App Router) · components/ · lib/ (api.ts, types.ts, hooks.ts, format.ts, cn.ts) · __tests__/
database/      schema.sql · rls_policies.sql · seed.sql · migrations/
sample_data/   tickets.json · customers.json · subscriptions.json · workspaces.json · incidents.json
               previous_resolutions.json · products.json · knowledge_base/*.md (15 articles)
tests/         unit/ · api/ · rag/ · agents/ · workflow/ · evaluation/ · deployment/
deployment/    aws/ · azure/ · gcp/ · kubernetes/ · docker/ · scripts/
data/          (git-ignored) support.db · checkpoints.db
docs/          API_CONTRACT.md · ARCHITECTURE.md · Git_Github_Workflow_Guide.md
```

## Common violations and their fix

| Smell | Fix |
|---|---|
| A route builds a resolution plan inline | Move it to a service; the route calls the service. |
| A service issues `select()` | Move the query to a repository. |
| A node imports `sqlalchemy` | Call a repository through the service the node already has. |
| `core/config.py` imports from `agents/` | Invert it — pass the setting in, or read it from `get_settings()` inside `agents/`. |
| A specialist calls a tool function directly | Route it through `ToolRegistry.execute(name, args, approved=…)`. |
| `rag/retriever.py` takes a `ticket_id` | RAG does not know about tickets. Pass the query and category. |
| `frontend` calls `fetch()` outside `lib/api.ts` | Every call goes through the typed client. |

## Middleware order

Outermost last: **CORS → RequestId → RateLimit → Audit**.

- `RequestIdMiddleware` reads or creates `X-Request-ID`, exposed through CORS (N3).
- Rate limit is a fixed window per client in Redis, `RATE_LIMIT_PER_MINUTE` (demo 120) (N2).
- `AuditMiddleware` writes `audit_logs` for every non-GET request (N6).

## Routing

- Routers mount under `/api/v1`.
- Health routes are **unprefixed**: `/health`, `/health/live` (no I/O, for probes),
  `/health/ready` (db, redis, vector store, llm).
- Errors are `{ "detail": string }` with a correct status code. 409 when a ticket is already
  `waiting_on_approval`; 409 when resuming a run that is not paused.
