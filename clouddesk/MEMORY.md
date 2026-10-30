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

Outermost last: **CORS → RequestId → RateLimit → Audit**.

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
| Backend application code | **not started** — no `backend/`, `agents/`, `rag/`, `memory/`, `integrations/` directories exist |
| Frontend | **not started** |
| Database schema / sample data | **not started** |
| Tests | **not started** — `make test` has never been run because there is nothing to run |
| Containers, Terraform, CI workflows | **not started** |
| Cloud deployment | **no cloud credentials used; nothing applied to any real account** |
| GitHub Actions | **never executed** — no workflow files exist and the repo has not been pushed with secrets configured |

What exists on disk today under `clouddesk/`: `CLAUDE.md`, the planning and docs files, a
`uv init` scaffold (`pyproject.toml`, `uv.lock`, `src/clouddesk/__init__.py`, `.python-version`,
`.venv/`), and `docs/Git_Github_Workflow_Guide.md`.

Nothing in `PLAN.md` is implemented. Every F-row and N-row is `not started` except where
phase 1 is partially underway.

---

## 3. Known discrepancies — unresolved

These are real conflicts between documents and reality. Do not paper over them; resolve each
with a decision and record it in §4.

| # | Discrepancy | Detail |
|---|---|---|
| D2 | **Promotion branch name** — *decided, action pending* | Resolved in favour of `testing`. The branch on the remote is still named `test`; the rename to `testing` has **not** been performed yet. Until it is, the docs describe `testing` and the remote has `test`. |
| D5 | **Python project layout** | `pyproject.toml` is a `uv init` default with a `src/clouddesk/` package layout, a `[project.scripts]` entry and `langchain` as the only dependency. CLAUDE.md §4.3 specifies a `backend/app/` + `agents/` + `rag/` application layout. These are incompatible. |
| D6 | **Git guide file format** | CLAUDE.md §14 refers to `Git_GitHub_Workflow_Guide.docx`; the file on disk is `docs/Git_Github_Workflow_Guide.md`. |
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
| 2026-10-31 | **The promotion branch is named `testing`, not `test`** (D2, action pending) | The guide, CLAUDE.md, MEMORY.md and TASKS.md all say `testing`. The rename of the actual branch has not been run yet — see D2. |

---

## 5. Branch model

Three long-lived branches. Feature work targets `development` only.

| Branch | Purpose | Represents |
|---|---|---|
| `development` | integration branch for active work | dev / integration, not a deploy |
| `testing` (still named `test` on the remote until the rename is run — see D2) | QA and staging validation | staging |
| `main` | code allowed to ship | production candidate; a merge is not a deploy |

- Every feature branch is cut from an up-to-date `development`.
- Every feature PR opens into `development`, never into `testing` or `main`.
- No direct pushes to `development`, `testing` or `main`.
- No stacking a feature branch on another feature branch.
- One sub-task in [TASKS.md](TASKS.md) = one branch = one PR = one ✅ after merge.
- A merge to `main` does **not** mean anything is deployed. This file stays honest until a real
  apply has happened.

Full procedure: [docs/Git_Github_Workflow_Guide.md](docs/Git_Github_Workflow_Guide.md).
