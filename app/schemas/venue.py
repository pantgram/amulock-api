import uuid
from datetime import datetime, timezone

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.schemas.base import CamelModel
from app.schemas.common import ClaimSource, ClaimStatus, ContactInput, ContactType, EventStatus, Token

MAX_POSITIONS_PER_REQUEST = 500


class VenueResponse(CamelModel):
    id: uuid.UUID
    name: str
    counter_token: Token = Field(description="Encode in the counter QR that guests scan.")


# ---------- events ----------


def _to_utc(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc) if value is not None else None


class EventCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    starts_at: AwareDatetime
    offer_text: str | None = Field(None, max_length=500, description="Shown to guests, e.g. a drinks offer.")

    _utc = field_validator("starts_at")(_to_utc)


class EventUpdateRequest(CamelModel):
    """Only the fields sent are changed. Send `offerText: null` to clear it."""

    name: str | None = Field(None, min_length=1, max_length=120)
    starts_at: AwareDatetime | None = None
    offer_text: str | None = Field(None, max_length=500)

    _utc = field_validator("starts_at")(_to_utc)


class EventResponse(CamelModel):
    id: uuid.UUID
    name: str
    starts_at: datetime
    offer_text: str | None
    status: EventStatus
    created_at: datetime
    opened_at: datetime | None
    closed_at: datetime | None


# ---------- positions ----------


class PositionCreateRequest(CamelModel):
    """Create positions `fromNumber`..`toNumber` (inclusive) in one zone."""

    zone: str = Field("", max_length=20, description='Empty for venues without zones; labels are then just "12".')
    from_number: int = Field(ge=1)
    to_number: int | None = Field(None, ge=1, description="Defaults to fromNumber.")

    @model_validator(mode="after")
    def _check_range(self):
        self.zone = self.zone.strip()
        to_number = self.to_number or self.from_number
        if to_number < self.from_number:
            raise ValueError("toNumber must be at least fromNumber")
        if to_number - self.from_number + 1 > MAX_POSITIONS_PER_REQUEST:
            raise ValueError(f"At most {MAX_POSITIONS_PER_REQUEST} positions per request")
        self.to_number = to_number
        return self


class PositionUpdateRequest(CamelModel):
    is_active: bool


class PositionResponse(CamelModel):
    id: uuid.UUID
    zone: str
    number: int
    label: str = Field(examples=["B-12"])
    is_active: bool


# ---------- claims ----------


class ClaimCreateRequest(ContactInput):
    """A claim staff create at the counter for a guest, in the open event."""

    note: str | None = Field(None, max_length=500)
    store: bool = Field(False, description="Store it right away (at positionId, or the next free position).")
    position_id: uuid.UUID | None = None


class ClaimStoreRequest(CamelModel):
    position_id: uuid.UUID | None = Field(None, description="Omit to use the next free position.")


class ClaimSearchRequest(ContactInput):
    event_id: uuid.UUID | None = Field(None, description="Omit to search every event of the venue.")


class ClaimResponse(CamelModel):
    id: uuid.UUID
    event_id: uuid.UUID
    status: ClaimStatus
    source: ClaimSource
    contact_type: ContactType
    contact_hint: str | None = Field(examples=["+30•••••••4567"], description="Masked; null once erased.")
    note: str | None
    position: PositionResponse | None
    created_at: datetime
    stored_at: datetime | None
    collected_at: datetime | None
