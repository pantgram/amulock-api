# ruff: noqa: E402
import os
import uuid
from datetime import datetime, timedelta, timezone

# Provide deterministic settings before any app module is imported.
# Environment variables take priority over the .env file in pydantic-settings.
_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "CLERK_SECRET_KEY": "sk_test_dummy_secret_key",
    "CLERK_JWT_KEY": "",
    "CLERK_AUTHORIZED_PARTIES": "",
    "CONTACT_SECRET_KEY": "test-contact-secret",
    "NODE_ENV": "test",
    "LOG_FILE": "/tmp/amulock_api_test.log",
}
for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (register all models on Base.metadata)
from app.config.database import Base, get_db
from app.main import app
from app.models import Event, Position, Venue
from app.utils.tokens import TokenKind, new_token

API = "/api/v1"

# Secret used to sign Clerk-shaped test tokens. The real Clerk verifier in
# app.dependencies.auth is replaced (see mock_clerk_auth): no network, SDK or keys needed.
TEST_AUTH_SECRET = "test-clerk-auth-secret-0123456789abcdef"


# --- Clerk Auth test doubles ---


def make_test_token(sub: str, expires_in: int = 3600) -> str:
    """Sign a Clerk-shaped session token (sub="user_<hex>", azp, iat/exp) with HS256."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": sub,
        "azp": "http://localhost:5174",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return pyjwt.encode(claims, TEST_AUTH_SECRET, algorithm="HS256")


def _fake_authenticate_clerk_request(request) -> dict:
    from app.utils.errors import UnauthorizedError

    bearer = request.headers.get("Authorization")
    if not bearer or not bearer.startswith("Bearer "):
        raise UnauthorizedError("Unauthorized")
    try:
        return pyjwt.decode(bearer.removeprefix("Bearer "), TEST_AUTH_SECRET, algorithms=["HS256"])
    except pyjwt.PyJWTError:
        raise UnauthorizedError("Unauthorized")


@pytest.fixture(autouse=True)
def mock_clerk_auth(monkeypatch):
    monkeypatch.setattr("app.dependencies.auth.authenticate_clerk_request", _fake_authenticate_clerk_request)


@pytest.fixture(autouse=True)
def disable_rate_limits(monkeypatch):
    from app.config.limiter import limiter

    monkeypatch.setattr(limiter, "enabled", False)


# --- Helpers (plain functions, usable from any test module) ---


def auth_headers_for(venue: Venue) -> dict:
    return {"Authorization": f"Bearer {make_test_token(venue.clerk_id)}"}


async def create_venue(
    session,
    name: str = "Demo Club",
    zones: tuple[str, ...] = ("A",),
    positions_per_zone: int = 3,
    event_status: str | None = "open",
):
    """A venue linked to a fresh Clerk account, with positions and (by default) an open event."""
    venue = Venue(name=name, clerk_id=f"user_{uuid.uuid4().hex}", counter_token=new_token(TokenKind.COUNTER))
    session.add(venue)
    await session.flush()
    for zone in zones:
        for number in range(1, positions_per_zone + 1):
            session.add(Position(venue_id=venue.id, zone=zone, number=number))
    if event_status is not None:
        opened_at = datetime.now(timezone.utc) if event_status != "draft" else None
        session.add(
            Event(
                venue_id=venue.id,
                name="Tonight",
                starts_at=datetime.now(timezone.utc),
                status=event_status,
                opened_at=opened_at,
            )
        )
    await session.commit()
    await session.refresh(venue)
    return venue


# --- Fixtures ---


# Optional: run the suite against a real, empty Postgres database (e.g. in CI) instead of SQLite.
# Every table is dropped after each test, so never point this at a database you care about.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
async def db_engine():
    if TEST_DATABASE_URL:
        async for engine in _postgres_engine():
            yield engine
        return
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite(dbapi_connection, _):
        dbapi_connection.create_function("NOW", 0, lambda: datetime.now(timezone.utc).isoformat(sep=" "))
        dbapi_connection.create_function("gen_random_uuid", 0, lambda: uuid.uuid4().hex)
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def _postgres_engine():
    from app.models.enums import ALL_ENUMS

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        for enum in ALL_ENUMS:
            await conn.run_sync(lambda sync_conn, e=enum: e.create(sync_conn, checkfirst=True))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        for enum in ALL_ENUMS:
            await conn.run_sync(lambda sync_conn, e=enum: e.drop(sync_conn, checkfirst=True))
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as db:
        yield db


@pytest.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    class _NoReraiseASGI:
        """Starlette re-raises after sending a 500; swallow it so tests can assert on the masked response."""

        def __init__(self, asgi_app):
            self._asgi_app = asgi_app

        async def __call__(self, scope, receive, send):
            try:
                await self._asgi_app(scope, receive, send)
            except Exception:
                pass

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=_NoReraiseASGI(app))
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def venue(session):
    return await create_venue(session)


@pytest.fixture
def venue_headers(venue):
    return auth_headers_for(venue)
