import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

API_ROOT = Path(__file__).resolve().parents[2]
TABLES = {
    "account", "approval", "audit_event", "cycle", "cycle_item", "exception",
    "funding_file", "funding_line", "hold", "journal_entry", "journal_line",
    "open_item", "order", "refund", "rollforward_row", "seller", "seller_alias",
    "source",
}


def alembic(database_url: str, *args: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


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
    assert TABLES <= public_tables(database_url)


def test_downgrade_base_removes_application_tables(database_url: str) -> None:
    alembic(database_url, "upgrade", "head")
    alembic(database_url, "downgrade", "base")
    assert public_tables(database_url) - {"alembic_version"} == set()
