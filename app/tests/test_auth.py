import pytest

from app.tests.conftest import API, make_test_token


class TestVenueAuth:
    async def test_venue_me_with_valid_token(self, client, venue, venue_headers):
        response = await client.get(f"{API}/venue/me", headers=venue_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(venue.id)
        assert body["name"] == "Demo Club"

    async def test_missing_token_is_401(self, client):
        response = await client.get(f"{API}/venue/me")

        assert response.status_code == 401
        assert response.json() == {"error": "UnauthorizedError", "message": "Unauthorized"}

    async def test_expired_token_is_401(self, client, venue):
        token = make_test_token(venue.clerk_id, expires_in=-30)
        response = await client.get(f"{API}/venue/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    async def test_clerk_account_without_venue_is_403(self, client):
        token = make_test_token("user_stranger")
        response = await client.get(f"{API}/venue/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403
        assert response.json()["error"] == "NotVenueAccountError"

    async def test_venues_only_see_themselves(self, client, session, venue_headers):
        from app.tests.conftest import auth_headers_for, create_venue

        other = await create_venue(session, name="Other Club")
        mine = (await client.get(f"{API}/venue/me", headers=venue_headers)).json()
        theirs = (await client.get(f"{API}/venue/me", headers=auth_headers_for(other))).json()

        assert mine["name"] == "Demo Club"
        assert theirs["name"] == "Other Club"


class TestVenueProfile:
    async def test_rename(self, client, venue_headers):
        response = await client.patch(f"{API}/venue/me", headers=venue_headers, json={"name": "  Club Nox  "})

        assert response.status_code == 200
        assert response.json()["name"] == "Club Nox"
        assert (await client.get(f"{API}/venue/me", headers=venue_headers)).json()["name"] == "Club Nox"

    async def test_guests_see_the_new_name(self, client, venue, venue_headers):
        await client.patch(f"{API}/venue/me", headers=venue_headers, json={"name": "Club Nox"})

        counter = await client.get(f"{API}/guest/counters/{venue.counter_token}")
        assert counter.json()["venueName"] == "Club Nox"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 121])
    async def test_invalid_name(self, client, venue_headers, name):
        response = await client.patch(f"{API}/venue/me", headers=venue_headers, json={"name": name})

        assert response.status_code == 422
        assert response.json()["error"] == "ValidationError"

    async def test_requires_venue_login(self, client):
        response = await client.patch(f"{API}/venue/me", json={"name": "Club Nox"})

        assert response.status_code == 401
