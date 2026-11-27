"""Events and positions for the Venue app. Sessions auto-commit in get_db, so nothing here commits."""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Event, Position, Venue
from app.schemas.venue import (
    EventCreateRequest,
    EventUpdateRequest,
    PositionCreateRequest,
    PositionUpdateRequest,
    VenueUpdateRequest,
)
from app.utils.errors import (
    EventAlreadyOpenError,
    EventNotFoundError,
    EventNotOpenError,
    EventWrongStateError,
    PositionAlreadyExistsError,
    PositionNotFoundError,
)
from app.utils.tokens import TokenKind, new_token

# ---------- venue ----------


async def update_venue(db: AsyncSession, venue: Venue, data: VenueUpdateRequest) -> Venue:
    venue.name = data.name
    await db.flush()
    return venue


# ---------- events ----------


async def find_open_event(db: AsyncSession, venue_id: uuid.UUID) -> Event | None:
    return await db.scalar(select(Event).where(Event.venue_id == venue_id, Event.status == "open"))


async def get_current_event(db: AsyncSession, venue: Venue) -> Event:
    """Errors: EventNotOpenError."""
    event = await find_open_event(db, venue.id)
    if event is None:
        raise EventNotOpenError()
    return event


async def list_events(db: AsyncSession, venue: Venue) -> list[Event]:
    """Newest first."""
    rows = await db.scalars(select(Event).where(Event.venue_id == venue.id).order_by(Event.starts_at.desc()))
    return list(rows.all())


async def get_event(db: AsyncSession, venue: Venue, event_id: uuid.UUID) -> Event:
    """Errors: EventNotFoundError."""
    event = await db.scalar(select(Event).where(Event.id == event_id, Event.venue_id == venue.id))
    if event is None:
        raise EventNotFoundError()
    return event


async def create_event(db: AsyncSession, venue: Venue, data: EventCreateRequest) -> Event:
    """A draft event; open it when the cloakroom opens."""
    event = Event(venue_id=venue.id, name=data.name.strip(), starts_at=data.starts_at, offer_text=data.offer_text)
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def update_event(db: AsyncSession, venue: Venue, event_id: uuid.UUID, data: EventUpdateRequest) -> Event:
    """Errors: EventNotFoundError, EventWrongStateError (closed)."""
    event = await get_event(db, venue, event_id)
    if event.status == "closed":
        raise EventWrongStateError("A closed event can't be edited")
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "starts_at"):
        if field in changes and changes[field] is None:
            changes.pop(field)
    for field, value in changes.items():
        setattr(event, field, value.strip() if field == "name" else value)
    await db.flush()
    await db.refresh(event)
    return event


async def open_event(db: AsyncSession, venue: Venue, event_id: uuid.UUID) -> Event:
    """draft → open. Errors: EventNotFoundError, EventWrongStateError, EventAlreadyOpenError."""
    event = await get_event(db, venue, event_id)
    if event.status != "draft":
        raise EventWrongStateError(f"Only a draft event can be opened; this one is {event.status}")
    if await find_open_event(db, venue.id) is not None:
        raise EventAlreadyOpenError()
    event.status = "open"
    event.opened_at = func.now()
    await db.flush()
    await db.refresh(event)
    return event


async def close_event(db: AsyncSession, venue: Venue, event_id: uuid.UUID) -> Event:
    """open → closed. Items still stored become unclaimed; pending claims are cancelled.

    Errors: EventNotFoundError, EventNotOpenError.
    """
    event = await get_event(db, venue, event_id)
    if event.status != "open":
        raise EventNotOpenError("Only an open event can be closed")
    event.status = "closed"
    event.closed_at = func.now()
    await db.execute(
        update(Claim).where(Claim.event_id == event.id, Claim.status == "stored").values(status="unclaimed"),
        execution_options={"synchronize_session": False},
    )
    await db.execute(
        update(Claim).where(Claim.event_id == event.id, Claim.status == "pending").values(status="cancelled"),
        execution_options={"synchronize_session": False},
    )
    await db.flush()
    await db.refresh(event)
    return event


# ---------- positions ----------


async def list_positions(db: AsyncSession, venue: Venue) -> list[Position]:
    """All positions ordered by zone, then number."""
    rows = await db.scalars(
        select(Position).where(Position.venue_id == venue.id).order_by(Position.zone, Position.number)
    )
    return list(rows.all())


async def create_positions(db: AsyncSession, venue: Venue, data: PositionCreateRequest) -> list[Position]:
    """Errors: PositionAlreadyExistsError (if any number in the range exists in that zone)."""
    numbers = range(data.from_number, data.to_number + 1)
    existing = await db.scalars(
        select(Position.number).where(
            Position.venue_id == venue.id, Position.zone == data.zone, Position.number.in_(numbers)
        )
    )
    taken = sorted(existing.all())
    if taken:
        label = f"{data.zone}-{taken[0]}" if data.zone else str(taken[0])
        raise PositionAlreadyExistsError(f"Position {label} already exists")
    positions = [Position(venue_id=venue.id, zone=data.zone, number=n) for n in numbers]
    db.add_all(positions)
    await db.flush()
    for position in positions:
        await db.refresh(position)
    return positions


async def update_position(
    db: AsyncSession, venue: Venue, position_id: uuid.UUID, data: PositionUpdateRequest
) -> Position:
    """Errors: PositionNotFoundError."""
    position = await db.scalar(select(Position).where(Position.id == position_id, Position.venue_id == venue.id))
    if position is None:
        raise PositionNotFoundError("Position not found")
    position.is_active = data.is_active
    await db.flush()
    return position


# ---------- accounts (Clerk webhook) ----------

# venues.name is NOT NULL; the venue replaces this through the Venue endpoints.
NEW_VENUE_NAME = "New venue"


async def find_venue_by_clerk_id(db: AsyncSession, clerk_id: str) -> Venue | None:
    return await db.scalar(select(Venue).where(Venue.clerk_id == clerk_id))


async def create_venue_for_account(db: AsyncSession, clerk_id: str) -> Venue:
    """Link a new Clerk account to a new, empty venue (no positions, no events) named
    NEW_VENUE_NAME until the venue sets its own. Idempotent: an account that already has a venue
    gets it back unchanged."""
    venue = await find_venue_by_clerk_id(db, clerk_id)
    if venue is not None:
        return venue
    venue = Venue(clerk_id=clerk_id, name=NEW_VENUE_NAME, counter_token=new_token(TokenKind.COUNTER))
    db.add(venue)
    await db.flush()
    return venue


async def remove_venue_for_account(db: AsyncSession, clerk_id: str) -> bool:
    """Delete the account's venue and its positions, but only if it never had an event: events hold
    claims and guest contacts, which are kept until contact retention is built. Returns whether it
    was deleted (False also when the account has no venue)."""
    venue = await find_venue_by_clerk_id(db, clerk_id)
    if venue is None:
        return False
    if await db.scalar(select(func.count()).select_from(Event).where(Event.venue_id == venue.id)):
        return False
    await db.execute(delete(Position).where(Position.venue_id == venue.id))
    await db.delete(venue)
    await db.flush()
    return True
