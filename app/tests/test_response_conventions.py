from app.tests.conftest import API
from app.utils.tokens import TokenKind, new_token


class TestCamelCaseResponses:
    async def test_venue_keys_are_camel_case(self, client, venue_headers):
        body = (await client.get(f"{API}/venue/me", headers=venue_headers)).json()

        assert set(body) == {"id", "name", "slug", "locale", "timezone"}

    async def test_contract_uses_camel_case(self, client):
        spec = (await client.get("/openapi.json")).json()
        claim = spec["components"]["schemas"]["GuestClaimResponse"]["properties"]

        assert "claimToken" in claim
        assert "shortCode" in claim
        assert "claim_token" not in claim

    async def test_every_api_route_declares_a_response_model(self, client):
        spec = (await client.get("/openapi.json")).json()
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                ok = next((r for code, r in operation["responses"].items() if code.startswith("2")), None)
                assert ok is not None and ok.get("content"), f"{method.upper()} {path} has no response model"


class TestContract:
    async def test_thin_slice_endpoints_exist(self, client):
        paths = (await client.get("/openapi.json")).json()["paths"]
        for path in (
            "/api/v1/guest/claims",
            "/api/v1/guest/claims/{claim_token}",
            "/api/v1/venue/hooks",
            "/api/v1/venue/drop-offs",
            "/api/v1/venue/claims/lookup",
            "/api/v1/venue/pickups",
        ):
            assert path in paths
        assert not any(p.startswith(("/api/v1/staff", "/api/v1/admin")) for p in paths)


class TestErrorFormats:
    async def test_validation_error_format(self, client):
        response = await client.post(f"{API}/guest/claims", json={"counterToken": "nope"})

        assert response.status_code == 422
        body = response.json()
        assert body["error"] == "Validation Error"
        assert body["message"] == "Invalid request data"
        assert body["details"][0]["path"] == "counterToken"

    async def test_unbuilt_endpoint_returns_501(self, client):
        response = await client.post(f"{API}/guest/claims", json={"counterToken": new_token(TokenKind.COUNTER)})

        assert response.status_code == 501
        assert response.json() == {"error": "NotImplementedYetError", "message": "Not implemented yet"}

    async def test_unknown_route_returns_404(self, client):
        response = await client.get(f"{API}/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {"error": "NotFoundError", "message": "Not Found"}
