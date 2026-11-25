import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import uuid_pk

if TYPE_CHECKING:
    from app.models.venue import Venue


class Position(Base):
    """One numbered spot in the cloakroom: zone "B", number 12 → "B-12" (no zone → "12")."""

    __tablename__ = "positions"
    __table_args__ = (
        sa.UniqueConstraint("venue_id", "zone", "number", name="positions_venue_id_zone_number_key"),
        sa.CheckConstraint("number > 0", name="positions_number_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    venue_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("venues.id"), nullable=False)
    zone: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())

    venue: Mapped["Venue"] = relationship("Venue", back_populates="positions")

    @property
    def label(self) -> str:
        return f"{self.zone}-{self.number}" if self.zone else str(self.number)
