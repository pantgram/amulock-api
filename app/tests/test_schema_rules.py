"""The database enforces the cloakroom's core rules even if a service has a bug."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Claim, Event
from app.models.hook import Hook
from app.utils.tokens import TokenKind, new_short_code, new_token


async def _claim(session, venue, event_id, hook_id=None, status="CREATED"):
    claim = Claim(
        venue_id=venue.id,
        event_id=event_id,
        hook_id=hook_id,
        claim_token=new_token(TokenKind.CLAIM),
        short_code=new_short_code(),
        status=status,
    )
    session.add(claim)
    await session.flush()
    return claim


async def _event_and_hook(session, venue):
    event = (await session.execute(select(Event).where(Event.venue_id == venue.id))).scalar_one()
    hook = (await session.execute(select(Hook).where(Hook.venue_id == venue.id).limit(1))).scalar_one()
    return event, hook


async def test_one_stored_claim_per_hook(session, venue):
    event, hook = await _event_and_hook(session, venue)
    await _claim(session, venue, event.id, hook.id, status="STORED")

    with pytest.raises(IntegrityError):
        await _claim(session, venue, event.id, hook.id, status="STORED")


async def test_returned_claims_free_the_hook(session, venue):
    event, hook = await _event_and_hook(session, venue)
    await _claim(session, venue, event.id, hook.id, status="RETURNED")
    await _claim(session, venue, event.id, hook.id, status="RETURNED")
    await _claim(session, venue, event.id, hook.id, status="STORED")


async def test_stored_claim_needs_a_hook(session, venue):
    event, _ = await _event_and_hook(session, venue)

    with pytest.raises(IntegrityError):
        await _claim(session, venue, event.id, hook_id=None, status="STORED")


async def test_one_open_event_per_venue(session, venue):
    session.add(Event(venue_id=venue.id, name="Second night"))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_hook_numbers_are_unique_per_rack(session, venue):
    session.add(Hook(venue_id=venue.id, rack="A", number=1))

    with pytest.raises(IntegrityError):
        await session.flush()
