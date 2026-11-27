from app.tests.conftest import API


class TestCamelCaseResponses:
    async def test_venue_keys_are_camel_case(self, client, venue_headers):
        body = (await client.get(f"{API}/venue/me", headers=venue_headers)).json()

        assert set(body) == {"id", "name", "counterToken"}

    async def test_contract_uses_camel_case(self, client):
        spec = (await client.get("/openapi.json")).json()
        event = spec["components"]["schemas"]["EventResponse"]["properties"]

        assert "openedAt" in event
        assert "opened_at" not in event

    async def test_every_api_route_declares_a_response_model(self, client):
        spec = (await client.get("/openapi.json")).json()
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                ok = next((r for code, r in operation["responses"].items() if code.startswith("2")), None)
                assert ok is not None and ok.get("content"), f"{method.upper()} {path} has no response model"


class TestContract:
    async def test_endpoints(self, client):
        paths = set((await client.get("/openapi.json")).json()["paths"])

        assert paths == {
            "/api/v1/health",
            "/api/v1/guest/counters/{counter_token}",
            "/api/v1/guest/claims",
            "/api/v1/guest/claims/{guest_token}",
            "/api/v1/guest/claims/{guest_token}/cancel",
            "/api/v1/venue/me",
            "/api/v1/venue/events",
            "/api/v1/venue/events/current",
            "/api/v1/venue/events/{event_id}",
            "/api/v1/venue/events/{event_id}/open",
            "/api/v1/venue/events/{event_id}/close",
            "/api/v1/venue/events/{event_id}/claims",
            "/api/v1/venue/positions",
            "/api/v1/venue/positions/{position_id}",
            "/api/v1/venue/claims",
            "/api/v1/venue/claims/search",
            "/api/v1/venue/claims/by-token/{guest_token}",
            "/api/v1/venue/claims/{claim_id}",
            "/api/v1/venue/claims/{claim_id}/store",
            "/api/v1/venue/claims/{claim_id}/collect",
            "/api/v1/venue/claims/{claim_id}/cancel",
            "/api/v1/webhooks/clerk",
        }


class TestErrorFormats:
    async def test_validation_error_format(self, client, venue_headers):
        response = await client.post(
            f"{API}/venue/events", headers=venue_headers, json={"name": "", "startsAt": "2026-11-27T22:00:00Z"}
        )

        assert response.status_code == 422
        body = response.json()
        assert body["error"] == "ValidationError"
        assert body["message"] == "Invalid request data"
        assert body["details"][0]["path"] == "name"

    async def test_domain_error_format(self, client, session):
        from app.tests.conftest import auth_headers_for, create_venue

        venue = await create_venue(session, event_status=None)
        response = await client.get(f"{API}/venue/events/current", headers=auth_headers_for(venue))

        assert response.status_code == 409
        assert response.json() == {"error": "EventNotOpenError", "message": "The cloakroom isn't open"}

    async def test_unknown_route_returns_404(self, client):
        response = await client.get(f"{API}/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {"error": "NotFoundError", "message": "Not Found"}

    async def test_unhandled_error_is_masked(self, session_factory):
        from fastapi import APIRouter
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        router = APIRouter()

        @router.get("/__boom")
        async def boom():
            raise RuntimeError("secret detail")

        app.include_router(router)
        try:
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                response = await raw.get("/__boom")
        finally:
            app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/__boom"]

        assert response.status_code == 500
        assert response.json() == {"error": "InternalServerError", "message": "An unexpected error occurred"}
