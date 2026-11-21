from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.common import ClaimStatus, ClaimToken, CounterToken, ShortCode


class GuestClaimCreate(CamelModel):
    counter_token: CounterToken


class GuestClaimResponse(CamelModel):
    """What the guest sees. Never includes the hook or other guests' data."""

    claim_token: ClaimToken
    short_code: ShortCode
    status: ClaimStatus
    venue_name: str
    event_name: str
    qr_url: str = Field(description="Encode this in the claim QR shown on the guest's phone.")
    has_phone: bool
    created_at: datetime


class GuestPhoneUpdate(CamelModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$", description="E.164, e.g. +306912345678")
    consent: bool = Field(description="Must be true: the guest agrees to one SMS about this claim.")
