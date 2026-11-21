import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.common import ClaimStatus, ClaimToken, EventStatus, ItemCategory, ShortCode


class VenueResponse(CamelModel):
    id: int
    name: str
    slug: str
    locale: str
    timezone: str


class CurrentEventResponse(CamelModel):
    id: int
    name: str
    status: EventStatus
    opened_at: datetime
    counts: dict[ClaimStatus, int] = Field(description="Claims per status in this event.")


class HookRef(CamelModel):
    id: int
    rack: str
    number: int
    label: str = Field(examples=["B-12"], description="Show this in large type at pickup.")


class HookStateResponse(CamelModel):
    id: int
    rack: str
    number: int
    label: str = Field(examples=["B-12"])
    active: bool
    occupied: bool = Field(description="Holds a stored claim right now.")


class VenueClaimResponse(CamelModel):
    id: int
    claim_token: ClaimToken
    short_code: ShortCode
    status: ClaimStatus
    item_category: ItemCategory
    item_count: int
    note: str | None
    hook: HookRef | None
    has_phone: bool
    created_at: datetime
    stored_at: datetime | None
    returned_at: datetime | None


class DropOffRequest(CamelModel):
    scan_id: uuid.UUID = Field(description="Client-generated. Replays return the original result.")
    claim_token: ClaimToken
    hook_id: int | None = Field(None, description="The hook the attendant chose. Omit to let the API assign one.")
    item_category: ItemCategory = "COAT"
    item_count: int = Field(1, ge=1, le=20)
    note: str | None = Field(None, max_length=200)


class PickupRequest(CamelModel):
    scan_id: uuid.UUID = Field(description="Client-generated. Replays return the original result.")
    claim_token: ClaimToken
