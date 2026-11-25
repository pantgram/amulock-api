import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base
from app.models.base import uuid_pk
from app.models.enums import claim_source_enum, claim_status_enum, contact_type_enum
from app.utils import contact

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.position import Position


class Claim(Base):
    """One guest's right to collect their item(s) from one event.

    pending → stored → collected; pending → cancelled; stored → unclaimed (event closed) → collected.
    """

    __tablename__ = "claims"
    __table_args__ = (
        sa.CheckConstraint("status <> 'stored' OR position_id IS NOT NULL", name="claims_check"),
        sa.Index("claims_event_id_status_idx", "event_id", "status"),
        sa.Index("claims_event_id_contact_hash_idx", "event_id", "contact_hash"),
        # A position holds at most one stored claim per event.
        sa.Index(
            "claims_one_per_position",
            "event_id",
            "position_id",
            unique=True,
            postgresql_where=sa.text("status = 'stored'"),
            sqlite_where=sa.text("status = 'stored'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, sa.ForeignKey("events.id"), nullable=False)
    # NULL while pending.
    position_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, sa.ForeignKey("positions.id"))
    guest_token: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    contact_type: Mapped[str] = mapped_column(contact_type_enum, nullable=False)
    # Fernet ciphertext of the normalized contact; nullable so it can be erased while the hash stays.
    contact_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    # HMAC-SHA256 of the normalized contact: lets staff find claims by phone or email.
    contact_hash: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(claim_status_enum, nullable=False, server_default="pending")
    source: Mapped[str] = mapped_column(claim_source_enum, nullable=False)
    note: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )
    stored_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    collected_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    event: Mapped["Event"] = relationship("Event")
    position: Mapped["Position | None"] = relationship("Position")

    @property
    def contact_hint(self) -> str | None:
        """Masked contact for staff screens, e.g. "+30•••••4567" or "a•••@example.com"."""
        if self.contact_encrypted is None:
            return None
        return contact.mask(self.contact_type, contact.decrypt(self.contact_encrypted))
