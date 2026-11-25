"""The database enforces the cloakroom's core rules even if a service has a bug."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Claim, Event, Position
from app.utils import contact
from app.utils.tokens import TokenKind, new_token


def _claim(event_id, **kwargs) -> Claim:
    return Claim(
        event_id=event_id,
        guest_token=new_token(TokenKind.CLAIM),
        contact_type="phone",
        contact_hash=contact.hash_contact("+306912345678"),
        source="staff",
        **kwargs,
    )


async def _open_event(session, venue) -> Event:
    return await session.scalar(select(Event).where(Event.venue_id == venue.id, Event.status == "open"))


async def _position(session, venue, number=1) -> Position:
    return await session.scalar(select(Position).where(Position.venue_id == venue.id, Position.number == number))


async def test_one_open_event_per_venue(session, venue):
    session.add(Event(venue_id=venue.id, name="Second night", starts_at=datetime.now(timezone.utc), status="open"))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_many_drafts_are_fine(session, venue):
    for name in ("Fri", "Sat"):
        session.add(Event(venue_id=venue.id, name=name, starts_at=datetime.now(timezone.utc)))

    await session.flush()


async def test_position_numbers_are_unique_per_zone(session, venue):
    session.add(Position(venue_id=venue.id, zone="A", number=1))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_position_number_is_positive(session, venue):
    session.add(Position(venue_id=venue.id, zone="Z", number=0))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_stored_claim_needs_a_position(session, venue):
    session.add(_claim((await _open_event(session, venue)).id, status="stored"))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_one_stored_claim_per_position(session, venue):
    event = await _open_event(session, venue)
    position = await _position(session, venue)
    session.add_all([_claim(event.id, status="stored", position_id=position.id) for _ in range(2)])

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_collected_claims_free_the_position(session, venue):
    event = await _open_event(session, venue)
    position = await _position(session, venue)
    session.add(_claim(event.id, status="collected", position_id=position.id))
    session.add(_claim(event.id, status="stored", position_id=position.id))

    await session.flush()
