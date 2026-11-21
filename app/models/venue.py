from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.hook import Hook


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(60), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(sa.String(64), nullable=False, server_default="Europe/Athens")
    locale: Mapped[str] = mapped_column(sa.String(5), nullable=False, server_default="el")
    # Encoded in the counter QR. Rotatable. See docs/decisions.md D2.
    counter_token: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    # The venue's Clerk account (the `sub` claim), shared on its counter devices. See D6.
    clerk_user_id: Mapped[str | None] = mapped_column(sa.String(64), unique=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )

    events: Mapped[list["Event"]] = relationship("Event", back_populates="venue")
    hooks: Mapped[list["Hook"]] = relationship("Hook", back_populates="venue")
