TICKET: FM-02a  Schema and reversible migration

GOAL: One Alembic migration creates every table in SPEC section 6 and can be fully reversed, verified on a real Postgres.

FROZEN AUTHORITIES: SPEC sections 6 (domain model, release cases), 7 (cycle states), 13 (Alembic, Postgres 16), 15 (integration via testcontainers), 17 (FM-02 row, split agreed 2026-10-01).

IN SCOPE:
- SQLAlchemy 2.0 table definitions under `api/fernway/repositories/` for: Seller, SellerAlias, Source, Order, Hold, Refund, FundingFile, FundingLine, Cycle, CycleItem, Exception, Approval, Account, JournalEntry, JournalLine, OpenItem, RollforwardRow, AuditEvent
- `FundingLine` gets a nullable `adjustment_type TEXT` (decision: untyped fee adjustment is `NULL`; allowed values are not defined yet, so no CHECK)
- All money columns `BIGINT`
- CHECK constraints only where the spec lists values: Hold.status (`held | partially_released | released | refunded`), Refund.kind (`full | partial`), FundingLine.line_type (`payout | fee_adjustment | reserve`), CycleItem.case (`EXACT | PARTIAL | ZERO | ADJUSTED`), Cycle.status (the section 7 states plus BLOCKED and REJECTED), Account.code (`SELLER_PAYABLE | CASH_CLEARING | REFUNDS | FEE_ADJ`), Source.format (`csv | xlsx`)
- `UNIQUE(source_code, external_ref)` on SellerAlias; PK, FK and NOT NULL as the model implies
- Alembic setup, one migration with working `downgrade`
- testcontainers fixture for Postgres 16 in `tests/integration/`

OUT OF SCOPE: ledger CHECK, UNIQUE idempotency key and triggers (FM-02b); staging tables (FM-04); job queue table (first job ticket); users and sessions; seed data; any domain code.

ACCEPTANCE:
1. Given an empty Postgres 16, when `alembic upgrade head` runs, then every section 6 table exists.
2. Given a migrated database, when `alembic downgrade base` runs, then no application tables remain.
3. Given the migrated schema, when column types are inspected, then every `*_cents` column is `BIGINT` and no column uses float or numeric types.
4. Given a duplicate `(source_code, external_ref)` insert, when it runs, then Postgres rejects it.
5. Given a row with a status, kind, line_type or case outside the listed values, when inserted, then Postgres rejects it.

EVIDENCE: integration test names and pass output; `alembic upgrade head` and `downgrade base` output; `git diff --stat` showing the diff size.

STOP IF: a column the spec does not define is needed to make a constraint work, the diff passes about 400 lines (propose a further split), two attempts fail, or scope must grow.
