from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.models.venue import Venue


class Hook(Base):
    """One numbered spot in the cloakroom: rack "B", number 12 → "B-12"."""

    __tablename__ = "hooks"
    __table_args__ = (sa.UniqueConstraint("venue_id", "rack", "number", name="uq_hooks_venue_rack_number"),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rack: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )

    venue: Mapped["Venue"] = relationship("Venue", back_populates="hooks")

    @property
    def label(self) -> str:
        return f"{self.rack}-{self.number}"
