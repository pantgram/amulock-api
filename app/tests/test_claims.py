"""Drop-off and pickup in the Venue app, and the guest's side of a claim."""

import pytest

from app.tests.conftest import API, auth_headers_for, create_venue

PHONE = {"contactType": "phone", "contact": "+30 691 234 5678"}


async def _staff_claim(client, headers, **extra) -> dict:
    response = await client.post(f"{API}/venue/claims", headers=headers, json={**PHONE, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def _positions(client, headers) -> list[dict]:
    return (await client.get(f"{API}/venue/positions", headers=headers)).json()


async def _current_event_id(client, headers) -> str:
    return (await client.get(f"{API}/venue/events/current", headers=headers)).json()["id"]


class TestStaffClaims:
    async def test_create_is_pending_with_masked_contact(self, client, venue_headers):
        claim = await _staff_claim(client, venue_headers, note="Red coat")

        assert claim["status"] == "pending" and claim["source"] == "staff"
        assert claim["position"] is None and claim["note"] == "Red coat"
        assert claim["contactHint"] == "+30••••••5678"
        assert "guestToken" not in claim and "contact" not in claim

    async def test_store_picks_the_next_free_position(self, client, venue_headers):
        first = await _staff_claim(client, venue_headers, store=True)
        second = await _staff_claim(client, venue_headers)

        stored = await client.post(f"{API}/venue/claims/{second['id']}/store", headers=venue_headers, json={})

        assert first["status"] == "stored" and first["position"]["label"] == "A-1" and first["storedAt"]
        assert stored.status_code == 200 and stored.json()["position"]["label"] == "A-2"

    async def test_store_at_a_chosen_position(self, client, venue_headers):
        target = (await _positions(client, venue_headers))[2]

        claim = await _staff_claim(client, venue_headers, positionId=target["id"])

        assert claim["status"] == "stored" and claim["position"]["label"] == "A-3"

    async def test_occupied_position(self, client, venue_headers):
        target = (await _positions(client, venue_headers))[0]
        await _staff_claim(client, venue_headers, positionId=target["id"])
        claim = await _staff_claim(client, venue_headers)

        response = await client.post(
            f"{API}/venue/claims/{claim['id']}/store", headers=venue_headers, json={"positionId": target["id"]}
        )

        assert response.status_code == 409 and response.json()["error"] == "PositionOccupiedError"

    async def test_inactive_and_foreign_positions_are_not_found(self, client, session, venue_headers):
        mine = (await _positions(client, venue_headers))[0]
        await client.patch(f"{API}/venue/positions/{mine['id']}", headers=venue_headers, json={"isActive": False})
        other = await create_venue(session, name="Other Club")
        theirs = (await _positions(client, auth_headers_for(other)))[1]
        claim = await _staff_claim(client, venue_headers)

        for position_id in (mine["id"], theirs["id"]):
            response = await client.post(
                f"{API}/venue/claims/{claim['id']}/store", headers=venue_headers, json={"positionId": position_id}
            )
            assert response.status_code == 404 and response.json()["error"] == "PositionNotFoundError"

    async def test_no_free_position(self, client, venue_headers):
        for _ in range(3):
            await _staff_claim(client, venue_headers, store=True)
        claim = await _staff_claim(client, venue_headers)

        response = await client.post(f"{API}/venue/claims/{claim['id']}/store", headers=venue_headers, json={})

        assert response.status_code == 409 and response.json()["error"] == "NoFreePositionError"

    async def test_collect_frees_the_position(self, client, venue_headers):
        claim = await _staff_claim(client, venue_headers, store=True)

        collected = await client.post(f"{API}/venue/claims/{claim['id']}/collect", headers=venue_headers)
        again = await _staff_claim(client, venue_headers, store=True)

        assert collected.status_code == 200
        assert collected.json()["status"] == "collected" and collected.json()["collectedAt"]
        assert again["position"]["label"] == "A-1"

    @pytest.mark.parametrize("action", ["collect", "store"])
    async def test_wrong_state(self, client, venue_headers, action):
        claim = await _staff_claim(client, venue_headers)
        await client.post(f"{API}/venue/claims/{claim['id']}/cancel", headers=venue_headers)

        response = await client.post(f"{API}/venue/claims/{claim['id']}/{action}", headers=venue_headers, json={})

        assert response.status_code == 409 and response.json()["error"] == "ClaimWrongStateError"

    async def test_requires_an_open_event(self, client, session):
        venue = await create_venue(session, event_status=None)

        response = await client.post(f"{API}/venue/claims", headers=auth_headers_for(venue), json=PHONE)

        assert response.status_code == 409 and response.json()["error"] == "EventNotOpenError"

    async def test_invalid_contact(self, client, venue_headers):
        response = await client.post(
            f"{API}/venue/claims", headers=venue_headers, json={"contactType": "email", "contact": "not-an-email"}
        )

        assert response.status_code == 422 and response.json()["details"][0]["path"] == "contact"

    async def test_closing_the_event(self, client, venue_headers):
        stored = await _staff_claim(client, venue_headers, store=True)
        pending = await _staff_claim(client, venue_headers)
        event_id = await _current_event_id(client, venue_headers)

        await client.post(f"{API}/venue/events/{event_id}/close", headers=venue_headers)

        claims = (await client.get(f"{API}/venue/events/{event_id}/claims", headers=venue_headers)).json()
        assert {c["id"]: c["status"] for c in claims} == {stored["id"]: "unclaimed", pending["id"]: "cancelled"}
        late = await client.post(f"{API}/venue/claims/{stored['id']}/collect", headers=venue_headers)
        assert late.status_code == 200 and late.json()["status"] == "collected"

    async def test_list_filters_by_status(self, client, venue_headers):
        stored = await _staff_claim(client, venue_headers, store=True)
        await _staff_claim(client, venue_headers)
        event_id = await _current_event_id(client, venue_headers)

        claims = (await client.get(f"{API}/venue/events/{event_id}/claims?status=stored", headers=venue_headers)).json()

        assert [c["id"] for c in claims] == [stored["id"]]

    async def test_search_by_contact(self, client, session, venue_headers):
        mine = await _staff_claim(client, venue_headers)
        await _staff_claim(client, venue_headers, contactType="email", contact="someone@example.com")
        other = await create_venue(session, name="Other Club")
        await _staff_claim(client, auth_headers_for(other))

        response = await client.post(
            f"{API}/venue/claims/search",
            headers=venue_headers,
            json={"contactType": "phone", "contact": "+306912345678"},
        )

        assert response.status_code == 200
        assert [c["id"] for c in response.json()] == [mine["id"]]

    async def test_another_venues_claim_is_hidden(self, client, session, venue_headers):
        other = await create_venue(session, name="Other Club")
        theirs = await _staff_claim(client, auth_headers_for(other))

        for method, suffix in (("get", ""), ("post", "/cancel")):
            response = await getattr(client, method)(
                f"{API}/venue/claims/{theirs['id']}{suffix}", headers=venue_headers
            )
            assert response.status_code == 404 and response.json()["error"] == "ClaimNotFoundError"


class TestGuestClaims:
    async def _guest_claim(self, client, venue, **extra) -> dict:
        response = await client.post(
            f"{API}/guest/claims", json={"counterToken": venue.counter_token, **PHONE, **extra}
        )
        assert response.status_code == 201, response.text
        return response.json()

    async def test_counter(self, client, venue):
        response = await client.get(f"{API}/guest/counters/{venue.counter_token}")

        assert response.status_code == 200
        assert response.json()["venueName"] == "Demo Club" and response.json()["event"]["name"] == "Tonight"

    async def test_counter_when_closed(self, client, session):
        venue = await create_venue(session, event_status="draft")

        response = await client.get(f"{API}/guest/counters/{venue.counter_token}")

        assert response.status_code == 200 and response.json()["event"] is None

    async def test_unknown_counter(self, client):
        response = await client.post(f"{API}/guest/claims", json={"counterToken": "v_" + "a" * 22, **PHONE})

        assert response.status_code == 404 and response.json()["error"] == "CounterNotFoundError"

    async def test_drop_off_and_pickup(self, client, venue, venue_headers):
        claim = await self._guest_claim(client, venue)
        assert claim["status"] == "pending" and claim["guestToken"].startswith("c_")
        assert set(claim) == {"guestToken", "status", "venueName", "event", "createdAt"}

        scanned = await client.get(f"{API}/venue/claims/by-token/{claim['guestToken']}", headers=venue_headers)
        assert scanned.status_code == 200 and scanned.json()["source"] == "guest"
        claim_id = scanned.json()["id"]
        await client.post(f"{API}/venue/claims/{claim_id}/store", headers=venue_headers, json={})
        assert (await client.get(f"{API}/guest/claims/{claim['guestToken']}")).json()["status"] == "stored"

        await client.post(f"{API}/venue/claims/{claim_id}/collect", headers=venue_headers)
        assert (await client.get(f"{API}/guest/claims/{claim['guestToken']}")).json()["status"] == "collected"

    async def test_guest_cancels_before_drop_off(self, client, venue):
        claim = await self._guest_claim(client, venue)

        response = await client.post(f"{API}/guest/claims/{claim['guestToken']}/cancel")
        again = await client.post(f"{API}/guest/claims/{claim['guestToken']}/cancel")

        assert response.status_code == 200 and response.json()["status"] == "cancelled"
        assert again.status_code == 409 and again.json()["error"] == "ClaimWrongStateError"

    async def test_unknown_claim(self, client):
        response = await client.get(f"{API}/guest/claims/c_{'b' * 22}")

        assert response.status_code == 404 and response.json()["error"] == "ClaimNotFoundError"

    async def test_another_venue_cannot_scan_it(self, client, session, venue):
        claim = await self._guest_claim(client, venue)
        other = await create_venue(session, name="Other Club")

        response = await client.get(
            f"{API}/venue/claims/by-token/{claim['guestToken']}", headers=auth_headers_for(other)
        )

        assert response.status_code == 404


class TestGuestRateLimit:
    async def test_limit_comes_from_settings(self, client, venue, monkeypatch):
        from app.config.limiter import limiter
        from app.config.settings import settings

        monkeypatch.setattr(limiter, "enabled", True)
        monkeypatch.setattr(settings, "guest_claim_rate_limit", "2/minute")
        limiter.reset()
        body = {"counterToken": venue.counter_token, **PHONE}

        codes = [(await client.post(f"{API}/guest/claims", json=body)).status_code for _ in range(3)]
        limited = await client.post(f"{API}/guest/claims", json=body)
        limiter.reset()

        assert codes == [201, 201, 429]
        assert limited.json()["error"] == "RateLimitedError"
