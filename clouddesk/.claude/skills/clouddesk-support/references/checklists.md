# Checklists

## Definition of done for any change

- [ ] A PLAN.md row (F1–F14 or N1–N8) is named in the commit message
- [ ] A test exists that fails without the change
- [ ] `make test` passes offline — no API key, no Docker, no network
- [ ] `make lint` (ruff) clean; `npm run lint` clean if the frontend changed
- [ ] `make demo` still completes, pausing for approval on CD-1002
- [ ] `.env.example` lists every new variable (asserted by `tests/deployment`)
- [ ] `MEMORY.md` honest status updated
- [ ] No hard stop from SKILL.md §4 is now reachable

## Changing an endpoint

- [ ] `docs/API_CONTRACT.md` updated — method, path, role, request, response, status codes
- [ ] `backend/app/schemas/` matches
- [ ] `frontend/lib/types.ts` matches
- [ ] RBAC: which of `viewer` / `agent` / `admin` may call it, and a 403 test for the role below
- [ ] An `tests/api/` test for the happy path and for each named error code

## Adding or changing a tool

- [ ] `async def`, decorated with `@tool`
- [ ] The docstring is written for the LLM and MCP clients to read — it is the description
- [ ] Declared in `ToolRegistry`; execution goes only through `ToolRegistry.execute()`
- [ ] Approval flag set in `ToolPolicy`; unknown tools default to requiring approval
- [ ] Honours `TOOL_TIMEOUT_SECONDS`
- [ ] Exceptions become `ToolResult(ok=False)` — a tool failure never crashes the graph
- [ ] A `tests/unit/` test asserting the approval decision
- [ ] If it writes money or account state, a `tests/api/` pause→approve test

Current policy (CLAUDE.md §7.4):

| Tool | Writes? | Approval |
|---|---|---|
| `get_customer`, `get_subscription`, `get_ticket_history` | no | no |
| `search_docs` | no | no |
| `check_service_status` | no | no |
| `update_ticket` | tickets | no |
| `reset_demo_setting` | workspace admin | **yes** |
| `create_refund_request` | billing | **yes** |
| `create_escalation` | escalations | no (it is the safe path) |

## Adding a node

- [ ] File in `agents/nodes/`, following the node shape
- [ ] Returns a partial dict including `completed_nodes: [NODE]` and `current_node: NODE`
- [ ] `GRAPH_NODES` and `GRAPH_EDGES` updated (served by `GET /api/v1/agents`)
- [ ] Frontend workflow panel step list updated
- [ ] `tests/workflow/` graph-shape test updated
- [ ] If it runs before `interrupt()`, it is tiny and idempotent

## Touching guardrails

- [ ] `scan_for_injection` still flags CD-1013
- [ ] `wrap_untrusted` applied to every external text source
- [ ] `validate_customer_output` still blocks internal URLs, secrets and other customers' data
- [ ] A validation failure still raises risk to `high`
- [ ] `tests/unit/` and the `tests/api/` injection-containment test still pass

## Touching memory

- [ ] Every note passes through `scrub()`
- [ ] Exact-duplicate notes are skipped
- [ ] Nothing stored from `SECRET_PATTERNS`: card numbers, API keys, passwords
- [ ] No raw ticket bodies, nothing about other customers
- [ ] Note type is one of `preference`, `past_issue`, `troubleshooting`, `note`

## Touching RAG

- [ ] Chunking still prefixes `"{title} - {heading}"`
- [ ] Nothing outside `rag/` knows which vector store is in use
- [ ] Evidence shape unchanged: `{ id, title, source, snippet, score, url, article_id }`
- [ ] If the embedding model changed, `POST /knowledge/reindex` is required — say so
- [ ] `tests/rag/` expected-article assertions still pass

## Before a commit

- [ ] Branch is `feature/<name>` or `bugfix/<name>`, cut from an up-to-date `development`
- [ ] PR targets `development`, never `testing` or `main`
- [ ] One sub-task in `TASKS.md` → one branch → one PR → mark Completed after merge
- [ ] No `.env`, `data/`, `*.db`, `terraform.tfvars`, `backend.hcl`, `tfplan`, or real key staged

## Evaluation thresholds — these fail the build

| Metric | Threshold |
|---|---|
| classification accuracy | ≥ 0.80 |
| retrieval hit-rate@3 | ≥ 0.75 |
| escalation correctness | ≥ 0.90 |
| citation rate | ≥ 0.90 |
| grounding rate (steps present in reply) | ≥ 0.90 |

## Honest status vocabulary

Never collapse these four into "done" (CLAUDE.md §15.1):

| Term | Means |
|---|---|
| implemented | code exists and is committed |
| validated locally | `make test` / `make demo` ran green on a dev machine |
| needs cloud credentials | cannot be verified without a real account |
| actually deployed | applied to a real environment and smoke-tested |
