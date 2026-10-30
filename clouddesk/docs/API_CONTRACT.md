# API_CONTRACT.md

The source of truth for every route and type in CloudDesk. Not the code, not the frontend — this
file. If an endpoint changes, this file, `backend/app/schemas/` and `frontend/lib/types.ts`
change in the **same commit** (CLAUDE.md §12).

**Status:** specification. No code implements this yet — see [MEMORY.md](../MEMORY.md) §2.
Written up front so each phase has a contract to build against. Revise the contract first, then
the code.

**Base URL:** `/api/v1` for everything except the three health routes, which are unprefixed.

---

## 1. Conventions

### Authentication

Every route except `/health*` and `POST /api/v1/auth/login` requires:

```http
Authorization: Bearer <jwt>
```

HS256 via PyJWT, verified against `settings.effective_jwt_secret` (the Supabase JWT secret when
set, so Supabase-issued tokens work unchanged). Demo tokens expire in 8 hours.

### Roles

`viewer` (1) < `agent` (2) < `admin` (3), enforced by `require_role`. Each route below states
its **minimum** role.

### Headers

| Header | Direction | Notes |
|---|---|---|
| `Authorization: Bearer <jwt>` | request | required except where stated |
| `X-Request-ID` | both | read from the request if present, generated otherwise; returned on **every** response and exposed through CORS |

### Errors

Every error body is:

```json
{ "detail": "string" }
```

| Code | Meaning in this API |
|---|---|
| `400` | malformed request that is not a schema violation |
| `401` | missing, invalid or expired token |
| `403` | authenticated but the role is insufficient |
| `404` | resource does not exist |
| `409` | the ticket is already `waiting_on_approval`, **or** the run being resumed is not paused |
| `422` | request body failed schema validation (FastAPI default shape) |
| `429` | rate limit exceeded — fixed window per client, `RATE_LIMIT_PER_MINUTE` |

### Pagination

List routes accept `limit` (default 50, max 200) and `offset` (default 0), and return:

```json
{ "items": [ ... ], "total": 0, "limit": 50, "offset": 0 }
```

### Audit

Every non-GET request writes an `audit_logs` row (N6).

---

## 2. Shared types

```ts
type Category =
  | "login_issue" | "billing" | "api_failure" | "workspace_permissions" | "storage_quota"
  | "integration" | "feature_request" | "account" | "security" | "other";   // exactly 10

type TicketStatus =
  | "new" | "in_progress" | "waiting_on_customer" | "waiting_on_approval"
  | "escalated" | "resolved" | "closed";

type Severity = "low" | "medium" | "high" | "critical";
type Channel  = "email" | "chat" | "web" | "api";
type Role     = "viewer" | "agent" | "admin";

type RiskLevel      = "low" | "medium" | "high";
type ApprovalStatus = "pending" | "approved" | "rejected";
type WorkflowStatus = "pending" | "running" | "paused" | "completed" | "failed";
type MemoryNoteType = "preference" | "past_issue" | "troubleshooting" | "note";

type WorkflowEventType =
  | "node_started" | "node_completed" | "tool_called" | "llm_called"
  | "approval_requested" | "approval_resolved" | "error" | "workflow_completed";
```

```ts
interface Evidence {
  id: string;
  title: string;
  source: string;      // "kb://slug#section"
  snippet: string;
  score: number;
  url: string;         // "/knowledge/<id>"
  article_id: string;
}

interface PreviousCase {
  ticket_id: string;
  subject: string;
  category: Category;
  resolution: string;
  similarity: number;
}

interface Diagnosis {
  probable_causes: string[];
  steps: string[];          // numbered in presentation order
  confidence: number;       // 0..1
  service_status: string | null;
}

interface PlannedAction {
  tool: string;
  args: Record<string, unknown>;
  requires_approval: boolean;
  reason: string;
}

interface ResolutionPlan {
  summary: string;
  customer_reply: string;
  internal_notes: string;
  actions: PlannedAction[];
}

interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;   // 0.0 for the fake provider
}
```

---

## 3. Health

Unprefixed. No authentication.

### `GET /health`

`200` → `{ "status": "ok", "version": string, "environment": string }`

### `GET /health/live`

Liveness probe. **Performs no I/O.** `200` → `{ "status": "alive" }`

### `GET /health/ready`

Readiness probe. Checks database, Redis, vector store and LLM provider.

`200` or `503` →

```json
{
  "status": "ready",
  "checks": { "database": "ok", "redis": "ok", "vector_store": "ok", "llm": "ok" }
}
```

---

## 4. Auth

### `POST /api/v1/auth/login`

No authentication required.

Request:

```json
{ "email": "sam.agent@clouddesk.demo", "password": "<PASSWORD>" }
```

`200` →

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": { "id": "...", "email": "...", "full_name": "...", "role": "agent" }
}
```

Errors: `401` invalid credentials, `422`, `429`.

### `GET /api/v1/auth/me`

Minimum role: `viewer`.

`200` → the `user` object above. Errors: `401`.

---

## 5. Dashboard

### `GET /api/v1/dashboard/summary`

Minimum role: `viewer`.

`200` →

```json
{
  "tickets": { "total": 13, "new": 4, "in_progress": 2, "waiting_on_approval": 1,
               "escalated": 3, "resolved": 3, "closed": 0 },
  "by_severity": { "low": 2, "medium": 5, "high": 4, "critical": 2 },
  "by_category": { "login_issue": 2, "billing": 2, "...": 0 },
  "pending_approvals": 1,
  "open_escalations": 3,
  "runs_last_24h": 0
}
```

Errors: `401`, `403`.

---

## 6. Tickets

### `GET /api/v1/tickets`

Minimum role: `viewer`. Paginated.

Query: `status`, `severity`, `category`, `customer_id`, `q` (subject search), `limit`, `offset`.

`200` → `{ "items": TicketSummary[], "total": n, "limit": n, "offset": n }`

```ts
interface TicketSummary {
  id: string;                   // "CD-1002"
  subject: string;
  status: TicketStatus;
  severity: Severity | null;
  category: Category | null;
  channel: Channel;
  customer_id: string;
  customer_name: string;
  created_at: string;           // ISO 8601
  updated_at: string;
}
```

### `POST /api/v1/tickets`

Minimum role: `agent`. **F1.**

Request:

```json
{
  "subject": "Refund: charged 8 seats, uses 5",
  "body": "string",
  "channel": "email",
  "customer_id": "<CUSTOMER_ID>",
  "category": null,
  "severity": null
}
```

`category` and `severity` are optional — the workflow sets them. A new ticket starts at status
`new`.

`201` → `Ticket`. Errors: `401`, `403` (viewer), `404` (unknown customer), `422`, `429`.

### `GET /api/v1/tickets/{id}`

Minimum role: `viewer`.

`200` →

```ts
interface Ticket extends TicketSummary {
  body: string;
  summary: string | null;             // F11, set by ticket_summary
  severity_reason: string | null;
  assigned_to: string | null;
  messages: TicketMessage[];
  customer: CustomerSummary;
  latest_workflow_id: string | null;
  approval_status: ApprovalStatus | null;
  escalation_id: string | null;
  resolved_at: string | null;
}

interface TicketMessage {
  id: string;
  ticket_id: string;
  author_type: "customer" | "agent" | "system";
  author_name: string;
  body: string;
  created_at: string;
}
```

Errors: `401`, `404`.

### `PATCH /api/v1/tickets/{id}`

Minimum role: `agent`.

Request — all fields optional: `{ status, severity, category, assigned_to }`

`200` → `Ticket`. Errors: `401`, `403`, `404`, `422`.

### `POST /api/v1/tickets/{id}/run`

Minimum role: `agent`. Starts the LangGraph workflow as a background task. **F13.**

Request: none, or `{ "force": false }`.

`202` → `{ "workflow_id": "<uuid>", "ticket_id": "CD-1002", "status": "pending" }`

Errors: `401`, `403`, `404`, **`409`** when the ticket is already `waiting_on_approval` or a run
is already active, `429`.

### `GET /api/v1/tickets/{id}/workflow`

Minimum role: `viewer`. Polled by the UI every 2 s.

`200` →

```ts
interface WorkflowRun {
  workflow_id: string;
  ticket_id: string;
  status: WorkflowStatus;
  current_node: string | null;
  completed_nodes: string[];        // node ids the frontend renders as steps
  risk_level: RiskLevel | null;
  approval_status: ApprovalStatus | null;
  approval_request_id: string | null;
  classification: { category: Category; summary: string; confidence: number } | null;
  severity: { level: Severity; reason: string } | null;
  customer_context: Record<string, unknown> | null;
  evidence: Evidence[];
  previous_cases: PreviousCase[];
  diagnosis: Diagnosis | null;
  resolution_plan: ResolutionPlan | null;
  escalation: EscalationDecision | null;
  injection_detected: boolean;
  output_validation_passed: boolean | null;
  token_usage: TokenUsage;
  errors: string[];
  started_at: string;
  completed_at: string | null;
}
```

Returns `404` if the ticket has never been run.

### `GET /api/v1/tickets/{id}/events`

Minimum role: `viewer`. The full inspectable trace. **F13.**

Query: `workflow_id` (defaults to the latest run), `type`, `limit`, `offset`.

`200` → `{ "items": WorkflowEvent[], "total": n, "limit": n, "offset": n }`

```ts
interface WorkflowEvent {
  id: string;
  workflow_id: string;
  ticket_id: string;
  type: WorkflowEventType;
  node: string | null;
  name: string | null;              // tool name, or the structured-output label
  duration_ms: number | null;
  token_usage: TokenUsage | null;
  payload: Record<string, unknown>; // tool args/results, evidence scores, error text
  created_at: string;
}
```

`payload` **never** contains raw prompts, hidden chain-of-thought, other customers' data, or
secrets (CLAUDE.md §16).

### `POST /api/v1/tickets/{id}/reply`

Minimum role: `agent`. Sends the agent-approved reply. Mocked — no real email is sent.

Request: `{ "body": "string", "mark_resolved": false }`

`201` → `TicketMessage`. Errors: `401`, `403`, `404`, `422`.

The body passes `validate_customer_output` before it is accepted (N5); a failure is `400` with
the reason in `detail`.

### `POST /api/v1/tickets/{id}/request-info`

Minimum role: `agent`. Sets the ticket to `waiting_on_customer`.

Request: `{ "body": "string" }`

`201` → `TicketMessage`. Errors: `401`, `403`, `404`, `422`.

### `POST /api/v1/tickets/{id}/escalate`

Minimum role: `agent`. Manual escalation by a human.

Request: `{ "team": "string", "reason": "string" }`

`201` → `Escalation`. Errors: `401`, `403`, `404`, `422`.

---

## 7. Approvals

### `GET /api/v1/approvals`

Minimum role: `viewer`. Paginated. Query: `status`, `ticket_id`, `limit`, `offset`.

`200` → `{ "items": ApprovalRequest[], "total": n, ... }`

```ts
interface ApprovalRequest {
  id: string;
  ticket_id: string;
  workflow_id: string;
  status: ApprovalStatus;
  action: PlannedAction;
  risk_level: RiskLevel;
  reason: string;
  requested_at: string;
  decided_at: string | null;
  decided_by: string | null;
  decision_note: string | null;
}
```

### `GET /api/v1/approvals/{id}`

Minimum role: `viewer`. `200` → `ApprovalRequest`. Errors: `401`, `404`.

### `POST /api/v1/approvals/{id}/approve`

Minimum role: `agent`. **F9.** Resumes the paused graph via `Command(resume=…)` →
`execute_resolution`.

Request: `{ "note": "string | null" }`

`200` → `{ "approval": ApprovalRequest, "workflow_id": "...", "status": "running" }`

Errors: `401`, `403` (viewer), `404`, **`409`** when the approval is already decided or the run
is not paused, `422`.

### `POST /api/v1/approvals/{id}/reject`

Minimum role: `agent`. Resumes the graph down the `escalation` branch.

Request: `{ "note": "string | null" }`

`200` → same shape as approve. Errors: as approve.

---

## 8. Customers

### `GET /api/v1/customers`

Minimum role: `viewer`. Paginated. Query: `q`, `plan`, `limit`, `offset`.

`200` → `{ "items": CustomerSummary[], "total": n, ... }`

```ts
interface CustomerSummary {
  id: string;
  name: string;
  email: string;
  company: string | null;
  plan: "free" | "pro" | "business" | "enterprise";
  created_at: string;
}
```

### `GET /api/v1/customers/{id}`

Minimum role: `viewer`. **F4.**

`200` →

```ts
interface Customer extends CustomerSummary {
  subscription: {
    plan: string; seats: number; seats_used: number;
    status: string; renews_at: string | null; mrr: number;
  } | null;
  workspaces: { id: string; name: string; storage_used_gb: number; storage_limit_gb: number }[];
  tickets: TicketSummary[];
  memory_notes: {
    id: string; type: MemoryNoteType; content: string; created_at: string;
  }[];                                   // scrubbed; never contains secrets (N7)
}
```

Errors: `401`, `404`.

---

## 9. Knowledge

### `GET /api/v1/knowledge`

Minimum role: `viewer`. Paginated. Query: `category`, `tag`, `limit`, `offset`.

`200` → `{ "items": ArticleSummary[], "total": n, ... }`

```ts
interface ArticleSummary {
  id: string; slug: string; title: string;
  category: Category; tags: string[]; summary: string; updated_at: string;
}
```

### `GET /api/v1/knowledge/{id}`

Minimum role: `viewer`. `200` → `ArticleSummary & { body: string }` (Markdown). Errors: `404`.

### `GET /api/v1/knowledge/search`

Minimum role: `viewer`. **F5.**

Query: `q` (required), `mode` ∈ `hybrid` (default) | `semantic` | `keyword`, `category`,
`top_k` (default 5, max 20).

`200` →

```json
{ "query": "...", "mode": "hybrid", "results": [ /* Evidence[] */ ], "took_ms": 0, "cached": false }
```

Results are one hit per article. Errors: `401`, `422`.

### `POST /api/v1/knowledge/reindex`

Minimum role: **`admin`**. Recreates the collection and re-ingests. Required after an embedding
model change.

Request: none.

`202` → `{ "status": "reindexing", "articles": 15, "chunks": 0 }`

Errors: `401`, `403` (agent and viewer both), `429`.

---

## 10. Escalations

### `GET /api/v1/escalations`

Minimum role: `viewer`. Paginated. Query: `status`, `team`, `ticket_id`, `limit`, `offset`.

`200` → `{ "items": Escalation[], "total": n, ... }`

```ts
interface Escalation {
  id: string;
  ticket_id: string;
  workflow_id: string | null;
  team: string;                   // the named team the policy rule routes to
  reason: string;
  rule_matched: string | null;    // null when a human escalated manually
  status: "open" | "acknowledged" | "closed";
  created_at: string;
  created_by: string;             // user id, or "system"
}

interface EscalationDecision {
  escalation_required: boolean;
  team: string | null;
  reason: string;
  rule_matched: string | null;
  confidence: number;
}
```

### `GET /api/v1/escalations/{id}`

Minimum role: `viewer`. `200` → `Escalation`. Errors: `401`, `404`.

---

## 11. Agents

### `GET /api/v1/agents`

Minimum role: `viewer`. Serves `GRAPH_NODES` and `GRAPH_EDGES` so the UI can render the graph.

`200` →

```json
{
  "nodes": [
    { "id": "understand_ticket", "label": "Understand", "agent": "Support Supervisor",
      "output_schema": "Classification", "tools": [] }
  ],
  "edges": [ { "from": "understand_ticket", "to": "classify_severity", "condition": null } ],
  "agents": [
    { "name": "Support Supervisor",
      "nodes": ["understand_ticket", "classify_severity", "ticket_summary"],
      "tools": [], "rules": ["rule_category", "rule_severity", "scan_for_injection"] }
  ]
}
```

Errors: `401`.

---

## 12. Audit

### `GET /api/v1/audit`

Minimum role: `viewer`. Paginated. Query: `user_id`, `method`, `path`, `since`, `until`,
`limit`, `offset`.

`200` → `{ "items": AuditLog[], "total": n, ... }`

```ts
interface AuditLog {
  id: string;
  request_id: string;
  user_id: string | null;
  user_email: string | null;
  method: string;              // non-GET only
  path: string;
  status_code: number;
  resource_type: string | null;
  resource_id: string | null;
  created_at: string;
}
```

---

## 13. Settings

### `GET /api/v1/settings`

Minimum role: `viewer`. Read-only view of operational settings. **Never returns a secret value** —
keys are reported as configured or not.

`200` →

```json
{
  "demo_mode": true,
  "environment": "development",
  "llm_provider": "fake",
  "llm_model": "fake",
  "llm_key_configured": false,
  "embedding_provider": "fake",
  "vector_store": "memory",
  "qdrant_collection": "clouddesk_knowledge",
  "approval_required_for_refunds": true,
  "max_refund_without_approval": 0,
  "tool_timeout_seconds": 30,
  "rate_limit_per_minute": 120,
  "langsmith_enabled": false
}
```

### `PATCH /api/v1/settings`

Minimum role: **`admin`**. Only the runtime-adjustable subset.

Request — all optional: `{ approval_required_for_refunds, max_refund_without_approval, rate_limit_per_minute }`

`200` → the `GET /settings` body. Errors: `401`, `403`, `422`.

Secrets are never settable over the API. They come from the environment only.

---

## 14. MCP

### `GET /api/v1/mcp/tools`

Minimum role: `viewer`. Describes the tools the MCP server exposes. The `description` is each
tool's docstring — it is what the LLM and MCP clients read.

`200` →

```json
{
  "tools": [
    { "name": "get_customer", "description": "...",
      "input_schema": { "type": "object", "properties": {} },
      "read_only": true, "requires_approval": false }
  ]
}
```

Only read-only tools are exposed over MCP.

---

## 15. Route summary

| Method | Path | Min role | Codes | Row |
|---|---|---|---|---|
| GET | `/health` | — | 200 | — |
| GET | `/health/live` | — | 200 | — |
| GET | `/health/ready` | — | 200, 503 | — |
| POST | `/api/v1/auth/login` | — | 200, 401, 422, 429 | N1 |
| GET | `/api/v1/auth/me` | viewer | 200, 401 | N1 |
| GET | `/api/v1/dashboard/summary` | viewer | 200, 401 | — |
| GET | `/api/v1/tickets` | viewer | 200, 401 | — |
| POST | `/api/v1/tickets` | agent | 201, 401, 403, 404, 422 | F1 |
| GET | `/api/v1/tickets/{id}` | viewer | 200, 401, 404 | — |
| PATCH | `/api/v1/tickets/{id}` | agent | 200, 401, 403, 404, 422 | — |
| POST | `/api/v1/tickets/{id}/run` | agent | 202, 401, 403, 404, **409** | F13 |
| GET | `/api/v1/tickets/{id}/workflow` | viewer | 200, 401, 404 | F13 |
| GET | `/api/v1/tickets/{id}/events` | viewer | 200, 401, 404 | F13 |
| POST | `/api/v1/tickets/{id}/reply` | agent | 201, 400, 401, 403, 404, 422 | F12, N5 |
| POST | `/api/v1/tickets/{id}/request-info` | agent | 201, 401, 403, 404, 422 | F12 |
| POST | `/api/v1/tickets/{id}/escalate` | agent | 201, 401, 403, 404, 422 | F12 |
| GET | `/api/v1/approvals` | viewer | 200, 401 | F9 |
| GET | `/api/v1/approvals/{id}` | viewer | 200, 401, 404 | F9 |
| POST | `/api/v1/approvals/{id}/approve` | agent | 200, 401, 403, 404, **409** | F9 |
| POST | `/api/v1/approvals/{id}/reject` | agent | 200, 401, 403, 404, **409** | F9 |
| GET | `/api/v1/customers` | viewer | 200, 401 | F4 |
| GET | `/api/v1/customers/{id}` | viewer | 200, 401, 404 | F4 |
| GET | `/api/v1/knowledge` | viewer | 200, 401 | F5 |
| GET | `/api/v1/knowledge/{id}` | viewer | 200, 401, 404 | F5 |
| GET | `/api/v1/knowledge/search` | viewer | 200, 401, 422 | F5 |
| POST | `/api/v1/knowledge/reindex` | **admin** | 202, 401, 403 | F5 |
| GET | `/api/v1/escalations` | viewer | 200, 401 | F10 |
| GET | `/api/v1/escalations/{id}` | viewer | 200, 401, 404 | F10 |
| GET | `/api/v1/agents` | viewer | 200, 401 | F13 |
| GET | `/api/v1/audit` | viewer | 200, 401 | N6 |
| GET | `/api/v1/settings` | viewer | 200, 401 | — |
| PATCH | `/api/v1/settings` | **admin** | 200, 401, 403, 422 | — |
| GET | `/api/v1/mcp/tools` | viewer | 200, 401 | — |

Any route can additionally return `429` (rate limit) and `500`.

---

## 16. Frontend route map

`frontend/lib/types.ts` mirrors §2 exactly. Every call goes through `frontend/lib/api.ts`.

| Page | Calls |
|---|---|
| `/login` | `POST /auth/login` |
| `/dashboard` | `GET /dashboard/summary`, `GET /tickets?limit=10` |
| `/tickets` | `GET /tickets` |
| `/tickets/[id]` | `GET /tickets/{id}`, `POST /{id}/run`, `GET /{id}/workflow` (2 s poll), `GET /{id}/events`, `POST /{id}/reply`, `POST /{id}/request-info`, `POST /{id}/escalate`, `POST /approvals/{id}/approve|reject` |
| `/customers`, `/customers/[id]` | `GET /customers`, `GET /customers/{id}` |
| `/knowledge` | `GET /knowledge`, `GET /knowledge/search`, `POST /knowledge/reindex` (admin) |
| `/escalations` | `GET /escalations` |
| `/agents` | `GET /agents` |
| `/audit` | `GET /audit` |
| `/settings` | `GET /settings`, `PATCH /settings` (admin) |
| `/api/health` | Next.js route handler for the container HEALTHCHECK — does not call the backend |

A `401` from any call redirects to `/login?reason=expired`.

---

## 17. Open items

Resolve these as the phases land, and update this file first.

1. The exact `customer_context` payload shape in `WorkflowRun` is left open until
   `CustomerContext` is written in phase 8.
2. Whether `PATCH /settings` is needed at all, or settings stay environment-only. Listed here
   because CLAUDE.md §12 names a `/settings` group; the admin-write half is the derived part.
3. Ticket id format: sample data uses `CD-NNNN`. Confirm whether API-created tickets continue
   that sequence or use a UUID.
4. Whether `POST /auth/logout` is required — with stateless JWTs the client can simply discard
   the token, so it is omitted for now.
