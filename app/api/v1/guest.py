"""Guest app endpoints. No auth: holding the claim token is the authorization."""

from fastapi import APIRouter, Depends, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.limiter import limiter
from app.schemas.common import MessageResponse
from app.schemas.guest import GuestClaimCreate, GuestClaimResponse, GuestPhoneUpdate
from app.services import claim as claim_service

router = APIRouter(prefix="/guest", tags=["Guest"])

ClaimTokenPath = Path(pattern=r"^c_[A-Za-z0-9_-]{22}$")


@router.post("/claims", response_model=GuestClaimResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_claim(request: Request, data: GuestClaimCreate, db: AsyncSession = Depends(get_db)):
    """Opened from the counter QR. Errors: CounterNotFoundError, EventNotOpenError."""
    return await claim_service.create_guest_claim(db, data.counter_token)


@router.get("/claims/{claim_token}", response_model=GuestClaimResponse)
async def get_claim(claim_token: str = ClaimTokenPath, db: AsyncSession = Depends(get_db)):
    """The guest's claim screen; polled for status changes. Errors: ClaimNotFoundError."""
    return await claim_service.get_guest_claim(db, claim_token)


@router.put("/claims/{claim_token}/phone", response_model=MessageResponse)
async def set_phone(data: GuestPhoneUpdate, claim_token: str = ClaimTokenPath, db: AsyncSession = Depends(get_db)):
    """Opt in to one lost-item SMS. Errors: ClaimNotFoundError, ClaimWrongStateError."""
    await claim_service.set_guest_phone(db, claim_token, data.phone)
    return {"message": "Phone saved"}
