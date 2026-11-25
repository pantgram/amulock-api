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
