from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.enums import claim_status_enum, item_category_enum

if TYPE_CHECKING:
    from app.models.claim_event import ClaimEvent
    from app.models.event import Event
    from app.models.hook import Hook


class Claim(Base):
    """One guest's right to collect their item(s) at one event. Lifecycle: docs/decisions.md D1."""

    __tablename__ = "claims"
    __table_args__ = (
        sa.UniqueConstraint("event_id", "short_code", name="uq_claims_event_short_code"),
        # A hook holds at most one stored claim.
        sa.Index(
            "uq_claims_one_stored_per_hook",
            "hook_id",
            unique=True,
            postgresql_where=sa.text("status = 'STORED'"),
            sqlite_where=sa.text("status = 'STORED'"),
        ),
        sa.CheckConstraint("item_count BETWEEN 1 AND 20", name="ck_claims_item_count_range"),
        sa.CheckConstraint("status <> 'STORED' OR hook_id IS NOT NULL", name="ck_claims_stored_has_hook"),
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hook_id: Mapped[int | None] = mapped_column(sa.Integer, sa.ForeignKey("hooks.id", ondelete="SET NULL"))
    claim_token: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    short_code: Mapped[str] = mapped_column(sa.String(6), nullable=False)
    status: Mapped[str] = mapped_column(claim_status_enum, nullable=False, server_default="CREATED")
    item_category: Mapped[str] = mapped_column(item_category_enum, nullable=False, server_default="COAT")
    item_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    note: Mapped[str | None] = mapped_column(sa.String(200))
    # Opt-in, encrypted, deleted 30 days after the event closes. See D7.
    guest_phone_enc: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )
    stored_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    returned_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    event: Mapped["Event"] = relationship("Event", back_populates="claims")
    hook: Mapped["Hook | None"] = relationship("Hook")
    history: Mapped[list["ClaimEvent"]] = relationship("ClaimEvent", back_populates="claim", order_by="ClaimEvent.id")
