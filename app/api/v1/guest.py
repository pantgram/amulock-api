"""Guest app endpoints. No auth: the counter token opens a claim, and holding the guest token is the
authorization for that one claim."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.limiter import limiter
from app.schemas.guest import GuestClaimCreate, GuestClaimResponse, GuestCounterResponse
from app.services import claim as claim_service
from app.utils.tokens import TOKEN_PATTERN

router = APIRouter(prefix="/guest", tags=["Guest"])

TokenPath = Annotated[str, Path(pattern=TOKEN_PATTERN)]


@router.get("/counters/{counter_token}", response_model=GuestCounterResponse)
async def get_counter(counter_token: TokenPath, db: AsyncSession = Depends(get_db)):
    """What the counter QR opens: the venue and its open event, if any. Errors: CounterNotFoundError."""
    return await claim_service.get_counter(db, counter_token)


@router.post("/claims", response_model=GuestClaimResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_claim(request: Request, data: GuestClaimCreate, db: AsyncSession = Depends(get_db)):
    """A pending claim in the venue's open event; staff store it at drop-off.

    Errors: CounterNotFoundError, EventNotOpenError.
    """
    return await claim_service.create_guest_claim(db, data)


@router.get("/claims/{guest_token}", response_model=GuestClaimResponse)
async def get_claim(guest_token: TokenPath, db: AsyncSession = Depends(get_db)):
    """The guest's claim screen; poll it for status changes. Errors: ClaimNotFoundError."""
    return await claim_service.get_guest_claim(db, guest_token)


@router.post("/claims/{guest_token}/cancel", response_model=GuestClaimResponse)
async def cancel_claim(guest_token: TokenPath, db: AsyncSession = Depends(get_db)):
    """Cancel before drop-off. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    return await claim_service.cancel_guest_claim(db, guest_token)
