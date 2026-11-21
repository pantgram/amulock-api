"""Claim lifecycle. Routers call these; sessions auto-commit in get_db, so nothing here commits.

The guest and drop-off/pickup flows are agreed in the contract (openapi.json) but not built yet:
they raise NotImplementedYetError until the thin slice lands.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.schemas.venue import DropOffRequest, PickupRequest
from app.utils.errors import NotImplementedYetError

# Allowed status transitions. See docs/decisions.md D1.
CLAIM_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"STORED", "VOID"},
    "STORED": {"RETURNED", "UNCLAIMED"},
    "UNCLAIMED": {"RETURNED"},
    "RETURNED": set(),
    "VOID": set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in CLAIM_TRANSITIONS[current]


async def create_guest_claim(db: AsyncSession, counter_token: str):
    """Create a claim in the venue's open event. Errors: CounterNotFoundError, EventNotOpenError."""
    raise NotImplementedYetError()


async def get_guest_claim(db: AsyncSession, claim_token: str):
    """Errors: ClaimNotFoundError."""
    raise NotImplementedYetError()


async def set_guest_phone(db: AsyncSession, claim_token: str, phone: str) -> None:
    """Errors: ClaimNotFoundError, ClaimWrongStateError (RETURNED or VOID)."""
    raise NotImplementedYetError()


async def drop_off(db: AsyncSession, venue: Venue, data: DropOffRequest, actor_clerk_user_id: str | None):
    """CREATED → STORED on the chosen hook, or the next free one (docs/decisions.md D4a).

    Errors: ClaimNotFoundError, HookNotFoundError, HookOccupiedError, NoFreeHookError,
    ClaimWrongStateError, EventNotOpenError.
    """
    raise NotImplementedYetError()


async def lookup_claim(db: AsyncSession, venue: Venue, claim_token: str | None, short_code: str | None):
    """Errors: ClaimNotFoundError."""
    raise NotImplementedYetError()


async def pickup(db: AsyncSession, venue: Venue, data: PickupRequest, actor_clerk_user_id: str | None):
    """STORED or UNCLAIMED → RETURNED. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    raise NotImplementedYetError()
