"""SPEC section 6 tables.

Money columns are BIGINT. CHECK lists are the values named in SPEC sections 6 and 7.
Other status fields stay plain TEXT (DECISIONS.md item 8).
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

seller = Table(
    "seller",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("payout_token", Text, nullable=False),
    Column("status", Text, nullable=False),
)

seller_alias = Table(
    "seller_alias",
    metadata,
    Column("source_code", Text, ForeignKey("source.code"), primary_key=True),
    Column("external_ref", Text, primary_key=True),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), nullable=False),
)

source = Table(
    "source",
    metadata,
    Column("code", Text, primary_key=True),
    Column("format", Text, nullable=False),
    Column("mapping_config_path", Text, nullable=False),
    CheckConstraint("format IN ('csv', 'xlsx')", name="ck_source_format"),
)

order_table = Table(
    "order",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("source_code", Text, ForeignKey("source.code"), nullable=False),
    Column("order_ref", Text, nullable=False),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), nullable=False),
    Column("gross_cents", BigInteger, nullable=False),
    Column("fee_cents", BigInteger, nullable=False),
    Column("net_cents", BigInteger, nullable=False),
    Column("delivered_at", DateTime(timezone=True), nullable=False),
)

hold = Table(
    "hold",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("order_id", BigInteger, ForeignKey("order.id"), nullable=False),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("eligible_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
    CheckConstraint(
        "status IN ('held', 'partially_released', 'released', 'refunded')",
        name="ck_hold_status",
    ),
)

refund = Table(
    "refund",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("order_ref", Text, nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("kind", Text, nullable=False),
    Column("processed_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("kind IN ('full', 'partial')", name="ck_refund_kind"),
)

funding_file = Table(
    "funding_file",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("cycle_id", Text, ForeignKey("cycle.id"), nullable=False),
    Column("sha256", Text, nullable=False),
    Column("uploaded_by", Text, nullable=False),
)

funding_line = Table(
    "funding_line",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column(
        "funding_file_id",
        BigInteger,
        ForeignKey("funding_file.id"),
        nullable=False,
    ),
    Column("seller_ref", Text, nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("line_type", Text, nullable=False),
    # NULL is an untyped fee adjustment. Allowed values are not defined (DECISIONS.md item 7).
    Column("adjustment_type", Text, nullable=True),
    CheckConstraint(
        "line_type IN ('payout', 'fee_adjustment', 'reserve')",
        name="ck_funding_line_type",
    ),
)

cycle = Table(
    "cycle",
    metadata,
    Column("id", Text, primary_key=True),
    Column("period_end", Date, nullable=False),
    Column("status", Text, nullable=False),
    Column("ruleset_hash", Text, nullable=False),
    Column("prepared_by", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ("
        "'DRAFT', 'INGESTED', 'MATCHED', 'VALIDATED', 'TIED_OUT', "
        "'SUBMITTED', 'APPROVED', 'POSTED', 'CLOSED', 'BLOCKED', 'REJECTED')",
        name="ck_cycle_status",
    ),
)

cycle_item_case = Column("case", Text, nullable=False)
cycle_item = Table(
    "cycle_item",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("cycle_id", Text, ForeignKey("cycle.id"), nullable=False),
    Column("hold_id", BigInteger, ForeignKey("hold.id"), nullable=False),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), nullable=False),
    cycle_item_case,
    Column("proposed_release_cents", BigInteger, nullable=False),
    Column("residual_cents", BigInteger, nullable=False),
    Column("blocked", Boolean, nullable=False),
    Column("block_reason", Text, nullable=False),
    Column("block_owner", Text, nullable=False),
    CheckConstraint(
        cycle_item_case.in_(("EXACT", "PARTIAL", "ZERO", "ADJUSTED")),
        name="ck_cycle_item_case",
    ),
)

exception = Table(
    "exception",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("cycle_id", Text, ForeignKey("cycle.id"), nullable=False),
    Column("item_id", BigInteger, ForeignKey("cycle_item.id"), nullable=True),
    Column("code", Text, nullable=False),
    Column("detail_json", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("resolved_by", Text, nullable=False),
    Column("resolution_note", Text, nullable=False),
)

approval = Table(
    "approval",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("cycle_id", Text, ForeignKey("cycle.id"), nullable=False),
    Column("approver", Text, nullable=False),
    Column("decision", Text, nullable=False),
    Column("comment", Text, nullable=False),
    Column("decided_at", DateTime(timezone=True), nullable=False),
)

account = Table(
    "account",
    metadata,
    Column("code", Text, primary_key=True),
    CheckConstraint(
        "code IN ('SELLER_PAYABLE', 'CASH_CLEARING', 'REFUNDS', 'FEE_ADJ')",
        name="ck_account_code",
    ),
)

journal_entry = Table(
    "journal_entry",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("cycle_id", Text, ForeignKey("cycle.id"), nullable=False),
    Column("idempotency_key", Text, nullable=False),
    Column("posted_by", Text, nullable=False),
    Column("posted_at", DateTime(timezone=True), nullable=False),
    Column("memo", Text, nullable=False),
)

journal_line = Table(
    "journal_line",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("entry_id", BigInteger, ForeignKey("journal_entry.id"), nullable=False),
    Column("account_code", Text, ForeignKey("account.code"), nullable=False),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), nullable=False),
    Column("debit_cents", BigInteger, nullable=False),
    Column("credit_cents", BigInteger, nullable=False),
)

open_item = Table(
    "open_item",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("hold_id", BigInteger, ForeignKey("hold.id"), nullable=False),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("cleared_cents", BigInteger, nullable=False),
    Column("status", Text, nullable=False),
)

rollforward_row = Table(
    "rollforward_row",
    metadata,
    Column("cycle_id", Text, ForeignKey("cycle.id"), primary_key=True),
    Column("seller_id", BigInteger, ForeignKey("seller.id"), primary_key=True),
    Column("opening", BigInteger, nullable=False),
    Column("new_holds", BigInteger, nullable=False),
    Column("released", BigInteger, nullable=False),
    Column("refunded", BigInteger, nullable=False),
    Column("closing", BigInteger, nullable=False),
)

audit_event = Table(
    "audit_event",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("actor", Text, nullable=False),
    Column("cycle_id", Text, ForeignKey("cycle.id"), nullable=False),
    Column("kind", Text, nullable=False),
    Column("payload_json", JSONB, nullable=False),
)
