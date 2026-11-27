"""Venue app endpoints. Require the venue's Clerk account; everything is scoped to that venue."""

import uuid

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.dependencies.auth import get_current_venue
from app.models.venue import Venue
from app.schemas.common import ClaimStatus
from app.schemas.venue import (
    ClaimCreateRequest,
    ClaimResponse,
    ClaimSearchRequest,
    ClaimStoreRequest,
    EventCreateRequest,
    EventResponse,
    EventUpdateRequest,
    PositionCreateRequest,
    PositionResponse,
    PositionUpdateRequest,
    VenueResponse,
    VenueUpdateRequest,
)
from app.services import claim as claim_service
from app.services import venue as venue_service
from app.utils.tokens import TOKEN_PATTERN

router = APIRouter(prefix="/venue", tags=["Venue"])


@router.get("/me", response_model=VenueResponse)
async def get_me(venue: Venue = Depends(get_current_venue)):
    return venue


@router.patch("/me", response_model=VenueResponse)
async def update_me(
    data: VenueUpdateRequest, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Set the venue's name (new accounts start as "New venue")."""
    return await venue_service.update_venue(db, venue, data)


# ---------- events ----------


@router.get("/events", response_model=list[EventResponse])
async def list_events(venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """Every event, newest first."""
    return await venue_service.list_events(db, venue)


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreateRequest, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Create a draft event. Open it with POST /events/{eventId}/open."""
    return await venue_service.create_event(db, venue, data)


@router.get("/events/current", response_model=EventResponse)
async def get_current_event(venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """The open event. Errors: EventNotOpenError."""
    return await venue_service.get_current_event(db, venue)


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: uuid.UUID, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """Errors: EventNotFoundError."""
    return await venue_service.get_event(db, venue, event_id)


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdateRequest,
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """Errors: EventNotFoundError, EventWrongStateError (closed)."""
    return await venue_service.update_event(db, venue, event_id, data)


@router.post("/events/{event_id}/open", response_model=EventResponse)
async def open_event(
    event_id: uuid.UUID, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Open the cloakroom. Errors: EventNotFoundError, EventWrongStateError, EventAlreadyOpenError."""
    return await venue_service.open_event(db, venue, event_id)


@router.post("/events/{event_id}/close", response_model=EventResponse)
async def close_event(
    event_id: uuid.UUID, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Close the cloakroom: stored claims become unclaimed, pending ones are cancelled.

    Errors: EventNotFoundError, EventNotOpenError.
    """
    return await venue_service.close_event(db, venue, event_id)


@router.get("/events/{event_id}/claims", response_model=list[ClaimResponse])
async def list_event_claims(
    event_id: uuid.UUID,
    claim_status: ClaimStatus | None = Query(None, alias="status"),
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """The event's claims, oldest first. Errors: EventNotFoundError."""
    return await claim_service.list_event_claims(db, venue, event_id, claim_status)


# ---------- positions ----------


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """All positions, ordered by zone, then number."""
    return await venue_service.list_positions(db, venue)


@router.post("/positions", response_model=list[PositionResponse], status_code=status.HTTP_201_CREATED)
async def create_positions(
    data: PositionCreateRequest, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Create a range of positions in one zone. Errors: PositionAlreadyExistsError."""
    return await venue_service.create_positions(db, venue, data)


@router.patch("/positions/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID,
    data: PositionUpdateRequest,
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """Activate or deactivate a position. Errors: PositionNotFoundError."""
    return await venue_service.update_position(db, venue, position_id, data)


# ---------- claims ----------


@router.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    data: ClaimCreateRequest, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Create a claim for a guest at the counter (source "staff"), optionally storing it right away.

    Errors: EventNotOpenError; with store: PositionNotFoundError, PositionOccupiedError, NoFreePositionError.
    """
    return await claim_service.create_staff_claim(db, venue, data)


@router.post("/claims/search", response_model=list[ClaimResponse])
async def search_claims(
    data: ClaimSearchRequest, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Find claims by the guest's phone or email (exact match), newest first. POST keeps contacts out of URLs."""
    return await claim_service.search_claims(db, venue, data)


@router.get("/claims/by-token/{guest_token}", response_model=ClaimResponse)
async def get_claim_by_token(
    guest_token: str = Path(pattern=TOKEN_PATTERN),
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """The claim behind a scanned guest QR. Errors: ClaimNotFoundError."""
    return await claim_service.get_claim_by_token(db, venue, guest_token)


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: uuid.UUID, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)):
    """Errors: ClaimNotFoundError."""
    return await claim_service.get_claim(db, venue, claim_id)


@router.post("/claims/{claim_id}/store", response_model=ClaimResponse)
async def store_claim(
    claim_id: uuid.UUID,
    data: ClaimStoreRequest,
    venue: Venue = Depends(get_current_venue),
    db: AsyncSession = Depends(get_db),
):
    """Drop-off: pending → stored, at the chosen position or the next free one.

    Errors: ClaimNotFoundError, ClaimWrongStateError, EventNotOpenError, PositionNotFoundError,
    PositionOccupiedError, NoFreePositionError.
    """
    return await claim_service.store_claim(db, venue, claim_id, data.position_id)


@router.post("/claims/{claim_id}/collect", response_model=ClaimResponse)
async def collect_claim(
    claim_id: uuid.UUID, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """Pickup: stored or unclaimed → collected. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    return await claim_service.collect_claim(db, venue, claim_id)


@router.post("/claims/{claim_id}/cancel", response_model=ClaimResponse)
async def cancel_claim(
    claim_id: uuid.UUID, venue: Venue = Depends(get_current_venue), db: AsyncSession = Depends(get_db)
):
    """pending → cancelled. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    return await claim_service.cancel_claim(db, venue, claim_id)
