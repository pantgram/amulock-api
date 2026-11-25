"""The Venue app: events and positions. Everything is scoped to the signed-in venue."""

from app.tests.conftest import API, auth_headers_for, create_venue

TONIGHT = {"name": "Friday", "startsAt": "2026-11-27T22:00:00+02:00", "offerText": "2-for-1 until midnight"}


async def _current(client, headers) -> dict:
    return (await client.get(f"{API}/venue/events/current", headers=headers)).json()


class TestEvents:
    async def test_current_event(self, client, venue_headers):
        response = await client.get(f"{API}/venue/events/current", headers=venue_headers)

        assert response.status_code == 200
        event = response.json()
        assert event["name"] == "Tonight" and event["status"] == "open" and event["closedAt"] is None
        assert event["openedAt"]

    async def test_create_is_a_draft(self, client, venue_headers):
        response = await client.post(f"{API}/venue/events", headers=venue_headers, json=TONIGHT)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "draft" and body["openedAt"] is None
        assert body["offerText"] == "2-for-1 until midnight"
        assert body["startsAt"].startswith("2026-11-27T20:00:00")

    async def test_starts_at_needs_a_timezone(self, client, venue_headers):
        response = await client.post(
            f"{API}/venue/events", headers=venue_headers, json={**TONIGHT, "startsAt": "2026-11-27T22:00:00"}
        )

        assert response.status_code == 422

    async def test_close_then_open_the_next(self, client, venue_headers):
        current = await _current(client, venue_headers)
        draft = (await client.post(f"{API}/venue/events", headers=venue_headers, json=TONIGHT)).json()

        blocked = await client.post(f"{API}/venue/events/{draft['id']}/open", headers=venue_headers)
        assert blocked.status_code == 409 and blocked.json()["error"] == "EventAlreadyOpenError"

        closed = await client.post(f"{API}/venue/events/{current['id']}/close", headers=venue_headers)
        assert closed.status_code == 200
        assert closed.json()["status"] == "closed" and closed.json()["closedAt"]

        opened = await client.post(f"{API}/venue/events/{draft['id']}/open", headers=venue_headers)
        assert opened.status_code == 200
        assert opened.json()["status"] == "open" and opened.json()["openedAt"]

    async def test_close_twice(self, client, venue_headers):
        event_id = (await _current(client, venue_headers))["id"]
        await client.post(f"{API}/venue/events/{event_id}/close", headers=venue_headers)

        response = await client.post(f"{API}/venue/events/{event_id}/close", headers=venue_headers)

        assert response.status_code == 409
        assert response.json()["error"] == "EventNotOpenError"

    async def test_closed_event_cannot_reopen(self, client, venue_headers):
        event_id = (await _current(client, venue_headers))["id"]
        await client.post(f"{API}/venue/events/{event_id}/close", headers=venue_headers)

        response = await client.post(f"{API}/venue/events/{event_id}/open", headers=venue_headers)

        assert response.status_code == 409
        assert response.json()["error"] == "EventWrongStateError"

    async def test_update(self, client, venue_headers):
        event_id = (await _current(client, venue_headers))["id"]

        response = await client.patch(
            f"{API}/venue/events/{event_id}", headers=venue_headers, json={"offerText": "Free shots"}
        )

        assert response.status_code == 200
        assert response.json()["offerText"] == "Free shots" and response.json()["name"] == "Tonight"
        cleared = await client.patch(f"{API}/venue/events/{event_id}", headers=venue_headers, json={"offerText": None})
        assert cleared.json()["offerText"] is None

    async def test_list_newest_first(self, client, venue_headers):
        await client.post(
            f"{API}/venue/events", headers=venue_headers, json={**TONIGHT, "startsAt": "2099-01-01T00:00Z"}
        )

        events = (await client.get(f"{API}/venue/events", headers=venue_headers)).json()

        assert [e["name"] for e in events] == ["Friday", "Tonight"]

    async def test_another_venues_event_is_hidden(self, client, session, venue_headers):
        other = await create_venue(session, name="Other Club")
        theirs = await _current(client, auth_headers_for(other))

        for method, suffix in (("get", ""), ("post", "/close")):
            response = await getattr(client, method)(
                f"{API}/venue/events/{theirs['id']}{suffix}", headers=venue_headers
            )
            assert response.status_code == 404 and response.json()["error"] == "EventNotFoundError"
        assert (await _current(client, auth_headers_for(other)))["status"] == "open"

    async def test_requires_venue_login(self, client):
        response = await client.post(f"{API}/venue/events", json=TONIGHT)

        assert response.status_code == 401


class TestPositions:
    async def test_ordered_by_zone_then_number(self, client, session):
        venue = await create_venue(session, zones=("B", "A"), positions_per_zone=2)

        positions = (await client.get(f"{API}/venue/positions", headers=auth_headers_for(venue))).json()

        assert [p["label"] for p in positions] == ["A-1", "A-2", "B-1", "B-2"]
        assert set(positions[0]) == {"id", "zone", "number", "label", "isActive"}

    async def test_only_the_venues_own_positions(self, client, session, venue_headers):
        await create_venue(session, name="Other Club", positions_per_zone=5)

        positions = (await client.get(f"{API}/venue/positions", headers=venue_headers)).json()

        assert len(positions) == 3

    async def test_create_a_range_without_zone(self, client, venue_headers):
        response = await client.post(
            f"{API}/venue/positions", headers=venue_headers, json={"fromNumber": 1, "toNumber": 3}
        )

        assert response.status_code == 201
        assert [p["label"] for p in response.json()] == ["1", "2", "3"]

    async def test_create_overlapping_range(self, client, venue_headers):
        response = await client.post(
            f"{API}/venue/positions", headers=venue_headers, json={"zone": "A", "fromNumber": 3, "toNumber": 5}
        )

        assert response.status_code == 409
        assert response.json() == {"error": "PositionAlreadyExistsError", "message": "Position A-3 already exists"}

    async def test_deactivate(self, client, venue_headers):
        position = (await client.get(f"{API}/venue/positions", headers=venue_headers)).json()[0]

        response = await client.patch(
            f"{API}/venue/positions/{position['id']}", headers=venue_headers, json={"isActive": False}
        )

        assert response.status_code == 200 and response.json()["isActive"] is False
