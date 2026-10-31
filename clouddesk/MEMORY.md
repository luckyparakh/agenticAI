# MEMORY.md — Locked facts and honest status

Facts that are settled and must not drift, the honest status of what actually works, and the log
of decisions taken. [CLAUDE.md](CLAUDE.md) is the source of truth for *how* the system is built;
this file records *what is true right now*.

Read this before starting a phase. Update it when a phase closes or a decision is made.

**Last updated:** 2026-10-31

---

## 1. Locked facts

Changing any of these is a breaking change. It needs a decision-log entry in §4, and the change
has to land in every place the fact appears.

### Enumerations

| Enum | Values | Defined in |
|---|---|---|
| Category (**exactly 10**) | `login_issue, billing, api_failure, workspace_permissions, storage_quota, integration, feature_request, account, security, other` | `backend/app/schemas/common.py` |
| Ticket status | `new, in_progress, waiting_on_customer, waiting_on_approval, escalated, resolved, closed` | `backend/app/schemas/common.py` |
| Severity | `low, medium, high, critical` | `backend/app/schemas/common.py` |
| Channel | `email, chat, web, api` | `backend/app/schemas/common.py` |
| Memory note type | `preference, past_issue, troubleshooting, note` | `memory/long_term.py` |

A new category is added to `common.py` **first**, then everywhere else.

### Roles

`viewer` (1) < `agent` (2) < `admin` (3), enforced by `require_role` in
`backend/app/core/security.py`.

| Role | Can do |
|---|---|
| `viewer` | read tickets, customers, knowledge, audit |
| `agent` | everything viewer can + run workflows, reply, approve/reject, escalate |
| `admin` | everything + reindex knowledge, settings |

Demo users: `admin@clouddesk.demo`, `sam.agent@clouddesk.demo`, `vic.viewer@clouddesk.demo`.

### Pipeline

```text
Understand → Classify → Investigate → Retrieve → Troubleshoot → Decide → Resolve → Act → Escalate → Remember
```

Graph node order:

```text
understand_ticket → classify_severity → customer_context → knowledge_retrieval → troubleshooting
  → resolution_planning → risk_check
      ├─ escalation_required          → escalation
      ├─ approval pending             → human_approval (interrupt) ─approved→ execute_resolution
      │                                                            └rejected→ escalation
      └─ low risk                     → execute_resolution
  → ticket_summary → memory_update → END
```

### Tool approval policy

| Tool | Writes? | Approval |
|---|---|---|
| `get_customer`, `get_subscription`, `get_ticket_history` | no | no |
| `search_docs` | no | no |
| `check_service_status` | no | no |
| `update_ticket` | tickets | no |
| `reset_demo_setting` | workspace admin | **yes** |
| `create_refund_request` | billing | **yes** |
| `create_escalation` | escalations | no — it is the safe path |

**Unknown tools always require approval.** `APPROVAL_REQUIRED_FOR_REFUNDS=true`,
`MAX_REFUND_WITHOUT_APPROVAL=0`.

### Middleware order

Request order, outermost first: **CORS → RequestId → RateLimit → Audit → route**.

Starlette wraps each `add_middleware` call *around* what is already installed, so
**the last one added is the outermost**. `app.main._add_middleware` therefore calls them in
reverse of the chain above. Getting this wrong is silent — nothing errors, the order is just
different — so change it only with that function's comment in view.

`ServerErrorMiddleware` sits outside all of them and cannot be reordered. That is why unhandled
exceptions are caught by an `Exception` handler instead (see the decision log).

### Evaluation thresholds — these fail the build

| Metric | Threshold |
|---|---|
| classification accuracy | ≥ 0.80 |
| retrieval hit-rate@3 | ≥ 0.75 |
| escalation correctness | ≥ 0.90 |
| citation rate | ≥ 0.90 |
| grounding rate | ≥ 0.90 |

### RAG constants

- Chunking: split on headings, then 900-char windows, 150-char overlap.
- Every chunk prefixed `"{title} - {heading}"`.
- Reciprocal rank fusion k = **60**. One hit per article.
- `FakeEmbeddings`: hashed bag-of-words, **384** dimensions.
- Retrieval cache key `rag:{mode}:{category}:{top_k}:{query}`, TTL 300 s.
- Short-term memory TTL 24 h.
- Default collection `clouddesk_knowledge`.

### Environment variables

Every one of these must appear in `.env.example` — `tests/deployment` asserts it.

```text
DEMO_MODE, ENVIRONMENT, CORS_ORIGINS, JWT_SECRET, SUPABASE_JWT_SECRET
DATABASE_URL, CHECKPOINT_DB_PATH, REDIS_URL, USE_FAKE_REDIS
LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
VECTOR_STORE, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION
APPROVAL_REQUIRED_FOR_REFUNDS, MAX_REFUND_WITHOUT_APPROVAL
TOOL_TIMEOUT_SECONDS, RATE_LIMIT_PER_MINUTE, SAMPLE_DATA_DIR
LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
```

### Test environment

`tests/conftest.py` sets these **before** importing the app: `DEMO_MODE=true`,
`LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `USE_FAKE_REDIS=true`, a temp SQLite DB,
`CHECKPOINT_DB_PATH=:memory:`. Fixtures: `agent_headers`, `admin_headers`, `viewer_headers`.

pytest: `asyncio_mode = "auto"`, `loop_scope = "session"` in `pyproject.toml`. Do not mix in
`@pytest.mark.asyncio` with a different scope.

### Things that must never happen

- A customer reply containing internal URLs, secrets, or another customer's data.
- A refund, deletion or setting reset executed without a recorded approval.
- A `viewer` able to approve, reply, or run a workflow — it must return 403.
- A prompt-injected instruction from ticket text changing the workflow. CD-1013 must never
  execute an export.
- Memory notes containing card numbers, keys, passwords, or raw ticket bodies.
- Deploying prod with the dev var-file, or applying without a reviewed plan.

---

## 2. Honest status

The four states are distinct. Never collapse them into "done" (CLAUDE.md §15.1).

| Term | Means |
|---|---|
| implemented | code exists and is committed |
| validated locally | `make test` / `make demo` ran green on a dev machine |
| needs cloud credentials | cannot be verified without a real account |
| actually deployed | applied to a real environment and smoke-tested |

### As of 2026-10-31

| Area | Status |
|---|---|
| Specification (`CLAUDE.md`) | written |
| Planning docs (`PLAN.md`, `PLAN_PHASE.md`, `TASKS.md`, this file) | written |
| Agent skills (`.claude/skills/`) | written |
| `docs/API_CONTRACT.md`, `docs/ARCHITECTURE.md` | written — **specification only, no code implements them yet** |
| Backend application code | **in progress** — `core/{config,logging,health}.py`, `main.py`, `api/health.py`, `middleware/request_id.py`, `schemas/health.py` (P1-1, P1-2). No `agents/`, `rag/`, `memory/`, `integrations/` directories yet. |
| Health endpoints | **validated locally** — all three respond; verified against a running uvicorn, not only via TestClient. `/health/ready` honestly reports all four components as `not_configured` because none of them exist yet. |
| Frontend | **not started** |
| Database schema / sample data | **not started** |
| Tests | **validated locally** for P1-1 and P1-2 — 111 tests, `uv run pytest` green in ~1.2 s offline. No `Makefile` yet, so `make test` itself does not exist (P1-4). |
| Containers, Terraform, CI workflows | **not started** |
| Cloud deployment | **no cloud credentials used; nothing applied to any real account** |
| GitHub Actions | **never executed** — no workflow files exist and the repo has not been pushed with secrets configured |

What exists on disk today under `clouddesk/`: `CLAUDE.md`, the planning and docs files,
`pyproject.toml` + `uv.lock`, `backend/app/core/{config,logging}.py`, `tests/unit/`, and
`docs/Git_Github_Workflow_Guide.md`.

Nothing in `PLAN.md` is fully implemented. Every F-row and N-row is `not started`; P1-1 is
groundwork for F14 but does not close it, because the fake LLM provider (P1-4 / `core/llm.py`)
does not exist yet.

---

## 3. Known discrepancies — unresolved

These are real conflicts between documents and reality. Do not paper over them; resolve each
with a decision and record it in §4.

| # | Discrepancy | Detail |
|---|---|---|
| D7 | **Table count** | CLAUDE.md §20 notes the database doc says 16 tables while RLS covers 15 data tables. `database/schema.sql` is the authority once written. |
| D8 | **Missing README source** | CLAUDE.md §20: the Project 1 `README.md` referenced by the course documents was never supplied, so the §14 command list is taken from stage docs and is unverified. |
| D9 | **External directories** | The course documents reference `../docs/…`, `../deployment-agent/…` and `../shared-infrastructure/…`, which sit outside the project. Undecided whether they are copied in or referenced. |

---

## 4. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-10-31 | Agent skills live in `clouddesk/.claude/skills/`, not `.cursor/skills/` | Claude Code is the harness in use; this location is auto-discovered. Scoped to `clouddesk/` so it does not apply to `lectures/`. CLAUDE.md §19 updated to match. |
| 2026-10-31 | The project root stays `clouddesk/`, not `project-01-customer-support/` | Already created, matches the product name. CLAUDE.md §4.3 updated to match. |
| 2026-10-31 | `docs/API_CONTRACT.md` is written in full up front | It is the contract each phase implements against, so it must exist before the code. Expect revisions as phases land; revise the contract first, then the code. |
| 2026-10-31 | Directory skeletons are **not** pre-created | `backend/`, `agents/`, `rag/` and the rest are created by the phase that needs them, so nothing is committed hollow. |
| 2026-10-31 | **The remote is `https://github.com/luckyparakh/agenticAI.git`** (closes D1) | Confirmed by the user as the repository in use. The `anulsasidharan/CloudDesk.git` URL in the course materials is not used. CLAUDE.md §14 and the Git guide updated. |
| 2026-10-31 | **The repository is a monorepo** (closes D3) | It will hold roughly three projects of CloudDesk's size plus `lectures/`. CloudDesk is the `clouddesk/` directory. The branch model is repository-wide, not per project; branch names carry the project once a second one exists (`feature/clouddesk-<name>`). |
| 2026-10-31 | **The remote is live, not empty** (closes D4) | Three commits exist (`01bcb53`, `e860cc8`, `a6bcf03`) and `origin/main`, `origin/development`, `origin/test` are all present. The Git guide's "empty as of 2026-10-23" section 3 was stale and has been rewritten as a clone-and-verify procedure. |
| 2026-10-31 | **The promotion branch is named `testing`, not `test`** (closes D2) | Rename performed and verified: `testing` exists locally and on the remote, `test` is gone on both, and `origin/HEAD` still points at `main`. The old branch carried no commits that were not already in `development`, so nothing was lost. |
| 2026-10-31 | **Git guide reference corrected** (closes D6) | CLAUDE.md §14 pointed at `Git_GitHub_Workflow_Guide.docx`; the file on disk is `docs/Git_Github_Workflow_Guide.md` and §14 now links to it. The guide's own reading-list row pointing at `.cursor/skills/…` was corrected to `.claude/skills/…` at the same time. |
| 2026-10-31 | **The project is an application, not a package** (closes D5, P1-1) | Removed the `uv init` scaffold (`src/clouddesk/__init__.py`, a 2-line hello-world) along with `[project.scripts]` and the `uv_build` backend. `pyproject.toml` now sets `[tool.uv] package = false` and declares the import roots via `pythonpath = ["backend", "."]`, matching CLAUDE.md §4.3. `langchain` was kept in dependencies to avoid churning `uv.lock` before Phase 9 needs it. |
| 2026-10-31 | **A handler for `Exception` is registered, not just middleware** (P1-2) | Starlette's `ServerErrorMiddleware` is the outermost layer, *outside* all user middleware, so the 500 it builds never passes through `RequestIdMiddleware`. Without the handler a 500 returns `text/plain` and **no `X-Request-ID`** — breaking the `{"detail": ...}` error shape (§10) and N3 on the one response where correlation matters most. Caught by a test, not by review. |
| 2026-10-31 | **`/health/ready` reports `not_configured`, never a fake `ok`** (P1-2) | `backend/app/core/health.py` is a registry; each component registers its check when its phase lands (database P2-3, redis P3-3, vector store P5-2, llm P9-1). Until then the component reports `not_configured`, which does **not** block readiness. A health endpoint that claims a database is `ok` before one exists is the worst possible place to be dishonest. |
| 2026-10-31 | **`RequestIdMiddleware` is pure ASGI, not `BaseHTTPMiddleware`** (P1-2) | It wraps `send`, so the header is attached to the response message itself and survives on 404s, 405s and validation errors that the application never returns itself. The incoming header is also sanitised (charset + 128-char limit) because it is echoed back and written into every log line for that request — an unchecked value is a log-injection vector. |
| 2026-10-31 | **`setup_logging()` rebuilds rather than returning early** (P1-2) | A `StreamHandler` binds whatever `sys.stdout` was at construction. Returning early on a second call left the old stream attached, which broke P1-1's logging tests the moment the API tests started calling `setup_logging()` first via the app lifespan. Still idempotent in the sense that matters: exactly one handler, never duplicated output. |
| 2026-10-31 | **Log level is derived, not configured** (P1-1) | `DEBUG` in demo mode, `INFO` in production, as a property on `Settings`. Avoids adding a `LOG_LEVEL` env var that CLAUDE.md §10.1 does not list, since `.env.example` must cover every variable. |
| 2026-10-31 | **`MAX_REFUND_WITHOUT_APPROVAL` is a `Decimal`** (P1-1) | It is money, compared against refund amounts. A float cannot represent `10.10` exactly, and this value gates whether a human sees a refund (F9). |
| 2026-10-31 | **`TASKS.md` is the course's own version, not the generated one** | The generated tracker numbered sub-tasks `1.1`/`4.2` with its own branch names, which contradicted `docs/Git_Github_Workflow_Guide.md` — already in the repo and written against `P1-1 · feature/backend-config-logging`. The course version is authoritative and uses the `P<phase>-<n>` scheme the guide expects. The generated file has been deleted and is recoverable from git history. Consequence: `TASKS.md` has **14** execution phases against this spec's **13** — see its "Map to `PLAN_PHASE.md`" table and the warning at the top of `PLAN_PHASE.md`. |

---

## 5. Branch model

Three long-lived branches. Feature work targets `development` only.

| Branch | Purpose | Represents |
|---|---|---|
| `development` | integration branch for active work | dev / integration, not a deploy |
| `testing` | QA and staging validation | staging |
| `main` | code allowed to ship | production candidate; a merge is not a deploy |

- Every feature branch is cut from an up-to-date `development`.
- Every feature PR opens into `development`, never into `testing` or `main`.
- No direct pushes to `development`, `testing` or `main`.
- No stacking a feature branch on another feature branch.
- One sub-task in [TASKS.md](TASKS.md) = one branch = one PR = one ✅ after merge.
- A merge to `main` does **not** mean anything is deployed. This file stays honest until a real
  apply has happened.

Full procedure: [docs/Git_Github_Workflow_Guide.md](docs/Git_Github_Workflow_Guide.md).
