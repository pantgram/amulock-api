import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import uuid_pk
from app.models.enums import event_status_enum

if TYPE_CHECKING:
    from app.models.venue import Venue


class Event(Base):
    """One cloakroom session, e.g. a club night: draft → open → closed."""

    __tablename__ = "events"
    __table_args__ = (
        sa.Index("events_venue_id_starts_at_idx", "venue_id", sa.text("starts_at DESC")),
        # At most one open event per venue.
        sa.Index(
            "events_one_open_per_venue",
            "venue_id",
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    venue_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("venues.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    starts_at: Mapped[sa.DateTime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    offer_text: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(event_status_enum, nullable=False, server_default="draft")
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )
    opened_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    closed_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    venue: Mapped["Venue"] = relationship("Venue", back_populates="events")
