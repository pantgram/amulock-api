"""Venue app endpoints. Require the venue's Clerk account; everything is scoped to that venue."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.dependencies.auth import get_current_venue
from app.models.venue import Venue
from app.schemas.venue import (
    CurrentEventResponse,
    DropOffRequest,
    HookStateResponse,
    PickupRequest,
    VenueClaimResponse,
    VenueResponse,
)
from app.services import claim as claim_service
from app.services import venue as venue_service

router = APIRouter(prefix="/venue", tags=["Venue"])


def _actor(request: Request) -> str | None:
    return getattr(request.state, "clerk_user_id", None)


@router.get("/me", response_model=VenueResponse)
async def get_me(venue: Venue = Depends(get_current_venue)):
    return venue


@router.get("/events/current", response_model=CurrentEventResponse)
async def get_current_event(venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """Errors: EventNotOpenError."""
    return await venue_service.get_current_event(db, venue)


@router.get("/hooks", response_model=list[HookStateResponse])
async def list_hooks(venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """All hooks with whether each is free, for the hook picker. Ordered by rack, then number."""
    return await venue_service.list_hooks(db, venue)


@router.post("/drop-offs", response_model=VenueClaimResponse)
async def drop_off(
    data: DropOffRequest,
    request: Request,
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """The attendant scans the guest's claim QR. The API assigns the next free hook unless `hookId`
    is given; the response's `hook.label` (e.g. "B-12") says where to hang it. CREATED → STORED.

    Errors: ClaimNotFoundError, HookNotFoundError, HookOccupiedError, NoFreeHookError,
    ClaimWrongStateError, EventNotOpenError.
    """
    return await claim_service.drop_off(db, venue, data, _actor(request))


@router.get("/claims/lookup", response_model=VenueClaimResponse)
async def lookup_claim(
    claim_token: str | None = Query(None, alias="claimToken", description="From scanning the guest's claim QR"),
    short_code: str | None = Query(None, alias="shortCode", description="Typed by the attendant, e.g. 'k7f 2qx'"),
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """Pass exactly one of `claimToken` or `shortCode`. Shows the hook for pickup. Errors: ClaimNotFoundError."""
    return await claim_service.lookup_claim(db, venue, claim_token, short_code)


@router.post("/pickups", response_model=VenueClaimResponse)
async def pickup(
    data: PickupRequest,
    request: Request,
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """STORED or UNCLAIMED → RETURNED, freeing the hook. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    return await claim_service.pickup(db, venue, data, _actor(request))
