import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.position import Position


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = uuid_pk()
    # The venue's Clerk account (the token's `sub`), shared on its counter devices.
    clerk_id: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Permanent token encoded in the counter QR; guests use it to open a claim.
    counter_token: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )

    events: Mapped[list["Event"]] = relationship("Event", back_populates="venue")
    positions: Mapped[list["Position"]] = relationship("Position", back_populates="venue")
