TICKET: FM-02b  Ledger invariants and triggers

GOAL: The database itself refuses to alter or unbalance the ledger.

FROZEN AUTHORITIES: SPEC sections 6 (ledger invariants), 15 (integration row), 17 (FM-02 row, split agreed 2026-10-01).

IN SCOPE:
- A second Alembic migration (with working `downgrade`) adding:
  - trigger rejecting UPDATE and DELETE on `journal_entry` and `journal_line`
  - `CHECK (debit_cents >= 0 AND credit_cents >= 0 AND (debit_cents = 0) <> (credit_cents = 0))` on `journal_line`
  - `UNIQUE` on `journal_entry.idempotency_key`
  - deferred constraint trigger: at commit, sum(debits) = sum(credits) per entry
- Integration tests in `api/tests/integration/` against real Postgres 16

OUT OF SCOPE: posting service, idempotent re-post behavior (FM-10), SKIP LOCKED worker test, advisory-lock migration runner (FM-16), any domain code.

ACCEPTANCE:
1. Given a posted journal entry and line, when an UPDATE or DELETE is issued on either table, then Postgres raises and the row is unchanged.
2. Given an entry whose debits and credits differ, when the transaction commits, then it is rejected and nothing is stored.
3. Given a balanced entry, when the transaction commits, then it is stored.
4. Given two entries with the same `idempotency_key`, when the second is inserted, then Postgres rejects it.
5. Given a line with both amounts zero, both positive, or a negative amount, when inserted, then the CHECK rejects it.

EVIDENCE: integration test names and pass output; each test shown failing against the schema from FM-02a alone (before the migration) and passing after; `alembic downgrade -1` output; `git diff --stat`.

STOP IF: the constraint trigger cannot be made deferred in a way the posting transaction can rely on, two attempts fail, or scope must grow.
