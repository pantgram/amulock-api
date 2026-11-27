# Amulock API

REST API for Amulock, the digital cloakroom: the backend for the Guest app (claims opened from the counter QR) and the Venue app (events, positions, drop-off and pickup).

Built with **FastAPI**, **SQLAlchemy 2.0 (async)** and **PostgreSQL**, with **Clerk** for Venue app sign-in. Packaged with [uv](https://docs.astral.sh/uv/), Dockerized, and covered by an async pytest suite.

## Features

- **Events** — draft → open → closed; at most one open event per venue, with an optional offer shown to guests
- **Positions** — the venue's numbered spots (`B-12`, or just `12`), created in ranges, activated or deactivated
- **Claims** — guests open one from the counter QR (or staff create it), staff store it at the next free position and hand it back at pickup; closing an event marks leftovers as unclaimed
- **Guest contacts** — phone or email, encrypted at rest, searchable by keyed hash, only ever shown masked
- **Venues** — one Clerk account per venue; every query is scoped to it
- **Cross-cutting** — camelCase JSON, consistent `{"error", "message"}` errors, CORS, rate-limited guest writes

Out of scope for now: staff users and roles, an Admin app, plans and billing, notifications.

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) + Alembic migrations |
| Database | PostgreSQL (asyncpg) |
| Validation | Pydantic v2 + pydantic-settings |
| Auth | Clerk (`clerk-backend-api` SDK) |
| Tooling | uv, ruff, pytest + pytest-asyncio |

## Getting Started

### Prerequisites

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL (or `docker compose up -d db`)
- A Clerk application

### Installation

```bash
git clone <repository-url>
cd amulock-api
uv sync
cp .env.example .env      # set DATABASE_URL, CLERK_SECRET_KEY and CONTACT_SECRET_KEY
```

### Running

```bash
docker compose up -d db                                   # Postgres on localhost:5432
uv run alembic upgrade head
uv run python -m scripts.seed --clerk-user-id user_xxx    # demo venue linked to your Clerk account
uv run uvicorn app.main:app --reload --port 5000
```

The API is served at `http://localhost:5000/api/v1`, with interactive docs at `/docs`.
Create the venue's Clerk account under **Users** in the Clerk dashboard and pass its user ID.

Or run everything in containers: `docker compose up --build`.

### Testing

```bash
docker compose up -d db-test   # throwaway Postgres on localhost:5433
uv run pytest
```

Tests run on Postgres with fake Clerk tokens, so no Clerk keys are needed. To use another database, set
`TEST_DATABASE_URL` (its name must end in `_test`; it is wiped):

```bash
TEST_DATABASE_URL=postgresql+asyncpg://amulock:amulock@localhost:5432/amulock_test uv run pytest
```

## API

| Method | Path | Auth |
|---|---|---|
| GET | `/api/v1/health` | — |
| GET | `/api/v1/guest/counters/{counterToken}` | — |
| POST | `/api/v1/guest/claims` | — |
| GET | `/api/v1/guest/claims/{guestToken}` | — |
| POST | `/api/v1/guest/claims/{guestToken}/cancel` | — |
| GET, PATCH | `/api/v1/venue/me` | Clerk |
| GET, POST | `/api/v1/venue/events` | Clerk |
| GET | `/api/v1/venue/events/current` | Clerk |
| GET, PATCH | `/api/v1/venue/events/{eventId}` | Clerk |
| POST | `/api/v1/venue/events/{eventId}/open`, `/close` | Clerk |
| GET | `/api/v1/venue/events/{eventId}/claims?status=` | Clerk |
| GET, POST | `/api/v1/venue/positions` | Clerk |
| PATCH | `/api/v1/venue/positions/{positionId}` | Clerk |
| POST | `/api/v1/venue/claims` | Clerk |
| POST | `/api/v1/venue/claims/search` | Clerk |
| GET | `/api/v1/venue/claims/by-token/{guestToken}` | Clerk |
| GET | `/api/v1/venue/claims/{claimId}` | Clerk |
| POST | `/api/v1/venue/claims/{claimId}/store`, `/collect`, `/cancel` | Clerk |

The live OpenAPI spec is served at `/openapi.json` (docs at `/docs`).

Errors are `{"error": "<Name>", "message": "..."}`. Clients switch on `error`, e.g. `EventNotOpenError`, `PositionOccupiedError`, `ClaimWrongStateError`, `NotVenueAccountError`.

## Project Structure

```
app/
  api/v1/          routers: health, guest, venue
  config/          settings, database (auto-commit sessions), logging, rate limiter
  dependencies/    Clerk auth -> current venue
  models/          venues, positions, events, claims (+ enums)
  schemas/         CamelModel request/response models
  services/        business logic (venue: events + positions; claim)
  utils/           errors, tokens, contact encryption/hashing
  tests/           pytest suite (Postgres)
alembic/           migrations
scripts/           seed
```

See [`AGENTS.md`](AGENTS.md) for conventions.
