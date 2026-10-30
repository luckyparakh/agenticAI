---
name: clouddesk-phase
description: Execute one phase of the CloudDesk 13-phase build end to end. Use when starting, continuing or closing a numbered phase from PLAN_PHASE.md — it covers the entry check, the build order within a phase, the demo checkpoint, the exit criteria, and the status updates that must land in MEMORY.md, PLAN_PHASE.md and the CLAUDE.md phase table.
---

# Running a CloudDesk phase

A phase is the unit of work. It is finished when its exit criteria pass, its tests are green
offline, `make demo` still runs, and its status is updated in three places.

Follow the `clouddesk-support` skill for everything inside a phase. This skill is about the
envelope around it.

## 1. Entry check

Before writing anything:

1. Open [PLAN_PHASE.md](../../../PLAN_PHASE.md) and read the phase's **goal, files touched,
   PLAN rows, tests added, demo checkpoint and exit criteria**.
2. Confirm the **previous phase's exit criteria actually pass** — rerun its tests, do not trust
   the status table. If they do not, say so and fix that first, or get an explicit decision to
   proceed anyway.
3. Open [MEMORY.md](../../../MEMORY.md) for locked facts and the honest status table.
4. List the PLAN rows this phase closes. If the phase touches a row owned by a different phase,
   stop and reconcile the plan before coding.

If the phase as written conflicts with CLAUDE.md, **CLAUDE.md wins** — update CLAUDE.md first,
then `PLAN_PHASE.md`, then build.

## 2. Build order inside a phase

Work outside in, contract first:

```text
contract → schema → repository → service → route/node → test → frontend → demo
```

1. **Contract** — if the phase adds routes, write them into `docs/API_CONTRACT.md` first.
2. **Schema** — Pydantic in `backend/app/schemas/`, SQLAlchemy in `backend/app/models/entities.py`,
   and the matching DDL in `database/schema.sql` plus an additive migration.
3. **Repository** — all SQL lives here.
4. **Service** — orchestration only.
5. **Route or node** — thin; no business rules in the API layer.
6. **Tests** — in the folder the phase names. A test that would pass before the change is not a test.
7. **Frontend** — `lib/types.ts` then the client then the page.
8. **Demo** — run the phase's `make demo` checkpoint.

Commit per sub-task, not per phase. One sub-task in [TASKS.md](../../../TASKS.md) = one
`feature/<name>` branch = one PR into `development`.

## 3. Exit gate

A phase is closed only when all of these hold. Run them, do not assume them.

- [ ] Every exit criterion in `PLAN_PHASE.md` for this phase is demonstrably true
- [ ] `make test` passes offline — `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`,
      `USE_FAKE_REDIS=true`, no API key, no Docker
- [ ] `make lint` clean; frontend `npm run lint` and `npm run test -- --run` clean if touched
- [ ] `make demo` completes, and the phase's specific demo checkpoint behaves as described
- [ ] Every PLAN row the phase claims maps to at least one named test
- [ ] `.env.example` lists every variable the phase introduced
- [ ] No hard stop from `clouddesk-support` §4 is reachable
- [ ] From phase 13 only: all five evaluation thresholds met

## 4. Status updates — all three, same change

When a phase closes, update:

1. **[PLAN_PHASE.md](../../../PLAN_PHASE.md)** — the phase's own status line.
2. **[MEMORY.md](../../../MEMORY.md)** — the honest status table, plus any new locked fact or
   decision the phase settled.
3. **[CLAUDE.md](../../../CLAUDE.md) §19** — the phase table row.

And in `TASKS.md`, mark each merged sub-task Completed ✅.

## 5. Honest status

Use the four states exactly (CLAUDE.md §15.1). Do not collapse them.

| Term | Means |
|---|---|
| implemented | code exists and is committed |
| validated locally | `make test` / `make demo` ran green on a dev machine |
| needs cloud credentials | cannot be verified without a real account |
| actually deployed | applied to a real environment and smoke-tested |

Do not write "deployed", "passes in CI" or "green" until it has happened. As of the last update
to `MEMORY.md`: no cloud credentials used, nothing applied to a real account, and GitHub
workflows have not executed because the repo has not been pushed with secrets configured.

## 6. The phases

| Phase | Name | Depends on |
|---|---|---|
| 1 | Runtime skeleton | — |
| 2 | Persistence and demo data | 1 |
| 3 | Identity and request guards | 2 |
| 4 | Support API | 3 |
| 5 | Knowledge pipeline | 2 |
| 6 | Tools and policy | 4, 5 |
| 7 | Rules and guardrails | 4 |
| 8 | Specialist agents | 6, 7 |
| 9 | Workflow graph and trace | 8 |
| 10 | Approval and escalation | 9 |
| 11 | Memory | 9 |
| 12 | Agent console | 10, 11 |
| 13 | Evaluation and delivery | 12 |

Stage 17 (Agentic DevOps, `../deployment-agent/`) is optional and is **not** a core exit
criterion for Project 1.
