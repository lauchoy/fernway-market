"""Initial SPEC section 6 schema.

Revision ID: 0001_schema
Revises:
Create Date: 2026-10-19

Applies the repository metadata. Replace this body with a SQL snapshot before
a later revision adds columns to these tables.
"""

from collections.abc import Sequence

from alembic import op

from fernway.repositories.schema import metadata

revision: str = "0001_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    metadata.drop_all(op.get_bind())
