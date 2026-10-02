# Fernway Market - payouts console spec sheet

Payout release automation for a marketplace. A demo product, built end to end with tests and a real deployment, designed to be shown as a 2-minute video.

Version 1.2 · 2026-10-01 (section 20 decisions applied; variance direction aligned to section 14) · Owner: Jimmy Lau Choy

---

## 1. One-paragraph pitch

Fernway Market (fictional) is a handmade-goods marketplace with 3,000 sellers. When a buyer pays, the seller's money is held until the 14-day return window closes. Once a month an analyst has to work out who gets paid: pull order exports from two storefronts, match every seller, subtract refunds, tie the total to the payment processor's funding file, and type the payouts. Fernway's payouts console does that in one screen. It ingests the files, matches and validates every hold, runs two money checks, and refuses to pay anything it can't prove. A human approves, and every dollar posts to a double-entry ledger exactly once.

## 2. What the video has to make obvious

1. The problem is real and expensive: thousands of sellers, money moving, errors cost real dollars.
2. The system does the boring 95% automatically and shows the 5% that needs a human.
3. It refuses to guess. The Pay button is disabled, with the reason on screen.
4. Every dollar is checked twice before it moves, and it can never be paid twice.
5. It was built with AI agents under strict guardrails, and the AI never touches money.

Every feature below exists to make one of these five beats land on screen.

## 3. Scope

### In scope (v1)

- Monthly payout cycle for one marketplace, USD only.
- Two storefront sources with different file formats (CSV and XLSX), mapped by config.
- Holds, full refunds, partial refunds, fee adjustments.
- Processor funding file tie-out.
- Net-zero check against open payables.
- Rules file with fail-closed behavior for undecided policies.
- Preparer and approver roles with segregation of duties.
- Idempotent posting to an append-only double-entry ledger.
- Payout instruction file export.
- Monthly rollforward per seller with a control total.
- Exceptions queue with an AI "explain this exception" assistant (read-only).
- Audit log of every state change.
- Demo mode: seeded data, role switcher, reset button.
- Deployed publicly, with CI/CD.

### Out of scope (v1)

Real payment rails, real bank or processor integrations, multi-currency, tax, seller-facing UI, real user signup, mobile layout beyond "doesn't break".

## 4. Glossary

| Term | Meaning |
|---|---|
| Hold | A seller's net proceeds from one order, held until the return window closes |
| Release | Paying out some or all of a hold |
| Cycle | One monthly payout run, keyed `YYYY-MM` |
| Funding file | The processor's settlement file: what was actually funded for payouts this cycle |
| Tie-out | Sum of releases equals funding payout total, with any difference explained by typed lines |
| Open payable | Ledger item representing money owed to a seller for a hold |
| Net-zero check | Each release clears exactly one open payable: release + payable change = 0 |
| Fail-closed | Unknown or undecided means blocked, never a default guess |
| Rollforward | Opening held + new holds - released - refunded = closing held |

## 5. Users and roles

| Role | Can | Cannot |
|---|---|---|
| Preparer (demo: Maya) | Upload files, run the cycle, resolve exceptions, submit for approval | Approve or post |
| Approver (demo: Sam) | Approve or reject a submitted cycle, post an approved cycle | Approve a cycle they prepared |
| Viewer | Read everything | Change anything |

## 6. Domain model

All money is integer cents (`BIGINT`) in storage and `int` in Python domain code. No floats anywhere in the domain package, enforced by a lint rule and a test.

```
Seller(id, display_name, payout_token, status)
SellerAlias(source_code, external_ref, seller_id)            -- unique(source_code, external_ref)
Source(code, format, mapping_config_path)                    -- storefront_a: csv, storefront_b: xlsx
Order(id, source_code, order_ref, seller_id, gross_cents, fee_cents, net_cents, delivered_at)
Hold(id, order_id, seller_id, amount_cents, eligible_at, status)   -- held | partially_released | released | refunded
Refund(id, order_ref, amount_cents, kind, processed_at)      -- kind: full | partial
FundingFile(id, cycle_id, sha256, uploaded_by)
FundingLine(id, funding_file_id, seller_ref, amount_cents, line_type)  -- payout | fee_adjustment | reserve
Cycle(id 'YYYY-MM', period_end, status, ruleset_hash, prepared_by, created_at)
CycleItem(id, cycle_id, hold_id, seller_id, case, proposed_release_cents, residual_cents, blocked, block_reason, block_owner)
Exception(id, cycle_id, item_id NULL, code, detail_json, status, resolved_by, resolution_note)
Approval(id, cycle_id, approver, decision, comment, decided_at)
Account(code)                                                -- SELLER_PAYABLE, CASH_CLEARING, REFUNDS, FEE_ADJ
JournalEntry(id, cycle_id, idempotency_key UNIQUE, posted_by, posted_at, memo)
JournalLine(id, entry_id, account_code, seller_id, debit_cents, credit_cents)
OpenItem(id, hold_id, seller_id, amount_cents, cleared_cents, status)
RollforwardRow(cycle_id, seller_id, opening, new_holds, released, refunded, closing)
AuditEvent(id, at, actor, cycle_id, kind, payload_json)      -- append-only
```

### Ledger invariants (enforced in the DB, not just code)

- `journal_line` and `journal_entry` are append-only. A trigger rejects UPDATE and DELETE.
- Every journal entry balances: sum(debits) = sum(credits). Checked in the posting transaction and by a constraint trigger.
- `idempotency_key` is unique. A re-post returns the original result, not a new entry.
- `CHECK (debit_cents >= 0 AND credit_cents >= 0 AND (debit_cents = 0) <> (credit_cents = 0))`.

### Release cases

| Case | When | Proposed release | Rule needed |
|---|---|---|---|
| EXACT | No refund, window closed | Full hold | none |
| PARTIAL | Partial refund on the order | Hold - refund | `partial_refund_policy` |
| ZERO | Full refund | 0, hold closes as refunded | none |
| ADJUSTED | Fee correction on the funding file | Hold +/- adjustment | `fee_adjustment_policy` |

## 7. Cycle state machine

```
DRAFT -> INGESTED -> MATCHED -> VALIDATED -> TIED_OUT -> SUBMITTED -> APPROVED -> POSTED -> CLOSED
                         \           \            \           \
                          +---------- BLOCKED (reason, owner) +---- REJECTED -> back to VALIDATED
```

- Transitions are only through service functions. Illegal transitions raise and write an audit event.
- BLOCKED is not terminal. Resolving the cause re-runs the stage.
- POSTED is terminal for money. CLOSED runs the rollforward and locks the cycle.

## 8. Pipeline stages and checks

1. **Ingest.** Upload storefront exports and the funding file. Each source is parsed with its mapping config (`config/sources/<code>.yaml`: column names, date formats, amount parsing). Reject files over 20 MB, wrong type, or a duplicate sha256 for the same cycle. Store raw rows in staging tables.
2. **Match.** Resolve every `(source, external_ref)` to one seller via `SellerAlias`. No match is `UNMATCHED_SELLER`. More than one match is `AMBIGUOUS_SELLER`. The preparer can map an alias from the UI, which writes an audit event.
3. **Validate.** For each hold with `eligible_at <= period_end`, assign a case and a proposed release. Checks: release never exceeds the hold, refund never exceeds the order, and any rule the case needs is non-null. A null rule blocks that item with the rule name and its owner.
4. **Tie-out.** Sum of proposed releases on unblocked items must equal funding `payout` lines plus explained `fee_adjustment` lines, within `tie_out_tolerance_cents` (default 0). Any variance blocks the cycle and shows the exact amount.
5. **Net-zero.** Each release has exactly one open item with enough uncleared amount, and release + open item change = 0. A partial release leaves a residual open only when the policy allows it.
6. **Submit and approve.** The preparer submits. An approver who is not the preparer approves or rejects with a comment. Blocked items are excluded and listed, and the approver must tick "I've reviewed N excluded items".
7. **Post.** One journal entry per release: Dr SELLER_PAYABLE / Cr CASH_CLEARING. Clear open items, update holds, generate `payout_instructions_<cycle>.csv`. The idempotency key is `sha256(cycle_id + ruleset_hash + sorted item ids and amounts)`. Runs in one transaction with a row lock on the cycle.
8. **Close.** Rollforward per seller. Total closing held must equal the SELLER_PAYABLE ledger balance (control total), or the close fails. The next cycle opens from the prior closing.

## 9. Rules file

`config/rules.yaml`, versioned. Its hash is stamped on each cycle.

```yaml
return_window_days: 14
tie_out_tolerance_cents: 0
partial_refund_policy:            # release_remainder | hold_until_resolved | null
  value: null
  owner: "Ops lead"
fee_adjustment_policy:
  value: apply_to_release
  owner: "Finance"
effective_date_rule: period_end
```

A null `value` is never defaulted. It blocks every item that needs it and shows `"Partial-refund policy not decided - owner: Ops lead"`. The demo seed ships with `partial_refund_policy: null` so this shows up on camera.

## 10. AI assistant: "Explain this exception"

- **What.** On any exception, a button returns a plain-English explanation and a suggested next step. Example: "The processor funded $50.00 more than the payouts. The difference matches one fee adjustment line with no type. Ask Finance to classify it."
- **How.** `GET /api/exceptions/{id}/explain` sends a structured, minimal context (codes, amounts, line types, no free text from files) to the Claude API, with a strict JSON output schema.
- **Guardrails.**
  - Read-only. The endpoint has no DB writes, and a test asserts the row count of every table is unchanged.
  - It never suggests posting or overriding a gate. The system prompt forbids it, and a post-filter rejects responses containing those actions.
  - Explanations are labeled "AI explanation".
  - It has a deterministic template fallback when no API key is set or the call fails, so the demo never breaks.
  - Responses are cached in memory per exception for 1 hour.
  - Public-demo cost guard: per-IP rate limit (10/min) and a global daily cap (`AI_DAILY_CAP`, default 300). Past the cap, the template fallback answers.
- **Flag.** `AI_EXPLAIN_ENABLED`, on in the deployed demo.

## 11. Screens

| # | Screen | Must show |
|---|---|---|
| S1 | Cycles | List with status chips, "New cycle" |
| S2 | Cycle overview | Stage stepper (Ingest, Match, Validate, Tie-out, Approve, Post). Tiles: sellers, auto-cleared, exceptions, total to release, variance |
| S3 | Items | Virtualized 3,000-row table, filter by case and blocked, seller search, row detail drawer |
| S4 | Exceptions | Grouped by code, each with reason, owner, AI explain, resolve action (map alias, add note) |
| S5 | Gate panel | Checklist: identity, rules complete, tie-out, net-zero, approval. Each green or red with the reason. Post disabled with a tooltip listing blockers |
| S6 | Approval | Approver-only modal, preparer shown, excluded-items acknowledgment, comment required on reject |
| S7 | Post result | Entries posted, total, download payout file. Re-post shows "Already posted at ..." |
| S8 | Rollforward | Per-seller table and the control total tie, green or red |
| S9 | Rules | Rendered rules.yaml, nulls highlighted with owner |
| S10 | Audit log | Filterable timeline per cycle |

Visual direction: a calm, dense finance tool. Neutral palette, one accent, red only for blocking states, tabular numerals for money, light and dark themes.

Demo mode: header role switcher (Maya Preparer, Sam Approver, Viewer), a "Reset demo" button that reseeds in under 5 seconds, and a banner saying "Demo data. No real money."

## 12. API (FastAPI, OpenAPI is the contract)

```
POST   /api/cycles                         create cycle {period}
GET    /api/cycles
GET    /api/cycles/{id}                    overview + gates
POST   /api/cycles/{id}/files              multipart upload {kind: storefront_a|storefront_b|funding}
POST   /api/cycles/{id}/run                run stages up to TIED_OUT (async job, returns job id)
GET    /api/jobs/{id}
GET    /api/cycles/{id}/items?case=&blocked=&q=&cursor=
GET    /api/cycles/{id}/exceptions
POST   /api/exceptions/{id}/resolve        {action: map_alias|note, ...}
GET    /api/exceptions/{id}/explain
POST   /api/cycles/{id}/submit
POST   /api/cycles/{id}/approve            {decision, comment, acknowledged_excluded}
POST   /api/cycles/{id}/post               header Idempotency-Key optional (server derives if absent)
GET    /api/cycles/{id}/payout-file
POST   /api/cycles/{id}/close
GET    /api/cycles/{id}/rollforward
GET    /api/cycles/{id}/audit
GET    /api/rules
POST   /api/demo/reset                     demo mode only
GET    /healthz  /readyz
```

Errors use RFC 9457 problem+json. A gate block returns 409 with `{"blocked_by": [{"gate","reason","owner"}]}`.

## 13. Architecture and stack

| Layer | Choice | Why |
|---|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | Typed contracts, mature migrations |
| Jobs | Postgres-backed queue (`SELECT ... FOR UPDATE SKIP LOCKED`). `WORKER_MODE=inprocess` runs the worker as a background task inside the web service (Render free tier has no background workers). `WORKER_MODE=separate` runs it as its own process | Durable retries, $0 extra infra. Temporal stays out of scope |
| DB | Postgres 16 | Constraints and triggers enforce ledger rules |
| Web | React 18, Vite, TypeScript strict, TanStack Query and Table, Tailwind, shadcn/ui | Fast, dense tables, accessible components |
| Types | `openapi-typescript` generates client types from the API schema | Contract drift fails CI |
| AI | Anthropic Claude API via official SDK | Explain feature only |
| Packaging | One Docker image: API serves the built web app, worker runs in-process | One deploy unit, one free service |
| Hosting | Render web service (Docker, free tier, upgradeable to Starter $7/mo) via `render.yaml` blueprint, and Neon Postgres (free tier) | Render's free Postgres expires after 30 days, so the DB lives on Neon |
| CI/CD | GitHub Actions, then a Render deploy hook | Render deploys only after CI is green on main |

Layering in `api/`: `routes -> services -> domain (pure, no I/O) -> repositories`. The domain package has zero imports from FastAPI or SQLAlchemy, enforced by an import-linter contract.

### Repo layout

```
fernway-market/
  api/
    fernway/{routes,services,domain,repositories,jobs,ai,config}/
    migrations/
    tests/{unit,property,integration,golden,contract}/
  web/
    src/{routes,components,api,lib}/
    e2e/
  config/{rules.yaml,sources/*.yaml}
  data/{generator/,fixtures/month_small/,golden/}
  docs/{ARCHITECTURE.md,DECISIONS.md,ai-sdlc/,demo-script.md}
  tickets/                      one file per ticket, template in section 17
  AGENTS.md
  docker-compose.yml  Dockerfile  render.yaml  Makefile  LICENSE (MIT)
  .github/workflows/{ci.yml,deploy.yml}
```

## 14. Synthetic data

`data/generator` builds a seeded month (`--seed 42`) with:

- 3,000 sellers and about 30,000 orders split across storefront_a (CSV, `Seller Handle`, `MM/DD/YYYY`, `$1,234.56`) and storefront_b (XLSX, `merchant_id`, ISO dates, cents as integers).
- Injected scenarios: 12 unmatched aliases, 2 ambiguous aliases, 40 partial refunds, 25 full refunds, 8 fee adjustments (one untyped), and a funding file exactly $50.00 over releases.
- `data/fixtures/month_small`: 20 sellers, every case at least once, with a hand-verified `expected.csv` (per-seller case, release, residual, block reason). This is the oracle. A human signs off on it before any slice that reads it merges.

## 15. Test strategy

| Layer | What | Gate |
|---|---|---|
| Unit | Every domain function, including parsing for each source config | Domain coverage >= 95% |
| Property (Hypothesis) | Ledger entries always balance. Release <= hold. Rollforward identity holds. Net-zero for every posted release. Posting twice is a no-op | 500 examples per property in CI |
| Oracle | `month_small` run end to end equals `expected.csv` exactly | Must pass |
| Golden | `payout_instructions_<cycle>.csv` byte-for-byte; AI fallback text | Must pass. Updating a golden needs `--update-golden` and a reviewed diff |
| Integration | Real Postgres via testcontainers: triggers reject UPDATE/DELETE on ledger, unbalanced entry rejected, unique idempotency key, SKIP LOCKED worker | Must pass |
| Fail-closed | Null rule blocks affected items with rule + owner. Missing funding file blocks tie-out. Any variance blocks | Must pass |
| Authz | Preparer can't approve. Approver can't approve own cycle. Viewer can't mutate | Must pass |
| Concurrency | Two simultaneous posts on one cycle produce exactly one set of entries | Must pass |
| AI | Explain endpoint changes no table row counts. Fallback used when key missing or on timeout. Forbidden-action filter works | Must pass |
| Contract | OpenAPI schema snapshot; generated TS types compile; web uses only generated types | Must pass |
| E2E (Playwright) | Happy path; $50 variance blocks then clears after resolving; null policy blocks partial refunds; SoD; duplicate post; reset demo | Must pass on docker-compose in CI |
| Performance | Seeded 3,000-seller month runs ingest through tie-out in < 10 s on CI runner; items API p95 < 300 ms | Must pass |
| Static | ruff, mypy --strict (api), eslint, tsc --noEmit, import-linter, no-float rule in domain | Must pass |
| Mutation (nightly) | mutmut on `domain/` | Score >= 80%, report only |

## 16. Production readiness checklist

- [ ] Alembic migrations run in the start command (`alembic upgrade head && uvicorn ...`) behind a Postgres advisory lock, and are reversible
- [ ] `/healthz` (process) and `/readyz` (DB reachable, migrations current)
- [ ] Structured JSON logs with `request_id` and `cycle_id` on every line
- [ ] Error tracking (Sentry, optional DSN)
- [ ] Auth: signed session cookie, roles server-side, CSRF protection on mutations
- [ ] Upload limits, MIME and extension checks, no file content reaches the AI prompt
- [ ] Rate limits on upload, run and explain
- [ ] Secrets only from env: `DATABASE_URL`, `SESSION_SECRET`, `ANTHROPIC_API_KEY`, `DEMO_MODE`, `WORKER_MODE`, `AI_DAILY_CAP`
- [ ] Public repo hygiene: MIT license, gitleaks secret scan in CI, `.env.example` only, no real company names or data
- [ ] Free-tier behavior documented: Render spins the service down after 15 idle minutes and takes about a minute to wake. Record the video on a warm instance, and switch to Starter ($7/mo) while actively sharing the link
- [ ] Neon branch-based restore documented; `make reseed` rebuilds demo data from scratch
- [ ] Dependabot, `pip-audit` and `npm audit` in CI
- [ ] Demo reseed is idempotent and finishes in under 5 s
- [ ] README: run locally in one command (`make up`), deploy steps, architecture diagram, honest status

## 17. Build plan

Each ticket is one PR. Template for every ticket file:

```
TICKET: FM-XX  title
GOAL: one observable behavior
FROZEN AUTHORITIES: spec sections that apply (rules, schema, API)
IN SCOPE: files or modules
OUT OF SCOPE: neighbors, refactors
ACCEPTANCE: Given / When / Then (max 5, else split)
EVIDENCE: tests added, command output, screenshot if UI
STOP IF: spec conflicts with reality, a needed value has no source, two attempts fail, scope must grow
```

| Ticket | Behavior | Key acceptance |
|---|---|---|
| FM-01 | Repo scaffold, compose, CI skeleton, Makefile | `make up` serves `/healthz`. CI runs lint and an empty test suite green |
| FM-02 | Schema, migrations, ledger triggers | Integration tests: append-only, balanced entries, unique idempotency key |
| FM-03 | Data generator and `month_small` fixture | Seed 42 reproduces byte-identical files. Fixture signed off by Jimmy |
| FM-04 | Ingest with per-source mapping config | Given a new column name in storefront_a, when only YAML changes, then ingest passes |
| FM-05 | Match and alias resolution | Unmatched and ambiguous become exceptions. Map-alias resolves and audits |
| FM-06 | Validate: cases, rules, fail-closed | `month_small` cases equal `expected.csv`. Null policy blocks with owner |
| FM-07 | Tie-out | $50 variance blocks with the exact amount. Explained adjustments pass |
| FM-08 | Net-zero and open items | Property test: every release clears exactly its open item |
| FM-09 | Submit, approve, SoD | Authz tests pass. Exclusion acknowledgment required |
| FM-10 | Post, idempotency, payout file | Concurrency test passes. Golden payout file matches |
| FM-11 | Close and rollforward with control total | Control total ties. Next cycle opens from prior closing |
| FM-12 | Web: cycles, overview, items table | 3,000 rows scroll smoothly. Types from OpenAPI |
| FM-13 | Web: exceptions, gate panel, approval, post | E2E happy path and blocked paths pass |
| FM-14 | AI explain with fallback and guardrails | AI tests in section 15 pass |
| FM-15 | Rules, rollforward, audit screens; demo mode | Reset under 5 s. Role switcher works |
| FM-16 | Deploy: Dockerfile, render.yaml, Neon DB, deploy-hook workflow | Green CI on main triggers the Render deploy hook. Public URL passes smoke test (`/readyz`, demo reset, one cycle run) |
| FM-17 | Demo video tooling and docs | Playwright records the storyboard. README and docs complete |

Order: FM-01 to FM-03 first, since everything reads the schema and the oracle. FM-04 to FM-11 make the backend spine, in order. FM-12 to FM-15 can start once FM-06 lands. FM-16 can run any time after FM-02. FM-17 goes last.

## 18. Review agents

### Per PR

A fresh agent sees only the ticket file and the diff. It reports PASS or REVISE with findings written as quote, problem, fix.

1. Every acceptance line has a test, and that test fails when the change is reverted (the agent checks this by running the test against the base branch).
2. Files touched are inside the ticket's IN SCOPE list.
3. Every constant traces to SPEC.md, `rules.yaml` or `docs/DECISIONS.md`. No invented business rules.
4. Diff is no more than about 400 lines, excluding fixtures and generated code.
5. CI is green.

After 2 REVISE rounds it stops and escalates to Jimmy.

### Final release review

A fresh agent acts as a sharp outsider seeing the project for the first time.

**Hard gates:** a clean clone gets `make up` working in 5 minutes or less with no secrets; the full test suite and e2e pass; the deployed URL passes the smoke test; and the repo has no real company names, people or data.

**Rubric:** each item is scored 1-5, and every score must be at least 4.

- **Story:** can it narrate the 2-minute pitch from the README alone?
- **Product:** would a non-engineer understand every blocked reason on screen?
- **Correctness:** do the money invariants hold under its own adversarial tries (double post, edits to posted data, a self-approval attempt)?
- **Craft:** visual polish, empty and error states, loading states.
- **Honesty:** does the README status match what the code does?
- **Process:** does the git history show one behavior per PR, with each ticket linked?

## 19. Demo video (2 minutes)

Recorded from the deployed app. Playwright drives the clicks at human speed with `video: on`, and Jimmy adds voiceover and captions.

| Time | Screen | Beat | Voiceover gist |
|---|---|---|---|
| 0:00 | S1 to S2 | Problem | "Every month a marketplace has to decide which of 3,000 sellers get paid, and how much. Done by hand, it's days of spreadsheets, and one mistake pays the wrong person." |
| 0:15 | Upload | Ingest | "Two storefronts, two file formats, one processor file. It reads all three." |
| 0:25 | S2 tiles | Automation | "2,9xx sellers clear automatically. 5x need a human, and it says exactly why." |
| 0:40 | S5 red | Refuses to guess | "The processor funded $50.00 more than we're paying out. Pay stays locked until that's explained." |
| 0:55 | S4 AI explain | AI assists | "AI explains the exception in plain English. It can read, never move money." |
| 1:10 | S9 null rule | Fail-closed | "Nobody has decided how to handle partial refunds yet, so those 40 payouts are held. It never fills in a default." |
| 1:20 | S6 as Sam | Control | "A second person approves, and you can't approve your own work." |
| 1:30 | S7 | Post once | "One click posts to a double-entry ledger. Click again and nothing happens. Paid exactly once." |
| 1:40 | S8 | Ties out | "Every seller's balance rolls forward, and the total ties to the ledger to the cent." |
| 1:50 | GitHub | How it was built | "Built with AI agents, one small, tested piece at a time, with a human approving every rule." |

## 20. Decisions (locked 2026-10-01)

1. Name: Fernway Market. Repo `fernway-market`, Python package `fernway`, ticket prefix FM.
2. Hosting: Render (free web service, Starter $7/mo when sharing the link) + Neon free Postgres.
3. Jobs: Postgres queue, worker in-process on free tier. No Temporal.
4. AI explain: on, with fallback and a daily cost cap.
5. Repo: public on Jimmy's GitHub.
