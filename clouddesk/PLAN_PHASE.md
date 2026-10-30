# PLAN_PHASE.md — The 13-phase build

The build order for CloudDesk. [CLAUDE.md](CLAUDE.md) is the source of truth; this file sequences
it. [PLAN.md](PLAN.md) is the requirement catalog, [MEMORY.md](MEMORY.md) holds locked facts and
honest status, [TASKS.md](TASKS.md) tracks the branch-level sub-tasks.

> **Phase numbers differ between this file and `TASKS.md`. Always say which file you mean.**
>
> This file has 13 phases, matching CLAUDE.md §19. `TASKS.md` splits the work into 14 execution
> phases so that memory and the console shell can be built in parallel rather than in series.
> The numbers therefore do **not** line up — "Phase 8" is *Specialist agents* here and *Memory*
> in `TASKS.md`. The authoritative mapping is the **"Map to `PLAN_PHASE.md`"** table at the
> bottom of `TASKS.md`:
>
> | `TASKS.md` | This file |
> |---|---|
> | Phase 8 Memory | Phase 11 Memory (pulled forward of the graph) |
> | Phase 9 Specialist agents | Phase 8 Specialist agents |
> | Phase 10 Workflow graph and trace | Phase 9 Workflow graph and trace |
> | Phase 11 Approval and escalation | Phase 10 Approval and escalation |
> | Phases 12 and 13 Console shell, Ticket workflow screen | Phase 12 Agent console |
> | Phase 14 Evaluation and delivery | Phase 13 Evaluation and delivery |
>
> Phases 1–7 share the same number in both files. This file remains the **exit-criteria spec**;
> `TASKS.md` is the **execution order and branch list**.

Phase names and the status table come from CLAUDE.md §19. The per-phase goals, file lists, tests
and exit criteria are **derived** from the dependency order in CLAUDE.md — if a phase boundary
here contradicts CLAUDE.md, fix CLAUDE.md first, then this file.

Use the `clouddesk-phase` skill to run a phase. Nothing in a phase is finished until its exit
criteria pass, `make test` is green offline, and `make demo` still runs.

## Status summary

| Phase | Name | Status |
|---|---|---|
| 1 | Runtime skeleton | in progress |
| 2 | Persistence and demo data | not started |
| 3 | Identity and request guards | not started |
| 4 | Support API | not started |
| 5 | Knowledge pipeline | not started |
| 6 | Tools and policy | not started |
| 7 | Rules and guardrails | not started |
| 8 | Specialist agents | not started |
| 9 | Workflow graph and trace | not started |
| 10 | Approval and escalation | not started |
| 11 | Memory | not started |
| 12 | Agent console | not started |
| 13 | Evaluation and delivery | not started |

Keep this table, the CLAUDE.md §19 table and the `MEMORY.md` honest status in agreement.

---

## Phase 1 — Runtime skeleton

**Status:** in progress

**Goal.** A FastAPI app that starts, answers health probes, logs JSON with a request id, and
selects a fake LLM provider so everything downstream can be built offline.

**Files touched**

```text
backend/app/main.py
backend/app/core/config.py · logging.py · llm.py
backend/app/api/health.py
pyproject.toml · Makefile · .env.example
tests/conftest.py · tests/unit/test_llm_provider.py · tests/api/test_health.py
```

**PLAN rows:** F14.

**Tests added:** `tests/api/test_health.py` (all three health routes), `tests/unit/test_llm_provider.py`
(fake provider selected when `LLM_PROVIDER=fake`, no key required).

**Demo checkpoint:** `make backend` starts on `:8000`; `GET /health/live` returns 200 with no I/O.

**Exit criteria**

- [ ] `/health`, `/health/live`, `/health/ready` respond; `/health/live` performs no I/O
- [x] `setup_logging()` emits JSON lines carrying `request_id` and `workflow_id` fields — P1-1
- [x] `get_settings()` is `lru_cache`d and reads `.env` — P1-1
- [ ] `get_llm()` returns the fake provider with no API key present
- [ ] `tests/conftest.py` sets env vars **before** importing the app
- [ ] `make test` passes offline; `make lint` clean

---

## Phase 2 — Persistence and demo data

**Status:** not started

**Goal.** The 16 tables exist in both forms, and the 13-ticket demo dataset loads into an empty
SQLite database at startup.

**Files touched**

```text
backend/app/models/entities.py
backend/app/core/database.py
backend/app/repositories/
backend/app/services/seed_service.py
database/schema.sql · rls_policies.sql · seed.sql · migrations/0001_initial.sql
sample_data/*.json · sample_data/knowledge_base/*.md
tests/unit/test_seed.py
```

**PLAN rows:** F14 (criterion 3), groundwork for F1 and F4.

**Tests added:** table creation, `bootstrap_demo_data()` loads 13 tickets and 8 customers and is
idempotent on a non-empty DB.

**Demo checkpoint:** `make seed` populates `data/support.db`; starting the backend twice does not
duplicate rows.

**Exit criteria**

- [ ] SQLAlchemy 2 models are portable — JSON not JSONB, `String(36)` UUIDs
- [ ] The same models run on SQLite and on Postgres
- [ ] `database/schema.sql` is the authority on table count and shape
- [ ] Every table has an `updated_at` trigger in the Postgres DDL (`set_updated_at()`)
- [ ] RLS enabled on all data tables in `rls_policies.sql`
- [ ] `create_tables()` runs at startup; `bootstrap_demo_data()` only when `DEMO_MODE=true` and
      the DB is empty
- [ ] `data/` and `*.db` are git-ignored

---

## Phase 3 — Identity and request guards

**Status:** not started

**Goal.** Every request is authenticated, rate-limited, traceable and audited, and roles are
enforced.

**Files touched**

```text
backend/app/core/security.py
backend/app/middleware/request_id.py · rate_limit.py · audit.py
backend/app/core/redis.py
backend/app/api/auth.py
tests/api/test_auth.py · test_rbac.py · test_request_id.py · test_rate_limit.py · test_audit.py
```

**PLAN rows:** N1, N2, N3, N6.

**Tests added:** login returns a token, expired/invalid token is 401, each role boundary returns
403, `X-Request-ID` echoes and is generated, the rate limit returns 429, non-GET requests write
`audit_logs`.

**Demo checkpoint:** logging in as `vic.viewer@clouddesk.demo` and attempting a write returns 403.

**Exit criteria**

- [ ] HS256 JWT via PyJWT using `settings.effective_jwt_secret`; demo tokens expire in 8 h
- [ ] `require_role` enforces `viewer 1 < agent 2 < admin 3`
- [ ] The three demo users exist and authenticate
- [ ] Middleware order is CORS → RequestId → RateLimit → Audit
- [ ] `X-Request-ID` is exposed through CORS
- [ ] Redis falls back to fakeredis when `REDIS_URL` is empty
- [ ] Every non-GET request produces an `audit_logs` row

---

## Phase 4 — Support API

**Status:** not started

**Goal.** The full read/write surface for tickets, customers, escalations, audit and settings,
matching the contract.

**Files touched**

```text
docs/API_CONTRACT.md
backend/app/schemas/common.py · ticket.py · customer.py
backend/app/api/tickets.py · customers.py · dashboard.py · escalations.py · audit.py · settings.py
backend/app/repositories/ · backend/app/services/ticket_service.py
tests/api/test_tickets.py · test_customers.py · test_dashboard.py
```

**PLAN rows:** F1, F12 (server side).

**Tests added:** ticket CRUD, list filters and pagination, 404s, dashboard summary, reply and
request-info, RBAC 403s per route.

**Demo checkpoint:** create a ticket over the API and read it back.

**Exit criteria**

- [ ] Every route in `docs/API_CONTRACT.md` for these groups exists and matches it exactly
- [ ] The 10 categories, 7 statuses, 4 severities and 4 channels live in
      `backend/app/schemas/common.py`
- [ ] Errors are `{ "detail": string }` with correct codes
- [ ] Routers mounted under `/api/v1`; health routes stay unprefixed
- [ ] No business rules in the API layer

---

## Phase 5 — Knowledge pipeline

**Status:** not started

**Goal.** 15 knowledge articles are chunked, embedded, indexed and retrievable by hybrid search,
entirely offline.

**Files touched**

```text
rag/chunking.py · vector_store.py · retriever.py · ingest.py
backend/app/api/knowledge.py
sample_data/knowledge_base/*.md
tests/rag/
```

**PLAN rows:** F5, F6.

**Tests added:** ingest count, expected article for key queries, all three modes, cache
behaviour, RRF ordering, rerank, filters.

**Demo checkpoint:** `make ingest` indexes the knowledge base; `GET /knowledge/search?q=…`
returns a cited hit.

**Exit criteria**

- [ ] Articles load with YAML front-matter (title, category, tags, summary)
- [ ] Chunking splits on headings, then 900-char windows with 150-char overlap
- [ ] Every chunk is prefixed `"{title} - {heading}"`
- [ ] `VectorStoreService` protocol implemented by `InMemoryVectorStore` and `QdrantVectorStore`;
      nothing outside `rag/` knows which is active
- [ ] Hybrid = semantic ∪ BM25 → RRF (k=60) → heuristic rerank → optional LLM rerank → one hit
      per article
- [ ] `FakeEmbeddings` (hashed bag-of-words, 384 dims) works with no API key
- [ ] Retrieval cache key is `rag:{mode}:{category}:{top_k}:{query}` with a 300 s TTL
- [ ] `POST /knowledge/reindex` is admin-only and recreates the collection
- [ ] `rag/` contains no reference to tickets

---

## Phase 6 — Tools and policy

**Status:** not started

**Goal.** Seven tools, one registry, one policy. Nothing executes outside the registry.

**Files touched**

```text
backend/app/tools/registry.py · policy.py · customer_tools.py · knowledge_tools.py ·
                               status_tools.py · ticket_tools.py · billing_tools.py · escalation_tools.py
integrations/protocols.py · mock/services.py · factory.py
tests/unit/test_tool_policy.py · test_tool_registry.py
```

**PLAN rows:** F9 (policy half).

**Tests added:** each tool's approval decision, unknown tool requires approval, timeout produces
`ToolResult(ok=False)`, an exception inside a tool does not propagate.

**Demo checkpoint:** `make mcp` serves the read-only tools.

**Exit criteria**

- [ ] All seven tools are `async` and `@tool`-decorated, with docstrings written for the LLM
- [ ] Approval table matches CLAUDE.md §7.4 exactly
- [ ] **Unknown tools always require approval**
- [ ] All execution goes through `ToolRegistry.execute(name, args, approved=…)`
- [ ] `TOOL_TIMEOUT_SECONDS` honoured
- [ ] Exceptions become `ToolResult(ok=False)` — tool failures never crash the graph
- [ ] `MAX_REFUND_WITHOUT_APPROVAL` defaults to 0 and `APPROVAL_REQUIRED_FOR_REFUNDS` to true
- [ ] `integrations/` is not imported by `core/`

---

## Phase 7 — Rules and guardrails

**Status:** not started

**Goal.** Policy lives outside the model, and untrusted text cannot steer the system.

**Files touched**

```text
agents/rules.py · agents/prompts.py
backend/app/core/guardrails.py
tests/unit/test_rules.py · test_guardrails.py
tests/api/test_injection.py
```

**PLAN rows:** F3 (rules half), F10 (rules half), N4, N5.

**Tests added:** `rule_category`, `rule_severity` can raise but not lower, every
`ESCALATION_RULES` entry, `scan_for_injection` flags CD-1013, `wrap_untrusted` delimiting,
`validate_customer_output` blocks internal URLs / secrets / other customers' data.

**Demo checkpoint:** CD-1013 is flagged as injection and no export is attempted.

**Exit criteria**

- [ ] Every policy case — dispute, deletion, security, data loss, legal, enterprise outage — is
      decided by a rule with its own test
- [ ] Severity rules raise only
- [ ] `SECURITY_PREAMBLE` is shared by every prompt; `<untrusted_content>` is documented as data
- [ ] Output validation failure raises risk to `high`
- [ ] No rule depends on an LLM call

---

## Phase 8 — Specialist agents

**Status:** not started

**Goal.** Six specialists, each returning a Pydantic model, each tested in isolation.

**Files touched**

```text
agents/specialists/supervisor.py · customer.py · knowledge.py · troubleshooting.py ·
                                   resolution.py · escalation.py
backend/app/schemas/workflow.py
backend/app/core/llm.py (call_structured)
tests/agents/
```

**PLAN rows:** F2, F3, F4, F7, F8.

**Tests added:** one test per specialist behaviour.

**Demo checkpoint:** each specialist can be run standalone against a sample ticket with the fake
provider.

**Exit criteria**

- [ ] Every specialist returns a Pydantic model — no free-text parsing
- [ ] No LLM call bypasses `call_structured`
- [ ] No tool call bypasses `ToolRegistry`
- [ ] `CustomerAgent` makes no LLM call
- [ ] `ResolutionAgent.plan_actions` is deterministic
- [ ] Rules outrank model output everywhere §7.2 says they do
- [ ] All prompts live in `agents/prompts.py`
- [ ] `agents/` writes no SQL directly

---

## Phase 9 — Workflow graph and trace

**Status:** not started

**Goal.** The LangGraph pipeline runs end to end for a low-risk ticket, saving state after every
node and emitting a full event trace.

**Files touched**

```text
agents/state.py · graph.py · checkpointer.py · nodes/
backend/app/services/workflow_service.py
backend/app/core/observability.py
backend/app/api/tickets.py (run, workflow, events) · agents.py
tests/workflow/test_graph_shape.py · test_routing.py · test_e2e_low_risk.py
```

**PLAN rows:** F13, and the orchestration half of F2–F8.

**Tests added:** graph shape, routing decisions, risk levels, end-to-end low-risk run.

**Demo checkpoint:** `make demo TICKET=CD-1003` runs understand → … → END with no approval pause.

**Exit criteria**

- [ ] Node order matches CLAUDE.md §7.3
- [ ] Every node returns a **partial** state dict
- [ ] `errors` and `completed_nodes` append; `token_usage` sums via `merge_usage`
- [ ] No large documents in reducer fields
- [ ] `POST /tickets/{id}/run` returns **202** with `{workflow_id}`
- [ ] State is saved after **every** node (`astream`), so polling at 2 s shows progress
- [ ] `assess_risk()` returns `high` for approval-required actions, policy escalation, critical
      severity, detected injection, or failed output validation
- [ ] `WorkflowTracer` writes all eight event types and never raises
- [ ] `InMemorySaver` when `CHECKPOINT_DB_PATH=:memory:`, `AsyncSqliteSaver` on a file
- [ ] `GRAPH_NODES` / `GRAPH_EDGES` are served by `GET /api/v1/agents`

---

## Phase 10 — Approval and escalation

**Status:** not started

**Goal.** The human gate works: pause, approve, resume — or reject and escalate.

**Files touched**

```text
agents/nodes/human_approval.py · escalation.py · execute_resolution.py
backend/app/services/approval_service.py · escalation_service.py
backend/app/api/approvals.py
tests/api/test_approvals.py · tests/workflow/test_pause_resume.py · test_escalation.py
```

**PLAN rows:** F9, F10.

**Tests added:** refund pause → approve → execute, rejection → escalation, security
auto-escalation, GDPR policy escalation, 409 on double-run and on resuming an unpaused run.

**Demo checkpoint:** `make demo` (CD-1002) pauses for approval in the terminal and completes on
approval.

**Exit criteria**

- [ ] `interrupt()` pauses the graph and the checkpointer stores state under `thread_id`
- [ ] Code **before** `interrupt()` is tiny and idempotent — it re-runs on resume
- [ ] `_handle_interrupt()` creates an `approval_requests` row and sets the ticket to
      `waiting_on_approval`
- [ ] Approve resumes via `Command(resume=…)` to `execute_resolution`; reject routes to
      `escalation`
- [ ] The same execution path serves auto-resolved and human-approved actions
- [ ] A `viewer` approving returns 403
- [ ] No refund, deletion or setting reset can execute without a recorded approval

---

## Phase 11 — Memory

**Status:** not started

**Goal.** Two tiers of memory, read before the run and written after it, with nothing sensitive
stored.

**Files touched**

```text
memory/short_term.py · long_term.py · memory_service.py
agents/nodes/customer_context.py (recall) · memory_update.py · ticket_summary.py
tests/unit/test_memory.py
```

**PLAN rows:** F11, N7.

**Tests added:** `scrub()` removes every `SECRET_PATTERNS` match, duplicates skipped, recall
returns at most 10 notes, TTLs applied.

**Demo checkpoint:** running CD-1004 twice — the second run shows the first run's memory note in
the customer context.

**Exit criteria**

- [ ] Short-term in Redis/fakeredis: conversation per ticket, workflow state, retrieval cache;
      24 h TTL, 300 s for the cache
- [ ] Long-term in `customer_memory`, permanent and de-duplicated
- [ ] Note types limited to `preference`, `past_issue`, `troubleshooting`, `note`
- [ ] `recall_customer()` returns up to 10 notes
- [ ] `record_resolution()` writes a past_issue, the first 3 troubleshooting steps and a
      resolution note
- [ ] Never stored: card numbers, API keys, passwords, raw ticket bodies, other customers' data

---

## Phase 12 — Agent console

**Status:** not started

**Goal.** The full Next.js console: one screen per job, one screen to resolve a ticket.

**Files touched**

```text
frontend/app/ (login, dashboard, tickets, tickets/[id], customers, customers/[id],
               knowledge, escalations, agents, audit, settings, api/health)
frontend/components/ui/ · layout/nav.ts
frontend/lib/api.ts · types.ts · hooks.ts · format.ts · cn.ts
frontend/__tests__/
```

**PLAN rows:** F12, and the presentation half of F13.

**Tests added:** `StatusPill`, `EmptyState`, `WorkflowSteps.deriveSteps`, api helpers.

**Demo checkpoint:** approve CD-1002's refund from the ticket screen and watch the workflow panel
complete.

**Exit criteria**

- [ ] The backend is reached **only** through `frontend/lib/api.ts`
- [ ] `types.ts` mirrors `API_CONTRACT.md`
- [ ] 401 redirects to `/login?reason=expired`; `NetworkError` shows a banner with auto-retry
- [ ] `usePolling` at 2 s on the ticket screen
- [ ] Ticket screen is the three-column grid with the 12-step workflow panel
- [ ] Approve/Reject render only when `approval_status === "pending"`
- [ ] A `viewer` sees disabled buttons (`canAct`)
- [ ] Nav is declared once in `components/layout/nav.ts`
- [ ] No UI library, no gradients
- [ ] The frontend never holds the service-role key

---

## Phase 13 — Evaluation and delivery

**Status:** not started

**Goal.** Measured quality, containers, infrastructure and CI — with an honest account of what
has and has not actually run.

**Files touched**

```text
datasets/eval_cases.json
tests/evaluation/ · tests/deployment/
backend/Dockerfile · frontend/Dockerfile · docker-compose.yml
deployment/{aws,azure,gcp}/ · kubernetes/ · docker/ · scripts/
.github/workflows/test.yml · security.yml · docker-build.yml · terraform-validate.yml · _deploy.yml
README.md · MEMORY.md
```

**PLAN rows:** N8, plus the threshold criteria of F2, F5, F8, F10.

**Tests added:** the five threshold metrics, compose service checks, Dockerfile hygiene
(non-root, HEALTHCHECK), `.env.example` coverage, no committed `.env`.

**Demo checkpoint:** `docker compose config -q && docker compose up --build`, then
`BASE_URL=http://localhost:8000 make smoke`.

**Exit criteria**

- [ ] All five evaluation thresholds met — they fail the build if not
- [ ] Every PLAN acceptance criterion maps to at least one named test
- [ ] Backend image: multi-stage, `python:3.12-slim`, non-root `app`, HEALTHCHECK on
      `/health/live`, built with context = repo root
- [ ] Frontend image: `node:22-alpine`, `output: "standalone"`, non-root, HEALTHCHECK on
      `/api/health`
- [ ] Compose wires frontend → backend → redis, qdrant with `depends_on: service_healthy`
- [ ] Terraform roots compose shared modules; environments are var-files, never copies of code
- [ ] Secrets only via `TF_VAR_*`; `backend.hcl` and `terraform.tfvars` git-ignored
- [ ] `--auto-approve` is refused by the scripts for staging and prod
- [ ] Image tags are the git SHA
- [ ] `MEMORY.md` honest status is accurate — nothing claimed as deployed or CI-green that is not

---

## Stage 17 — Agentic DevOps (optional)

Not a core exit criterion. `../deployment-agent/` is a separate LangGraph agent that ships this
project: it analyses a deploy request, runs read-only checks (CI status, Terraform plan),
classifies risk, asks a human, then calls **allow-listed scripts only**.

Rules if it is built: no `shell=True`, no LLM-composed commands, RBAC per role (`viewer` none ·
`developer` dev · `release_manager` dev/staging/prod · `admin` all), one session = one project +
cloud + environment, audit every decision.
