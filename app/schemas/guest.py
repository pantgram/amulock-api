from datetime import datetime

from app.schemas.base import CamelModel
from app.schemas.common import ClaimStatus, ContactInput, Token


class GuestEventResponse(CamelModel):
    name: str
    starts_at: datetime
    offer_text: str | None


class GuestCounterResponse(CamelModel):
    """What the counter QR opens: the venue and its open event (null when the cloakroom is closed)."""

    venue_name: str
    event: GuestEventResponse | None


class GuestClaimCreate(ContactInput):
    counter_token: Token


class GuestClaimResponse(CamelModel):
    """What the guest sees. Never includes the position or other guests' data."""

    guest_token: Token
    status: ClaimStatus
    venue_name: str
    event: GuestEventResponse
    created_at: datetime
