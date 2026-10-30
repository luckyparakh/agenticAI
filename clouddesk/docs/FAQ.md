# FAQ

Questions that come up while working on CloudDesk, with answers kept honest about what is known
versus derived.

---

## How did the agent know which files to create, and what to put in them?

**It didn't decide. [CLAUDE.md](../CLAUDE.md) named every file explicitly.**

The clearest example is §19, which in a single paragraph names four files *and* specifies their
contents:

> The 13-phase build is `PLAN_PHASE.md`. Each phase states **a goal, files touched, PRD rows
> covered, tests added, a `make demo` checkpoint, and exit criteria**. `PLAN.md` is the
> requirement catalog. `MEMORY.md` holds **locked facts and honest status**. The agent procedure
> is `.cursor/skills/clouddesk-support/SKILL.md`.

That is why [PLAN_PHASE.md](../PLAN_PHASE.md) has exactly those six fields per phase. The fields
were not a design choice — they are quoted from the specification.

The rest of the file list came from the same place:

| File | Named in CLAUDE.md |
|---|---|
| [docs/ARCHITECTURE.md](ARCHITECTURE.md) | §4 |
| [docs/API_CONTRACT.md](API_CONTRACT.md) | §4.3 and §12 — "the source of truth for every route and type" |
| [PLAN.md](../PLAN.md), [PLAN_PHASE.md](../PLAN_PHASE.md), [MEMORY.md](../MEMORY.md) | §19 |
| `.claude/skills/clouddesk-support/SKILL.md` | §19 (as `.cursor/skills/…` before the harness decision) |
| [TASKS.md](../TASKS.md) | the header table of [Git_Github_Workflow_Guide.md](Git_Github_Workflow_Guide.md) |
| `.env.example` | §10.1 — "must list every one" |
| `Makefile` | implied by the command list in §14 |
| [README.md](../README.md) | §20, recorded there as a known gap |

§12 went further and listed the route groups to document — `/auth`, `/dashboard/summary`,
`/tickets` with its sub-routes, `/approvals`, `/customers`, `/knowledge`, `/escalations`,
`/agents`, `/audit`, `/settings`, `/mcp/tools`. Writing the contract meant expanding that list
into schemas, not inventing which endpoints exist.

So the work was closer to transcription than to architecture.

---

## Then which parts were actually invented?

This matters more than the previous answer, because it is where this repo's documents may
diverge from any other version built from the same course material.

**Taken from CLAUDE.md, quoted and safe to rely on:**

- The 10 categories, 7 ticket statuses, 4 severities, 4 channels, 3 roles
- The tool/approval table and the "unknown tools always require approval" rule
- The five evaluation thresholds
- The RAG constants: 900-char windows, 150-char overlap, RRF k=60, 384-dim fake embeddings
- Middleware order, the graph node order, the layering table
- The 13 ticket demo scenario
- The 13 phase **names**

**Derived, and therefore the weakest parts:**

- Everything about a phase except its name — goals, file lists, dependency ordering, tests and
  exit criteria in [PLAN_PHASE.md](../PLAN_PHASE.md)
- All 73 sub-tasks and their branch names in [TASKS.md](../TASKS.md)
- The request and response **field names** in [API_CONTRACT.md](API_CONTRACT.md); only the route
  groups were specified
- The acceptance criteria under each F-row in [PLAN.md](../PLAN.md), which were inferred from
  prose elsewhere in CLAUDE.md

Both documents say so in their own headers. API_CONTRACT.md additionally carries a §17 "Open
items" list of four things that genuinely could not be determined from the specification — for
example, whether API-created tickets continue the `CD-NNNN` sequence or switch to a UUID.

The rule when a derived document disagrees with CLAUDE.md: **CLAUDE.md wins.** Fix CLAUDE.md
first, then the derived file, then the code.

---

## Why do other people building this project end up with the same files?

Because the file list is not an independent invention — it comes from the course material that
produced CLAUDE.md. §19 notes that *"Course documents 00–17 are not in this repo"*, and §20
refers to stage documents and a README the course supplied.

The chain is: the course defines the structure → CLAUDE.md records it → anyone reading CLAUDE.md
produces the same file list. Two people arriving at `PLAN.md`, `PLAN_PHASE.md`, `MEMORY.md` and
`TASKS.md` are reading the same document, not converging by coincidence.

The generalisable lesson is about the specification, not the agent: **a good CLAUDE.md names its
own satellite files and states what belongs in each.** That is what makes the work mechanical and
checkable. A vague specification produces plausible-looking files that quietly disagree with
their source, which is far worse than having no files at all.

---

## Why is nothing marked "done"?

CLAUDE.md §15.1 requires four states to be tracked separately, and they must not be collapsed:

| Term | Means |
|---|---|
| implemented | code exists and is committed |
| validated locally | `make test` / `make demo` ran green on a dev machine |
| needs cloud credentials | cannot be verified without a real account |
| actually deployed | applied to a real environment and smoke-tested |

As of the last update, the specification and planning documents are written and **no application
code exists**. `make test` has never run, because there is nothing to run. No cloud credentials
have been used and the GitHub workflows have never executed.

[MEMORY.md](../MEMORY.md) §2 holds the current status per area and is the file to update — not
this one — when that changes.

---

## Where do I start?

1. Read [CLAUDE.md](../CLAUDE.md) end to end. It is the source of truth and everything else
   defers to it.
2. Read [MEMORY.md](../MEMORY.md) for locked facts, honest status and the open discrepancies.
3. Pick the current phase in [PLAN_PHASE.md](../PLAN_PHASE.md) and its sub-tasks in
   [TASKS.md](../TASKS.md).
4. Follow the `clouddesk-support` skill in `.claude/skills/` while you work, and
   `clouddesk-phase` for the envelope around a phase.
