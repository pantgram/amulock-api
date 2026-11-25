"""initial schema: venues, positions, events, claims

Revision ID: 0001
Revises:
Create Date: 2026-11-25 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUMS = ("claim_source", "contact_type", "claim_status", "event_status")


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "venues",
        _uuid_pk(),
        sa.Column("clerk_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("counter_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clerk_id"),
        sa.UniqueConstraint("counter_token"),
    )
    op.create_table(
        "positions",
        _uuid_pk(),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("zone", sa.Text(), server_default="", nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("number > 0", name="positions_number_check"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("venue_id", "zone", "number", name="positions_venue_id_zone_number_key"),
    )
    op.create_table(
        "events",
        _uuid_pk(),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("offer_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "open", "closed", name="event_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("events_venue_id_starts_at_idx", "events", ["venue_id", sa.text("starts_at DESC")], unique=False)
    op.create_index(
        "events_one_open_per_venue",
        "events",
        ["venue_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
        sqlite_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "claims",
        _uuid_pk(),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("guest_token", sa.Text(), nullable=False),
        sa.Column("contact_type", sa.Enum("phone", "email", name="contact_type"), nullable=False),
        sa.Column("contact_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("contact_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "stored", "collected", "unclaimed", "cancelled", name="claim_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("source", sa.Enum("guest", "staff", name="claim_source"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("stored_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("collected_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status <> 'stored' OR position_id IS NOT NULL", name="claims_check"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guest_token"),
    )
    op.create_index("claims_event_id_status_idx", "claims", ["event_id", "status"], unique=False)
    op.create_index("claims_event_id_contact_hash_idx", "claims", ["event_id", "contact_hash"], unique=False)
    # A position holds at most one stored claim per event.
    op.create_index(
        "claims_one_per_position",
        "claims",
        ["event_id", "position_id"],
        unique=True,
        postgresql_where=sa.text("status = 'stored'"),
        sqlite_where=sa.text("status = 'stored'"),
    )


def downgrade() -> None:
    op.drop_table("claims")
    op.drop_table("events")
    op.drop_table("positions")
    op.drop_table("venues")
    for enum_name in ENUMS:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
