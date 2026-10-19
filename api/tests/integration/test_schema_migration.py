import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

API_ROOT = Path(__file__).resolve().parents[2]

SECTION_6_TABLES = {
    "account",
    "approval",
    "audit_event",
    "cycle",
    "cycle_item",
    "exception",
    "funding_file",
    "funding_line",
    "hold",
    "journal_entry",
    "journal_line",
    "open_item",
    "order",
    "refund",
    "rollforward_row",
    "seller",
    "seller_alias",
    "source",
}

CENTS_COLUMNS = {
    ("cycle_item", "proposed_release_cents"),
    ("cycle_item", "residual_cents"),
    ("funding_line", "amount_cents"),
    ("hold", "amount_cents"),
    ("journal_line", "credit_cents"),
    ("journal_line", "debit_cents"),
    ("open_item", "amount_cents"),
    ("open_item", "cleared_cents"),
    ("order", "fee_cents"),
    ("order", "gross_cents"),
    ("order", "net_cents"),
    ("refund", "amount_cents"),
}

ROLLFORWARD_MONEY = ("opening", "new_holds", "released", "refunded", "closing")

FLOAT_TYPES = {"real", "double precision", "numeric", "decimal"}

SEED = (
    "INSERT INTO source (code, format, mapping_config_path) "
    "VALUES ('storefront_a', 'csv', 'a.yaml')",
    "INSERT INTO seller (id, display_name, payout_token, status) "
    "VALUES (1, 'Ada', 'tok', 'active')",
    "INSERT INTO seller_alias (source_code, external_ref, seller_id) "
    "VALUES ('storefront_a', 'ext-1', 1)",
    'INSERT INTO "order" (id, source_code, order_ref, seller_id, gross_cents, '
    "fee_cents, net_cents, delivered_at) VALUES "
    "(1, 'storefront_a', 'o-1', 1, 1000, 100, 900, '2026-10-01T00:00:00Z')",
    "INSERT INTO hold (id, order_id, seller_id, amount_cents, eligible_at, status) "
    "VALUES (1, 1, 1, 900, '2026-10-15T00:00:00Z', 'held')",
    "INSERT INTO refund (id, order_ref, amount_cents, kind, processed_at) "
    "VALUES (1, 'o-1', 100, 'partial', '2026-10-16T00:00:00Z')",
    "INSERT INTO cycle (id, period_end, status, ruleset_hash, prepared_by, created_at) "
    "VALUES ('2026-10', '2026-10-31', 'DRAFT', 'hash', 'maya', '2026-10-01T00:00:00Z')",
    "INSERT INTO funding_file (id, cycle_id, sha256, uploaded_by) "
    "VALUES (1, '2026-10', 'abc', 'maya')",
    "INSERT INTO funding_line (id, funding_file_id, seller_ref, amount_cents, "
    "line_type, adjustment_type) VALUES (1, 1, 'ext-1', 900, 'payout', NULL)",
    "INSERT INTO cycle_item (id, cycle_id, hold_id, seller_id, \"case\", "
    "proposed_release_cents, residual_cents, blocked, block_reason, block_owner) "
    "VALUES (1, '2026-10', 1, 1, 'EXACT', 900, 0, false, '', '')",
    "INSERT INTO account (code) VALUES ('SELLER_PAYABLE')",
)

REJECTED = (
    "INSERT INTO hold (id, order_id, seller_id, amount_cents, eligible_at, status) "
    "VALUES (2, 1, 1, 1, '2026-10-15T00:00:00Z', 'open')",
    "INSERT INTO refund (id, order_ref, amount_cents, kind, processed_at) "
    "VALUES (2, 'o-1', 1, 'none', '2026-10-16T00:00:00Z')",
    "INSERT INTO funding_line (id, funding_file_id, seller_ref, amount_cents, line_type) "
    "VALUES (2, 1, 'ext-1', 1, 'bonus')",
    "INSERT INTO cycle_item (id, cycle_id, hold_id, seller_id, \"case\", "
    "proposed_release_cents, residual_cents, blocked, block_reason, block_owner) "
    "VALUES (2, '2026-10', 1, 1, 'OTHER', 1, 0, false, '', '')",
    "INSERT INTO cycle (id, period_end, status, ruleset_hash, prepared_by, created_at) "
    "VALUES ('2026-11', '2026-11-30', 'DONE', 'hash', 'maya', '2026-10-01T00:00:00Z')",
    "INSERT INTO source (code, format, mapping_config_path) "
    "VALUES ('storefront_c', 'pdf', 'c.yaml')",
    "INSERT INTO account (code) VALUES ('BANK')",
)


def alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed


def public_tables(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        names = {row[0] for row in rows}
    engine.dispose()
    return names


def test_upgrade_head_creates_section_6_tables(database_url: str) -> None:
    alembic(database_url, "upgrade", "head")

    assert SECTION_6_TABLES <= public_tables(database_url)


def test_downgrade_base_removes_application_tables(database_url: str) -> None:
    alembic(database_url, "upgrade", "head")
    alembic(database_url, "downgrade", "base")

    remaining = public_tables(database_url) - {"alembic_version"}
    assert remaining == set()


def test_cents_columns_are_bigint_and_no_float_or_numeric(database_url: str) -> None:
    alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns WHERE table_schema = 'public'"
            )
        ).all()
    engine.dispose()

    types = {(row.table_name, row.column_name): row.data_type for row in rows}
    assert {key for key in types if key[1].endswith("_cents")} == CENTS_COLUMNS
    assert {types[key] for key in CENTS_COLUMNS} == {"bigint"}
    assert {types[("rollforward_row", name)] for name in ROLLFORWARD_MONEY} == {"bigint"}
    assert not [row for row in rows if row.data_type in FLOAT_TYPES]


def test_seller_alias_rejects_duplicate_source_code_and_external_ref(
    database_url: str,
) -> None:
    alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for statement in SEED[:3]:
            connection.execute(text(statement))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text(SEED[2]))
    engine.dispose()


def test_unknown_status_kind_line_type_or_case_is_rejected(database_url: str) -> None:
    alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for statement in SEED:
            connection.execute(text(statement))
    for statement in REJECTED:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(statement))
    engine.dispose()
