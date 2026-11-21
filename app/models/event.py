from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.enums import event_status_enum

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.venue import Venue


class Event(Base):
    """One cloakroom session, e.g. a club night. Claims belong to exactly one event."""

    __tablename__ = "events"
    __table_args__ = (
        # At most one non-closed event per venue.
        sa.Index(
            "uq_events_one_active_per_venue",
            "venue_id",
            unique=True,
            postgresql_where=sa.text("status <> 'CLOSED'"),
            sqlite_where=sa.text("status <> 'CLOSED'"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    status: Mapped[str] = mapped_column(event_status_enum, nullable=False, server_default="OPEN")
    opened_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )
    closed_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    venue: Mapped["Venue"] = relationship("Venue", back_populates="events")
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="event")
