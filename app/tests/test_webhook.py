import base64
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from svix.webhooks import Webhook

from app.models import Position, Venue
from app.tests.conftest import API, auth_headers_for, create_venue

URL = f"{API}/webhooks/clerk"
SECRET = "whsec_" + base64.b64encode(b"test-clerk-webhook-secret-0123456").decode()


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "clerk_webhook_secret", SECRET)


def signed(event: dict, secret: str = SECRET) -> dict:
    """Request kwargs for a Clerk delivery signed the way Svix does it."""
    body = json.dumps(event)
    msg_id = f"msg_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    headers = {
        "svix-id": msg_id,
        "svix-timestamp": str(int(now.timestamp())),
        "svix-signature": Webhook(secret).sign(msg_id, now, body),
        "content-type": "application/json",
    }
    return {"content": body, "headers": headers}


def user_event(event_type: str, clerk_id: str, **data) -> dict:
    return {"type": event_type, "object": "event", "data": {"id": clerk_id, **data}}


async def venue_of(session, clerk_id: str) -> Venue | None:
    session.expire_all()
    return await session.scalar(select(Venue).where(Venue.clerk_id == clerk_id))


class TestSignature:
    async def test_unsigned_delivery_is_400(self, client):
        response = await client.post(URL, json=user_event("user.created", "user_x"))

        assert response.status_code == 400
        assert response.json() == {"error": "ValidationError", "message": "Invalid webhook signature"}

    async def test_wrong_secret_is_400(self, client, session):
        other = "whsec_" + base64.b64encode(b"some-other-secret-012345678901234").decode()
        response = await client.post(URL, **signed(user_event("user.created", "user_x"), secret=other))

        assert response.status_code == 400
        assert await venue_of(session, "user_x") is None

    async def test_missing_secret_rejects_everything(self, client, monkeypatch):
        from app.config.settings import settings

        monkeypatch.setattr(settings, "clerk_webhook_secret", "")
        response = await client.post(URL, **signed(user_event("user.created", "user_x")))

        assert response.status_code == 400


class TestUserCreated:
    async def test_creates_an_empty_venue_usable_by_the_account(self, client, session):
        event = user_event("user.created", "user_new", public_metadata={"venueName": "  Club Nox  "})
        response = await client.post(URL, **signed(event))

        assert response.status_code == 200
        assert response.json() == {"received": True}
        venue = await venue_of(session, "user_new")
        assert venue.name == "Club Nox"
        assert venue.counter_token.startswith("v_")
        assert await session.scalar(select(Position).where(Position.venue_id == venue.id)) is None

        me = await client.get(f"{API}/venue/me", headers=auth_headers_for(venue))
        assert me.status_code == 200

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"first_name": "Ada", "last_name": "Lovelace"}, "Ada Lovelace"),
            ({"first_name": None, "last_name": None, "username": "nox"}, "nox"),
            ({}, "My venue"),
        ],
    )
    async def test_name_fallbacks(self, client, session, data, expected):
        await client.post(URL, **signed(user_event("user.created", "user_fb", **data)))

        assert (await venue_of(session, "user_fb")).name == expected

    async def test_redelivery_keeps_the_existing_venue(self, client, session):
        venue = await create_venue(session)
        response = await client.post(
            URL, **signed(user_event("user.created", venue.clerk_id, public_metadata={"venueName": "Other"}))
        )

        assert response.status_code == 200
        again = await venue_of(session, venue.clerk_id)
        assert (again.id, again.name, again.counter_token) == (venue.id, "Demo Club", venue.counter_token)


class TestUserUpdated:
    async def test_renames_from_metadata(self, client, session):
        venue = await create_venue(session)
        event = user_event("user.updated", venue.clerk_id, public_metadata={"venueName": "Nox"})
        await client.post(URL, **signed(event))

        assert (await venue_of(session, venue.clerk_id)).name == "Nox"

    async def test_without_metadata_name_changes_nothing(self, client, session):
        venue = await create_venue(session)
        await client.post(URL, **signed(user_event("user.updated", venue.clerk_id, first_name="Ada")))

        assert (await venue_of(session, venue.clerk_id)).name == "Demo Club"

    async def test_unknown_account_is_ignored(self, client, session):
        event = user_event("user.updated", "user_ghost", public_metadata={"venueName": "Nox"})
        response = await client.post(URL, **signed(event))

        assert response.status_code == 200
        assert await venue_of(session, "user_ghost") is None


class TestUserDeleted:
    async def test_removes_a_venue_without_events(self, client, session):
        venue = await create_venue(session, event_status=None)
        venue_id, clerk_id = venue.id, venue.clerk_id
        response = await client.post(URL, **signed(user_event("user.deleted", clerk_id, deleted=True)))

        assert response.status_code == 200
        assert await venue_of(session, clerk_id) is None
        assert await session.scalar(select(Position).where(Position.venue_id == venue_id)) is None

    async def test_keeps_a_venue_with_events(self, client, session):
        venue = await create_venue(session, event_status="open")
        response = await client.post(URL, **signed(user_event("user.deleted", venue.clerk_id, deleted=True)))

        assert response.status_code == 200
        assert await venue_of(session, venue.clerk_id) is not None

    async def test_unknown_account_is_ignored(self, client):
        response = await client.post(URL, **signed(user_event("user.deleted", "user_ghost", deleted=True)))

        assert response.status_code == 200


class TestOtherEvents:
    async def test_unknown_type_is_acknowledged(self, client):
        response = await client.post(URL, **signed({"type": "session.created", "data": {"id": "sess_1"}}))

        assert response.status_code == 200
        assert response.json() == {"received": True}
