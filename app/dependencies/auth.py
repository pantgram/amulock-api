import jwt
from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from clerk_backend_api.security.types import TokenVerificationErrorReason
from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.logging_config import logger
from app.config.settings import settings
from app.models.venue import Venue
from app.utils.errors import NotVenueAccountError, UnauthorizedError

bearer_scheme = HTTPBearer(auto_error=False, description="Clerk session token")


def authenticate_clerk_request(request: Request) -> dict:
    """Verify the Clerk session token on the request and return its claims.

    Thin wrapper around the clerk-backend-api SDK, which reads the
    ``Authorization: Bearer`` header itself. ``jwt_key`` (PEM from the dashboard)
    enables networkless verification; omitted, the SDK falls back to JWKS.
    ``authorized_parties`` is the ``azp`` allowlist.
    """
    state = authenticate_request(
        request,
        AuthenticateRequestOptions(
            secret_key=settings.clerk_secret_key,
            jwt_key=settings.clerk_jwt_key or None,
            authorized_parties=settings.clerk_authorized_parties_list or None,
            accepts_token=["session_token"],
        ),
    )
    if not state.is_signed_in:
        reason = state.reason.name if state.reason is not None else state.status.name
        logger.warning("Clerk token verification failed: %s", reason)
        raise UnauthorizedError("Unauthorized")
    return state.payload



async def get_current_venue(
    request: Request,
    _: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Venue:
    """The venue whose Clerk account signed this request. Every Venue app query is scoped to it.

    One Clerk account per venue for now (venues.clerk_id); staff accounts come later.
    """
    payload = authenticate_clerk_request(request)
    clerk_id = payload.get("sub")
    if not clerk_id:
        raise UnauthorizedError("Unauthorized")

    result = await db.execute(select(Venue).where(Venue.clerk_id == clerk_id))
    venue = result.scalar_one_or_none()
    if venue is None:
        # Valid Clerk token, but this account isn't linked to a venue.
        raise NotVenueAccountError()
    return venue
