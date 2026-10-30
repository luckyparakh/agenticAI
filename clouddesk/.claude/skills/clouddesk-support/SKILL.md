---
name: clouddesk-support
description: The working procedure for building CloudDesk, the autonomous customer support platform. Use whenever changing anything under clouddesk/ — backend, agents, RAG, tools, memory, frontend, tests or deployment. Covers the read-before-write order, the layering rules, the rules-plus-LLM pattern, the node shape, approval gates and the hard stops.
---

# CloudDesk agent procedure

[CLAUDE.md](../../../CLAUDE.md) is the single source of truth. When this skill and CLAUDE.md
disagree, CLAUDE.md wins — fix CLAUDE.md first, then the code, then this skill.

## 1. Read before you write

Never start editing from the request alone. In this order:

1. **CLAUDE.md** — the section that owns the thing you are touching.
2. **[docs/API_CONTRACT.md](../../../docs/API_CONTRACT.md)** — if an HTTP route, schema or
   frontend type is involved. It is the contract, not a description of the code.
3. **[PLAN.md](../../../PLAN.md)** — find the F-row or N-row this change serves. If there is no
   row, you are either out of scope or the row is missing; say which.
4. **[PLAN_PHASE.md](../../../PLAN_PHASE.md)** — confirm the phase. Do not build phase 9 work
   while phase 4 is unfinished unless the user asked for it.
5. **The existing test** for that behaviour. Changing behaviour without reading its test is how
   the eval thresholds silently drop.
6. **[MEMORY.md](../../../MEMORY.md)** — locked facts and the honest status table.

## 2. The loop

One change → one PLAN row → one test → one commit.

```text
read (§1) → write the test → write the code → make test → make demo → update status → commit
```

- `make test` must pass **offline**: `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`,
  `USE_FAKE_REDIS=true`, no API key, no Docker. If your change only works with a real key, it is
  not done.
- `make demo` must still run end to end at the end of every phase (CD-1002 pauses for approval).
- Update the status in `MEMORY.md` and the phase table in CLAUDE.md §19 in the same change.

## 3. Non-negotiables

These are CLAUDE.md §18 as a checklist. Check each one before you call a change finished.

| # | Rule | How to verify |
|---|---|---|
| 1 | Layers stay clean | See [references/layers.md](references/layers.md). No shortcut across a layer — refactor instead. |
| 2 | Rules first, LLM second | Every policy decision is deterministic and has its own test in `tests/unit/`. |
| 3 | No LLM call without `call_structured` | Needed for telemetry, usage and retry. Grep for direct provider calls. |
| 4 | No tool call without `ToolRegistry.execute` | Including approved ones. Unknown tools always require approval. |
| 5 | Structured outputs everywhere | Every agent returns a Pydantic model from `backend/app/schemas/workflow.py`. No free-text parsing. |
| 6 | Injection-safe by default | Ticket, email, file and web text goes through `wrap_untrusted` and carries `SECURITY_PREAMBLE`. |
| 7 | Offline first | `make test` with the fake provider. |
| 8 | Small, idempotent interrupts | No side effects before `interrupt()` — that code re-runs on resume. |
| 9 | Reducers append | `errors` and `completed_nodes` append; `token_usage` sums via `merge_usage`. Never overwrite. No large documents in reducer fields. |
| 10 | Money and accounts are approval-gated | Refunds, setting resets, deletions, disputes never run unattended. |
| 11 | Never commit secrets or state | `.env`, `data/`, `*.db`, `terraform.tfvars`, `backend.hcl`, `tfplan`, any real key. |
| 12 | Migrations are additive | Never edit an applied migration. Never drop data without an explicit decision. |
| 13 | One change, one commit, one test | Each feature maps to a PLAN row and a test. |
| 14 | Demo before production | Every stage still runs with `make demo`. |
| 15 | Say what is not done | Keep the honest status (CLAUDE.md §15.1, `MEMORY.md`) current. |

## 4. Hard stops

If a change could cause any of these, stop and raise it rather than shipping it. From CLAUDE.md §18.1:

- A customer reply containing internal URLs, secrets, or another customer's data.
- A refund, deletion or setting reset executed without a recorded approval.
- A `viewer` able to approve, reply, or run a workflow — it must return 403.
- A prompt-injected instruction from ticket text changing the workflow. **CD-1013 must never
  execute an export.**
- Memory notes containing card numbers, keys, passwords, or raw ticket bodies.
- Deploying prod with the dev var-file, or applying without a reviewed plan.

## 5. The rules-plus-LLM pattern

Policy cases — dispute, deletion, security, data loss, legal, enterprise outage — are decided by
rules in `agents/rules.py`, never left to the model's probability. The LLM adds judgement in grey
areas only.

```python
matched = rules.matching_escalation_rules(text, plan_name)     # policy
result  = await call_structured(EscalationDecision, ...)        # judgement
if matched:                       decision = policy decision
elif escalation and not (high severity and low confidence):
                                  decision.escalation_required = False   # distrust vague model escalations
```

Severity: rules can **raise** the model's severity, never lower it.

Planned actions are deterministic (`ResolutionAgent.plan_actions`), not model-invented.

## 6. Node shape

Every node file in `agents/nodes/` follows this. Nodes return a **partial** state dict.

```python
async def troubleshooting(state):
    tracer = tracer_for(state)
    async with tracer.node(NODE):                       # node_started/node_completed + duration
        diagnosis, status, usage, ms, calls = await TroubleshootingAgent().run(...)
        await record_tool_calls(tracer, NODE, calls)
        await record_llm(tracer, NODE, usage, ms, "diagnosis")
    return {"diagnosis": diagnosis, "token_usage": usage,
            "completed_nodes": [NODE], "current_node": NODE}
```

Node ids are what the frontend renders as workflow steps. Adding a node means updating
`GRAPH_NODES` / `GRAPH_EDGES` (served by `GET /api/v1/agents`) and the frontend's step list.

`WorkflowTracer` **never raises** — telemetry must not break a run.

## 7. Changing an endpoint

Three files move together, in the same change (CLAUDE.md §12):

1. `docs/API_CONTRACT.md`
2. `backend/app/schemas/`
3. `frontend/lib/types.ts`

See the `clouddesk-contract` skill for the full procedure.

## 8. Adding things

| Adding | Do this first |
|---|---|
| A category | Add it to `backend/app/schemas/common.py`. There are exactly 10 today. |
| A tool | `async` + `@tool`, docstring is the LLM/MCP description, register it, set its approval flag in `ToolPolicy`, add a `tests/unit/` policy test. |
| A node | `agents/nodes/`, `GRAPH_NODES`/`GRAPH_EDGES`, frontend steps, a `tests/workflow/` shape test. |
| An eval case | Append to `datasets/eval_cases.json` with a valid `expected_category`. |
| A migration | `database/migrations/000N_<name>.sql` + update the model + `schema.sql`. |
| An env var | Add it to `.env.example` — `tests/deployment` asserts full coverage. |

## 9. Before you say it is done

Run through [references/checklists.md](references/checklists.md). The short version:

- [ ] `make test` passes offline
- [ ] `make lint` clean
- [ ] `make demo` still completes
- [ ] The PLAN row's acceptance criterion maps to a named test
- [ ] `API_CONTRACT.md` / schemas / `types.ts` agree, if a route changed
- [ ] `.env.example` lists any new variable
- [ ] `MEMORY.md` honest status updated — nothing claimed as deployed or green in CI that is not
- [ ] Nothing in §4 above is possible as a result of this change
