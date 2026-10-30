# TASKS.md — Sub-task tracker

One sub-task = one `feature/<name>` branch = one pull request into `development` = one ✅ after
merge. This is the tracker [docs/Git_Github_Workflow_Guide.md](docs/Git_Github_Workflow_Guide.md)
refers to.

Phases come from [PLAN_PHASE.md](PLAN_PHASE.md); requirement rows from [PLAN.md](PLAN.md).

**Rules**

- Cut every branch from an up-to-date `development`.
- This is a monorepo — branches are repository-wide. Scope each branch to one project, and once
  a second project exists, name it `feature/clouddesk-<name>`.
- Do not stack a feature branch on another feature branch. If a task names a predecessor, merge
  the predecessor first.
- Mark Completed ✅ only **after** the PR merges — not when the code is written.
- A task is not complete without its test and without `make test` passing offline.

**Status:** ⬜ not started · 🟨 in progress · ✅ completed

---

## Phase 1 — Runtime skeleton

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 1.1 | Replace the `uv init` scaffold with the app layout; dependencies, ruff and pytest config in `pyproject.toml` | `feature/project-scaffold` | — | — | ⬜ |
| 1.2 | `core/config.py` — `get_settings()`, `lru_cache`d, plus `.env.example` with every variable | `feature/settings` | — | 1.1 | ⬜ |
| 1.3 | `core/logging.py` — JSON logs carrying `request_id` and `workflow_id` | `feature/json-logging` | — | 1.2 | ⬜ |
| 1.4 | `core/llm.py` — provider factory with the `fake` provider and `call_structured` | `feature/llm-factory` | F14 | 1.2 | ⬜ |
| 1.5 | `main.py` + health routes `/health`, `/health/live`, `/health/ready` | `feature/health-routes` | — | 1.3, 1.4 | ⬜ |
| 1.6 | `tests/conftest.py` offline fixtures + `Makefile` | `feature/test-harness` | F14 | 1.5 | ⬜ |

## Phase 2 — Persistence and demo data

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 2.1 | SQLAlchemy 2 models for all tables, portable across SQLite and Postgres | `feature/data-model` | — | 1.6 | ⬜ |
| 2.2 | `database/schema.sql`, `rls_policies.sql`, `seed.sql`, `migrations/0001_initial.sql` | `feature/postgres-ddl` | — | 2.1 | ⬜ |
| 2.3 | `core/database.py` + `create_tables()` on startup | `feature/db-session` | — | 2.1 | ⬜ |
| 2.4 | Repository layer — all SQL lives here | `feature/repositories` | — | 2.3 | ⬜ |
| 2.5 | `sample_data/*.json` — 13 tickets, 8 customers, subscriptions, workspaces, incidents, previous resolutions, products | `feature/sample-data` | — | 2.1 | ⬜ |
| 2.6 | 15 knowledge base articles with YAML front-matter | `feature/knowledge-articles` | — | — | ⬜ |
| 2.7 | `seed_service.bootstrap_demo_data()`, idempotent | `feature/demo-bootstrap` | F14 | 2.4, 2.5 | ⬜ |

## Phase 3 — Identity and request guards

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 3.1 | `core/security.py` — HS256 JWT, `require_role`, the three demo users | `feature/jwt-auth` | N1 | 2.7 | ⬜ |
| 3.2 | `/auth` routes | `feature/auth-routes` | N1 | 3.1 | ⬜ |
| 3.3 | `RequestIdMiddleware` + CORS exposure | `feature/request-id` | N3 | 1.5 | ⬜ |
| 3.4 | `core/redis.py` with the fakeredis fallback | `feature/redis-client` | — | 1.2 | ⬜ |
| 3.5 | `RateLimitMiddleware` — fixed window per client | `feature/rate-limit` | N2 | 3.4 | ⬜ |
| 3.6 | `AuditMiddleware` → `audit_logs` for every non-GET | `feature/audit-middleware` | N6 | 2.4 | ⬜ |
| 3.7 | Wire middleware in order CORS → RequestId → RateLimit → Audit | `feature/middleware-order` | N2, N3, N6 | 3.3, 3.5, 3.6 | ⬜ |

## Phase 4 — Support API

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 4.1 | `schemas/common.py` — categories, statuses, severities, channels | `feature/common-enums` | — | 2.1 | ⬜ |
| 4.2 | Ticket routes: create, list, get, update | `feature/ticket-api` | F1 | 3.7, 4.1 | ⬜ |
| 4.3 | Ticket actions: `/reply`, `/request-info`, `/escalate` | `feature/ticket-actions` | F12 | 4.2 | ⬜ |
| 4.4 | Customer routes | `feature/customer-api` | F4 | 3.7 | ⬜ |
| 4.5 | `/dashboard/summary` | `feature/dashboard-api` | — | 4.2 | ⬜ |
| 4.6 | `/escalations`, `/audit`, `/settings` | `feature/support-api-rest` | F10, N6 | 3.7 | ⬜ |
| 4.7 | RBAC 403 test coverage for every route | `feature/rbac-tests` | N1 | 4.6 | ⬜ |

## Phase 5 — Knowledge pipeline

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 5.1 | `rag/chunking.py` — heading split, 900/150 windows, title-heading prefix | `feature/rag-chunking` | F5 | 2.6 | ⬜ |
| 5.2 | `rag/vector_store.py` — protocol, `InMemoryVectorStore`, `QdrantVectorStore` | `feature/vector-store` | F5 | 5.1 | ⬜ |
| 5.3 | `FakeEmbeddings` (384 dims) + the embedding provider factory | `feature/embeddings` | F5, F14 | 1.4 | ⬜ |
| 5.4 | `rag/retriever.py` — hybrid, RRF k=60, heuristic rerank, cache | `feature/hybrid-retrieval` | F5 | 5.2, 5.3, 3.4 | ⬜ |
| 5.5 | `rag/ingest.py` + `make ingest` | `feature/rag-ingest` | F5 | 5.4 | ⬜ |
| 5.6 | `/knowledge` routes incl. admin-only `reindex` | `feature/knowledge-api` | F5 | 5.5, 4.7 | ⬜ |
| 5.7 | Similar-case lookup by Jaccard overlap | `feature/similar-cases` | F6 | 2.5 | ⬜ |

## Phase 6 — Tools and policy

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 6.1 | `integrations/` protocols, mock adapters, factory | `feature/mock-integrations` | — | 2.4 | ⬜ |
| 6.2 | `ToolRegistry` with timeout and `ToolResult(ok=False)` error containment | `feature/tool-registry` | F9 | 6.1 | ⬜ |
| 6.3 | `ToolPolicy` — approval table, unknown tools require approval | `feature/tool-policy` | F9 | 6.2 | ⬜ |
| 6.4 | Read-only tools: `get_customer`, `get_subscription`, `get_ticket_history`, `search_docs`, `check_service_status` | `feature/readonly-tools` | F4, F5, F7 | 6.3, 5.6 | ⬜ |
| 6.5 | Write tools: `update_ticket`, `reset_demo_setting`, `create_refund_request`, `create_escalation` | `feature/write-tools` | F8, F9, F10 | 6.3 | ⬜ |
| 6.6 | MCP server exposing the read-only tools + `make mcp` | `feature/mcp-server` | — | 6.4 | ⬜ |

## Phase 7 — Rules and guardrails

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 7.1 | `agents/rules.py` — `rule_category`, `rule_severity` (raise only) | `feature/classification-rules` | F2, F3 | 4.1 | ⬜ |
| 7.2 | `ESCALATION_RULES` with a named team per policy case | `feature/escalation-rules` | F10 | 7.1 | ⬜ |
| 7.3 | `scan_for_injection` + `wrap_untrusted` | `feature/injection-defence` | N4 | 1.2 | ⬜ |
| 7.4 | `agents/prompts.py` with the shared `SECURITY_PREAMBLE` | `feature/prompts` | N4 | 7.3 | ⬜ |
| 7.5 | `validate_customer_output` — internal URLs, secrets, other customers' data | `feature/output-validation` | N5 | 7.3 | ⬜ |

## Phase 8 — Specialist agents

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 8.1 | `schemas/workflow.py` — every agent output model | `feature/workflow-schemas` | F2–F8 | 4.1 | ⬜ |
| 8.2 | Support Supervisor — `understand`, `assess_severity` | `feature/supervisor-agent` | F2, F3 | 8.1, 7.1 | ⬜ |
| 8.3 | Customer Agent — no LLM call | `feature/customer-agent` | F4 | 8.1, 6.4 | ⬜ |
| 8.4 | Knowledge Agent | `feature/knowledge-agent` | F5, F6 | 8.1, 5.7 | ⬜ |
| 8.5 | Troubleshooting Agent with per-category playbooks | `feature/troubleshooting-agent` | F7 | 8.1, 6.4 | ⬜ |
| 8.6 | Resolution Agent — `plan_actions`, `_ground_response` | `feature/resolution-agent` | F8 | 8.1, 6.5, 7.5 | ⬜ |
| 8.7 | Escalation Agent — policy always wins | `feature/escalation-agent` | F10 | 8.1, 7.2 | ⬜ |

## Phase 9 — Workflow graph and trace

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 9.1 | `agents/state.py` — `SupportState` and its reducers | `feature/workflow-state` | — | 8.1 | ⬜ |
| 9.2 | Node implementations, one per specialist | `feature/graph-nodes` | F2–F8 | 9.1, 8.7 | ⬜ |
| 9.3 | `agents/graph.py` — wiring, `GRAPH_NODES`, `GRAPH_EDGES` | `feature/langgraph-wiring` | — | 9.2 | ⬜ |
| 9.4 | `agents/checkpointer.py` — `InMemorySaver` / `AsyncSqliteSaver` | `feature/checkpointer` | — | 9.3 | ⬜ |
| 9.5 | `WorkflowTracer` + `workflow_events`, never raises | `feature/workflow-tracer` | F13 | 9.3, 2.4 | ⬜ |
| 9.6 | `workflow_service` — `create_run`, `start_workflow`, per-node state save | `feature/workflow-service` | F13 | 9.4, 9.5 | ⬜ |
| 9.7 | `/tickets/{id}/run` (202), `/workflow`, `/events`, and `/agents` | `feature/workflow-api` | F13 | 9.6, 4.7 | ⬜ |
| 9.8 | `assess_risk()` and the `risk_check` routing | `feature/risk-check` | F9, F10 | 9.3, 7.5 | ⬜ |

## Phase 10 — Approval and escalation

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 10.1 | `human_approval` node with `interrupt()` | `feature/human-approval-node` | F9 | 9.8 | ⬜ |
| 10.2 | `_handle_interrupt()` → `approval_requests`, ticket `waiting_on_approval` | `feature/approval-persistence` | F9 | 10.1 | ⬜ |
| 10.3 | `/approvals` routes incl. approve and reject | `feature/approvals-api` | F9 | 10.2 | ⬜ |
| 10.4 | `resume_workflow(Command(resume=…))` | `feature/workflow-resume` | F9 | 10.3 | ⬜ |
| 10.5 | `execute_resolution` — one path for auto and approved actions | `feature/execute-resolution` | F8, F9 | 10.4, 6.5 | ⬜ |
| 10.6 | `escalation` node + `escalations` persistence | `feature/escalation-node` | F10 | 9.8, 8.7 | ⬜ |
| 10.7 | 409s: double-run, resuming an unpaused run | `feature/conflict-handling` | F9 | 10.4 | ⬜ |
| 10.8 | `make demo` — CD-1002 refund end to end with a pause | `feature/demo-cli` | F9, F14 | 10.5 | ⬜ |

## Phase 11 — Memory

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 11.1 | `memory/short_term.py` — Redis, 24 h TTL | `feature/short-term-memory` | F11 | 3.4 | ⬜ |
| 11.2 | `memory/long_term.py` — `customer_memory`, de-duplicated | `feature/long-term-memory` | F11 | 2.4 | ⬜ |
| 11.3 | `scrub()` + `SECRET_PATTERNS` | `feature/memory-scrub` | N7 | 11.2 | ⬜ |
| 11.4 | `recall_customer()` wired into `customer_context` | `feature/memory-recall` | F4, F11 | 11.2, 9.2 | ⬜ |
| 11.5 | `ticket_summary` and `memory_update` nodes, `record_resolution()` | `feature/memory-write` | F11 | 11.3, 10.5 | ⬜ |

## Phase 12 — Agent console

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 12.1 | Next.js 15 app shell, Tailwind, `components/ui/` kit | `feature/frontend-shell` | F12 | — | ⬜ |
| 12.2 | `lib/types.ts` mirroring the contract + `lib/api.ts` typed client | `feature/api-client` | F12 | 12.1, 9.7 | ⬜ |
| 12.3 | Auth: `/login`, token storage, 401 → `/login?reason=expired` | `feature/frontend-auth` | N1 | 12.2 | ⬜ |
| 12.4 | Layout, nav declared once in `components/layout/nav.ts` | `feature/frontend-nav` | F12 | 12.3 | ⬜ |
| 12.5 | `/dashboard` and `/tickets` | `feature/tickets-list` | F12 | 12.4 | ⬜ |
| 12.6 | `/tickets/[id]` three-column screen + `usePolling` | `feature/ticket-detail` | F12 | 12.5 | ⬜ |
| 12.7 | Workflow panel: 12 steps, chips, evidence, diagnosis, actions, editable reply | `feature/workflow-panel` | F12, F13 | 12.6 | ⬜ |
| 12.8 | Approve/reject/escalate controls with `canAct` role gating | `feature/approval-ui` | F9, F12 | 12.7, 10.3 | ⬜ |
| 12.9 | `/customers`, `/customers/[id]`, `/knowledge`, `/escalations`, `/agents`, `/audit`, `/settings` | `feature/console-pages` | F12 | 12.4 | ⬜ |
| 12.10 | `frontend/__tests__/` | `feature/frontend-tests` | F12 | 12.9 | ⬜ |

## Phase 13 — Evaluation and delivery

| # | Sub-task | Branch | Rows | Depends on | Status |
|---|---|---|---|---|---|
| 13.1 | `datasets/eval_cases.json` | `feature/eval-dataset` | — | 12.10 | ⬜ |
| 13.2 | `tests/evaluation/` — the five thresholds | `feature/eval-harness` | F2, F5, F8, F10 | 13.1 | ⬜ |
| 13.3 | Backend + frontend Dockerfiles, non-root with HEALTHCHECKs | `feature/dockerfiles` | N8 | 12.10 | ⬜ |
| 13.4 | `docker-compose.yml` with `depends_on: service_healthy` | `feature/docker-compose` | N8 | 13.3 | ⬜ |
| 13.5 | `tests/deployment/` — compose, image hygiene, `.env.example` coverage, no committed `.env` | `feature/deployment-tests` | N8 | 13.4 | ⬜ |
| 13.6 | Shared Terraform modules | `feature/terraform-modules` | N8 | 13.4 | ⬜ |
| 13.7 | AWS, Azure and GCP roots + environment var-files | `feature/terraform-roots` | N8 | 13.6 | ⬜ |
| 13.8 | `deployment/scripts/` — deploy, build_and_push, smoke_test, rollback, destroy | `feature/deploy-scripts` | N8 | 13.7 | ⬜ |
| 13.9 | CI: `test.yml`, `security.yml`, `docker-build.yml`, `terraform-validate.yml` | `feature/ci-workflows` | N8 | 13.5 | ⬜ |
| 13.10 | `_deploy.yml` reusable pipeline with OIDC and the `prod-apply` environment | `feature/deploy-pipeline` | N8 | 13.9 | ⬜ |
| 13.11 | `README.md` and a final honest-status pass over `MEMORY.md` | `feature/final-docs` | — | 13.10 | ⬜ |

---

## Blocked / needs a decision

These cannot be closed by writing code. They are tracked as discrepancies D1–D9 in
[MEMORY.md](MEMORY.md) §3.

| # | Item | Needs |
|---|---|---|
| B1 | Promotion branch is named `test` on the remote; everything else now says `testing` (D2) | Run the branch rename. Remote URL (D1) and monorepo shape (D3) are settled — see the MEMORY.md decision log. |
| B2 | `pyproject.toml` `uv init` scaffold conflicts with the specified layout (D5) | Covered by task 1.1 once the decision is confirmed. |
| B3 | Whether `../docs/`, `../deployment-agent/`, `../shared-infrastructure/` are copied in or referenced (D9) | A decision before phase 13. |
| B4 | Authoritative table count, 15 vs 16 (D7) | Settled by writing `database/schema.sql` in task 2.2. |
