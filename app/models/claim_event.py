import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.enums import claim_event_type_enum

if TYPE_CHECKING:
    from app.models.claim import Claim


class ClaimEvent(Base):
    """Append-only history of a claim. Every claim change writes one row. See D1 and D4."""

    __tablename__ = "claim_events"

    id: Mapped[int] = mapped_column(sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(claim_event_type_enum, nullable=False)
    # Who did it: the Clerk user of the Venue app, or None for guest/system actions.
    actor_clerk_user_id: Mapped[str | None] = mapped_column(sa.String(64))
    # Client-generated idempotency key for Venue app writes.
    scan_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, unique=True)
    at: Mapped[sa.DateTime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())
    payload: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )

    claim: Mapped["Claim"] = relationship("Claim", back_populates="history")
