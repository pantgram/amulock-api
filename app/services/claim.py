"""Claim lifecycle for the Venue and Guest apps. Sessions auto-commit in get_db, so nothing here commits.

    pending ──store──► stored ──collect──► collected
       │                 │                    ▲
     cancel        event closes               │
       ▼                 ▼                    │
   cancelled         unclaimed ───collect─────┘

Closing an event also cancels its pending claims (see services.venue.close_event).
"""

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.models import Claim, Event, Position, Venue
from app.schemas.common import ContactInput
from app.schemas.guest import GuestClaimCreate
from app.schemas.venue import ClaimCreateRequest, ClaimSearchRequest
from app.services.venue import find_open_event
from app.utils import contact
from app.utils.errors import (
    ClaimNotFoundError,
    ClaimWrongStateError,
    CounterNotFoundError,
    EventNotFoundError,
    EventNotOpenError,
    NoFreePositionError,
    PositionNotFoundError,
    PositionOccupiedError,
)
from app.utils.tokens import TokenKind, new_token

SEARCH_LIMIT = 50


def _venue_claims():
    """Claims joined to their event, so queries can filter by Event.venue_id."""
    return select(Claim).join(Claim.event).options(contains_eager(Claim.event), selectinload(Claim.position))


def _new_claim(event: Event, data: ContactInput, source: str, note: str | None = None) -> Claim:
    return Claim(
        event_id=event.id,
        guest_token=new_token(TokenKind.CLAIM),
        contact_type=data.contact_type,
        contact_encrypted=contact.encrypt(data.contact),
        contact_hash=contact.hash_contact(data.contact),
        source=source,
        note=note,
    )


async def _reload(db: AsyncSession, venue: Venue, claim_id: uuid.UUID) -> Claim:
    """Fresh copy with server defaults and the position loaded, ready to serialize."""
    stmt = _venue_claims().where(Claim.id == claim_id, Event.venue_id == venue.id)
    return await db.scalar(stmt.execution_options(populate_existing=True))


async def _get_for_update(db: AsyncSession, venue: Venue, claim_id: uuid.UUID) -> Claim:
    stmt = _venue_claims().where(Claim.id == claim_id, Event.venue_id == venue.id).with_for_update(of=Claim)
    claim = await db.scalar(stmt)
    if claim is None:
        raise ClaimNotFoundError()
    return claim


async def _pick_position(
    db: AsyncSession, venue: Venue, event_id: uuid.UUID, position_id: uuid.UUID | None
) -> Position:
    """The chosen position if free, else the next free active one (lowest zone, then number)."""
    occupied = select(Claim.position_id).where(
        Claim.event_id == event_id, Claim.status == "stored", Claim.position_id.is_not(None)
    )
    if position_id is not None:
        position = await db.scalar(
            select(Position).where(Position.id == position_id, Position.venue_id == venue.id, Position.is_active)
        )
        if position is None:
            raise PositionNotFoundError()
        taken = exists().where(Claim.event_id == event_id, Claim.status == "stored", Claim.position_id == position.id)
        if await db.scalar(select(taken)):
            raise PositionOccupiedError(f"{position.label} already holds a stored claim")
        return position
    position = await db.scalar(
        select(Position)
        .where(Position.venue_id == venue.id, Position.is_active, Position.id.not_in(occupied))
        .order_by(Position.zone, Position.number)
        .limit(1)
    )
    if position is None:
        raise NoFreePositionError()
    return position


async def _store(db: AsyncSession, venue: Venue, claim: Claim, position_id: uuid.UUID | None) -> None:
    if claim.event.status != "open":
        raise EventNotOpenError()
    position = await _pick_position(db, venue, claim.event_id, position_id)
    claim.position_id = position.id
    claim.status = "stored"
    claim.stored_at = func.now()
    try:
        await db.flush()
    except IntegrityError:
        # Another attendant stored a claim on the same position a moment ago (claims_one_per_position).
        raise PositionOccupiedError(f"{position.label} was just taken; try again")


# ---------- Venue app ----------


async def create_staff_claim(db: AsyncSession, venue: Venue, data: ClaimCreateRequest) -> Claim:
    """A claim in the open event, optionally stored at once. Errors: EventNotOpenError, plus store()'s."""
    event = await find_open_event(db, venue.id)
    if event is None:
        raise EventNotOpenError()
    claim = _new_claim(event, data, source="staff", note=data.note)
    claim.event = event
    db.add(claim)
    await db.flush()
    if data.store or data.position_id is not None:
        await _store(db, venue, claim, data.position_id)
    return await _reload(db, venue, claim.id)


async def get_claim(db: AsyncSession, venue: Venue, claim_id: uuid.UUID) -> Claim:
    """Errors: ClaimNotFoundError."""
    claim = await _reload(db, venue, claim_id)
    if claim is None:
        raise ClaimNotFoundError()
    return claim


async def get_claim_by_token(db: AsyncSession, venue: Venue, guest_token: str) -> Claim:
    """What staff get when scanning a guest's claim QR. Errors: ClaimNotFoundError."""
    claim = await db.scalar(_venue_claims().where(Claim.guest_token == guest_token, Event.venue_id == venue.id))
    if claim is None:
        raise ClaimNotFoundError()
    return claim


async def list_event_claims(db: AsyncSession, venue: Venue, event_id: uuid.UUID, status: str | None) -> list[Claim]:
    """Errors: EventNotFoundError."""
    if await db.scalar(select(Event.id).where(Event.id == event_id, Event.venue_id == venue.id)) is None:
        raise EventNotFoundError()
    stmt = _venue_claims().where(Claim.event_id == event_id).order_by(Claim.created_at)
    if status is not None:
        stmt = stmt.where(Claim.status == status)
    return list((await db.scalars(stmt)).all())


async def search_claims(db: AsyncSession, venue: Venue, data: ClaimSearchRequest) -> list[Claim]:
    """Claims with this exact contact, newest first (at most 50)."""
    stmt = (
        _venue_claims()
        .where(Event.venue_id == venue.id, Claim.contact_hash == contact.hash_contact(data.contact))
        .order_by(Claim.created_at.desc())
        .limit(SEARCH_LIMIT)
    )
    if data.event_id is not None:
        stmt = stmt.where(Claim.event_id == data.event_id)
    return list((await db.scalars(stmt)).all())


async def store_claim(db: AsyncSession, venue: Venue, claim_id: uuid.UUID, position_id: uuid.UUID | None) -> Claim:
    """pending → stored, at the chosen position or the next free one.

    Errors: ClaimNotFoundError, ClaimWrongStateError, EventNotOpenError, PositionNotFoundError,
    PositionOccupiedError, NoFreePositionError.
    """
    claim = await _get_for_update(db, venue, claim_id)
    if claim.status != "pending":
        raise ClaimWrongStateError(f"Only a pending claim can be stored; this one is {claim.status}")
    await _store(db, venue, claim, position_id)
    return await _reload(db, venue, claim.id)


async def collect_claim(db: AsyncSession, venue: Venue, claim_id: uuid.UUID) -> Claim:
    """stored or unclaimed → collected. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    claim = await _get_for_update(db, venue, claim_id)
    if claim.status not in ("stored", "unclaimed"):
        raise ClaimWrongStateError(f"Only a stored or unclaimed claim can be collected; this one is {claim.status}")
    claim.status = "collected"
    claim.collected_at = func.now()
    await db.flush()
    return await _reload(db, venue, claim.id)


async def cancel_claim(db: AsyncSession, venue: Venue, claim_id: uuid.UUID) -> Claim:
    """pending → cancelled. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    claim = await _get_for_update(db, venue, claim_id)
    if claim.status != "pending":
        raise ClaimWrongStateError(f"Only a pending claim can be cancelled; this one is {claim.status}")
    claim.status = "cancelled"
    await db.flush()
    return await _reload(db, venue, claim.id)


# ---------- Guest app ----------


async def _venue_by_counter(db: AsyncSession, counter_token: str) -> Venue:
    venue = await db.scalar(select(Venue).where(Venue.counter_token == counter_token))
    if venue is None:
        raise CounterNotFoundError()
    return venue


def _guest_view(claim: Claim) -> dict:
    return {
        "guest_token": claim.guest_token,
        "status": claim.status,
        "venue_name": claim.event.venue.name,
        "event": claim.event,
        "created_at": claim.created_at,
    }


async def _guest_claim(db: AsyncSession, guest_token: str) -> Claim:
    claim = await db.scalar(
        select(Claim)
        .where(Claim.guest_token == guest_token)
        .options(joinedload(Claim.event).joinedload(Event.venue))
        .execution_options(populate_existing=True)
    )
    if claim is None:
        raise ClaimNotFoundError()
    return claim


async def get_counter(db: AsyncSession, counter_token: str) -> dict:
    """Errors: CounterNotFoundError."""
    venue = await _venue_by_counter(db, counter_token)
    return {"venue_name": venue.name, "event": await find_open_event(db, venue.id)}


async def create_guest_claim(db: AsyncSession, data: GuestClaimCreate) -> dict:
    """A pending claim in the venue's open event. Errors: CounterNotFoundError, EventNotOpenError."""
    venue = await _venue_by_counter(db, data.counter_token)
    event = await find_open_event(db, venue.id)
    if event is None:
        raise EventNotOpenError()
    claim = _new_claim(event, data, source="guest")
    db.add(claim)
    await db.flush()
    return _guest_view(await _guest_claim(db, claim.guest_token))


async def get_guest_claim(db: AsyncSession, guest_token: str) -> dict:
    """Errors: ClaimNotFoundError."""
    return _guest_view(await _guest_claim(db, guest_token))


async def cancel_guest_claim(db: AsyncSession, guest_token: str) -> dict:
    """The guest changed their mind before drop-off. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    claim = await _guest_claim(db, guest_token)
    if claim.status != "pending":
        raise ClaimWrongStateError("Only a claim that hasn't been dropped off can be cancelled")
    claim.status = "cancelled"
    await db.flush()
    return _guest_view(claim)
