import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config.database import get_db
from app.config.logging_config import logger
from app.config.settings import settings
from app.schemas.webhook import WebhookAckResponse
from app.services import venue as venue_service
from app.utils.errors import ValidationError

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Same limit as event names; venues.name itself is unbounded text.
_MAX_VENUE_NAME_LENGTH = 120
_DEFAULT_VENUE_NAME = "My venue"


def verify_webhook(payload: bytes, headers: dict) -> dict:
    """Verify the Svix signature of a Clerk webhook delivery and return the
    decoded event. Fail-closed: any missing/invalid ``svix-*`` header raises,
    and the endpoint answers 400 (Clerk only retries non-2xx).

    The signature must be checked before the payload is trusted, so this is a
    plain function (patchable in tests), not a FastAPI dependency.
    """
    if not settings.clerk_webhook_secret:
        logger.warning("CLERK_WEBHOOK_SECRET not configured; rejecting webhook delivery")
        raise WebhookVerificationError
    Webhook(settings.clerk_webhook_secret).verify(payload, headers)
    return json.loads(payload)


def _clean(value) -> str:
    return value.strip()[:_MAX_VENUE_NAME_LENGTH] if isinstance(value, str) else ""


def _metadata_venue_name(data: dict) -> str:
    """The venue name set on the Clerk user's public metadata (``venueName``), if any.
    Public metadata is only writable from the backend/dashboard, so an account can't rename itself."""
    metadata = data.get("public_metadata") or {}
    return _clean(metadata.get("venueName") or metadata.get("venue_name"))


def _initial_venue_name(data: dict) -> str:
    """metadata venueName → the account's full name → username → a placeholder."""
    full_name = " ".join(part for part in (_clean(data.get("first_name")), _clean(data.get("last_name"))) if part)
    return _metadata_venue_name(data) or _clean(full_name) or _clean(data.get("username")) or _DEFAULT_VENUE_NAME


@router.post("/clerk", response_model=WebhookAckResponse)
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Clerk user lifecycle events for venue accounts (one Clerk account per venue).

    ``user.created`` links the new account to a new, empty venue (counter token, no positions,
    no events). ``user.updated`` renames the venue when ``public_metadata.venueName`` is set.
    ``user.deleted`` removes the venue only if it never had an event; venues with claim
    history are kept (and logged) until contact retention exists. Handlers are idempotent
    (Clerk redelivers), every verified event is answered 200 and unknown types are ignored.
    """
    payload = await request.body()
    try:
        event = verify_webhook(payload, dict(request.headers))
    except (WebhookVerificationError, ValueError):
        logger.error("Webhook rejected: invalid or missing Svix signature")
        raise ValidationError("Invalid webhook signature")

    event_type = event.get("type")
    data = event.get("data") or {}
    clerk_id = data.get("id")

    if not event_type or not clerk_id:
        logger.warning("Webhook ignored: missing type or data.id")
        return WebhookAckResponse()

    if event_type == "user.created":
        venue = await venue_service.create_venue_for_account(db, clerk_id, _initial_venue_name(data))
        logger.info("Webhook user.created: clerk user %s linked to venue %s", clerk_id, venue.id)

    elif event_type == "user.updated":
        name = _metadata_venue_name(data)
        if not name:
            logger.info("Webhook user.updated for clerk user %s: no venueName in metadata; ignoring", clerk_id)
        elif (venue := await venue_service.rename_venue_for_account(db, clerk_id, name)) is None:
            logger.info("Webhook user.updated for clerk user %s without a venue; ignoring", clerk_id)
        else:
            logger.info("Webhook user.updated: venue %s name refreshed", venue.id)

    elif event_type == "user.deleted":
        venue = await venue_service.find_venue_by_clerk_id(db, clerk_id)
        if venue is None:
            logger.info("Webhook user.deleted for clerk user %s without a venue; ignoring", clerk_id)
        elif await venue_service.remove_venue_for_account(db, clerk_id):
            logger.info("Webhook user.deleted: removed venue %s of clerk user %s", venue.id, clerk_id)
        else:
            logger.warning(
                "Webhook user.deleted: venue %s of clerk user %s has events; kept (clean up manually)",
                venue.id,
                clerk_id,
            )

    else:
        logger.info("Webhook event %s ignored", event_type)

    return WebhookAckResponse()
