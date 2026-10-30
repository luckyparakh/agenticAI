---
name: clouddesk-contract
description: Keep the CloudDesk API contract in sync. Use whenever adding, changing or removing an HTTP route, a request or response field, a status code, or an enum value — it enforces that docs/API_CONTRACT.md, backend/app/schemas/ and frontend/lib/types.ts change together, with the RBAC and test obligations that go with them.
---

# Changing the API contract

[docs/API_CONTRACT.md](../../../docs/API_CONTRACT.md) is the source of truth for every route and
type — not the code, not the frontend. If an endpoint changes, three files change in the **same
commit** (CLAUDE.md §12):

```text
docs/API_CONTRACT.md  →  backend/app/schemas/  →  frontend/lib/types.ts
```

A change that lands in only two of the three is incomplete, even if everything compiles.

## 1. Order of work

1. **Write the contract first.** Method, path, required role, request body, response body, every
   status code it can return. Decide the shape before implementing it.
2. **Pydantic schemas** in `backend/app/schemas/`. Enums live in
   `backend/app/schemas/common.py` — a new category must be added there before it is used anywhere.
3. **Route** in `backend/app/api/`, mounted under `/api/v1`. Thin: HTTP, validation, auth, RBAC,
   background tasks. No business rules.
4. **`frontend/lib/types.ts`** mirrors the contract exactly, then `lib/api.ts`, then the page.
5. **Tests** in `tests/api/` and `frontend/__tests__/`.

## 2. Every route declares

| Field | Rule |
|---|---|
| Method + path | Under `/api/v1`, except `/health`, `/health/live`, `/health/ready` which are unprefixed |
| Auth | Bearer JWT (HS256, PyJWT, `settings.effective_jwt_secret`). Demo tokens expire in 8 h |
| Role | The minimum of `viewer` (1) < `agent` (2) < `admin` (3), via `require_role` |
| Request | A Pydantic model, or none |
| Response | A Pydantic model and an explicit status code (`202` for accepted background work) |
| Errors | `{ "detail": string }` with a correct code |
| Headers | `X-Request-ID` on every response, exposed through CORS |

Known status codes in this API: `200`, `201`, `202`, `400`, `401`, `403`, `404`, `409`, `422`, `429`.

`409` specifically means: the ticket is already `waiting_on_approval`, or the run being resumed
is not paused.

## 3. RBAC obligations

| Role | May |
|---|---|
| `viewer` | read tickets, customers, knowledge, audit |
| `agent` | everything viewer can + run workflows, reply, approve/reject, escalate |
| `admin` | everything + reindex knowledge, settings |

For every route you add or change:

- [ ] The minimum role is stated in `API_CONTRACT.md`
- [ ] `require_role` enforces it
- [ ] A `tests/api/` test asserts **403** for the role one step below
- [ ] The frontend disables the control for roles that cannot use it (`canAct`) — a disabled
      button is not a substitute for the 403

## 4. Enum changes

Enums are shared across the contract, the backend and the frontend. Changing one is a breaking
change.

| Enum | Values | Defined in |
|---|---|---|
| category | `login_issue, billing, api_failure, workspace_permissions, storage_quota, integration, feature_request, account, security, other` | `backend/app/schemas/common.py` |
| ticket status | `new, in_progress, waiting_on_customer, waiting_on_approval, escalated, resolved, closed` | `backend/app/schemas/common.py` |
| severity | `low, medium, high, critical` | `backend/app/schemas/common.py` |
| channel | `email, chat, web, api` | `backend/app/schemas/common.py` |
| role | `viewer, agent, admin` | `backend/app/core/security.py` |

Adding a value means: `common.py` → `API_CONTRACT.md` → `types.ts` → the frontend's display map
(labels, colours, `StatusPill`) → any rule in `agents/rules.py` that switches on it → the eval
dataset if it affects classification.

There are exactly **10** categories today. Do not add an eleventh without an explicit decision
recorded in `MEMORY.md`.

## 5. Checklist

- [ ] `docs/API_CONTRACT.md` updated
- [ ] `backend/app/schemas/` matches the contract field for field
- [ ] `frontend/lib/types.ts` matches the contract field for field
- [ ] Minimum role stated and enforced, with a 403 test
- [ ] Happy-path `tests/api/` test
- [ ] A test per named error code — at minimum the 404 and any 409
- [ ] Frontend reaches the backend only through `lib/api.ts`
- [ ] 401 still redirects to `/login?reason=expired`
- [ ] If the route is long-running, it returns `202` and the UI polls `/workflow` every 2 s
- [ ] No breaking rename without updating all three files plus the pages that read them
