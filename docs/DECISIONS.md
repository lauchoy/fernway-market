# Decisions

Constants and policies trace to SPEC.md, `config/rules.yaml` or this file.

## Locked 2026-10-01 (SPEC section 20)

1. Name: Fernway Market. Repo `fernway-market`, Python package `fernway`, ticket prefix FM.
2. Hosting: Render (free web service, Starter $7/mo when sharing the link) and Neon free Postgres.
3. Jobs: Postgres queue, worker in-process on free tier. No Temporal.
4. AI explain: on, with fallback and a daily cost cap.
5. Repo: public on Jimmy's GitHub.

## Planning decisions 2026-10-01 (FM-01 to FM-03 kickoff)

6. Variance direction: the funding file exceeds releases by $50.00. SPEC sections 10 and 19 reworded to match section 14 (spec v1.2).
7. Untyped fee adjustment: `FundingLine.adjustment_type` is a nullable TEXT column. `NULL` means untyped and unexplained. Allowed values are not yet defined.
8. Enums the spec does not list (Seller.status, Exception.status and code, Approval.decision, OpenItem.status, AuditEvent.kind) are plain TEXT with no CHECK.
9. Staging tables are deferred to FM-04. The job queue table is deferred to the first ticket that runs a job. Users and sessions are deferred.
10. FM-02 is split into FM-02a (tables, migration) and FM-02b (ledger triggers and constraints).
11. `month_small/expected.csv` has one row per hold: `seller_id, order_ref, case, release_cents, residual_cents, block_reason`.
12. Generator amounts, fee percentage and delivery dates are seeded synthetic parameters, not business rules.
