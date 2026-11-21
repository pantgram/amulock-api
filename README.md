# Amulock API

REST API for Amulock, the digital cloakroom: guests get a QR claim on their phone instead of a paper ticket, and venue attendants scan it at drop-off and pickup.

Built with **FastAPI**, **SQLAlchemy 2.0 (async)** and **PostgreSQL**, with **Clerk** for Venue app sign-in. Packaged with [uv](https://docs.astral.sh/uv/), Dockerized, and covered by an async pytest suite.

## Features

- **Guest claims** — the counter QR opens the Guest app, which creates a claim with a QR token and a short code (`K7F-2QX`) for dead phones; optional phone opt-in for a lost-item SMS
- **Drop-off and pickup** — the attendant scans the guest's claim; the API assigns the next free hook (`B-12`) or uses the one they pick; pickup frees the hook
- **Claim history** — every change is logged with who did it; repeated scans are detected and not applied twice
- **Venues** — one Clerk account per venue; every query is scoped to it
- **Cross-cutting** — camelCase JSON, consistent `{"error", "message"}` errors, rate limiting on claim creation, CORS

Out of scope for now: staff users and roles, an Admin app, plans and billing.

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) + Alembic migrations |
| Database | PostgreSQL (asyncpg); SQLite (aiosqlite) in tests |
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
cp .env.example .env      # set DATABASE_URL and CLERK_SECRET_KEY
```

### Running

```bash
docker compose up -d db                                   # Postgres on localhost:5432
uv run alembic upgrade head
uv run python -m scripts.seed --clerk-user-id user_xxx    # demo venue linked to your Clerk account
uv run uvicorn app.main:app --reload --port 5000
```

The API is served at `http://localhost:5000/api/v1`, with interactive docs at `/docs`.
The seed prints the demo venue's counter QR URL. Create the venue's Clerk account under **Users** in the Clerk dashboard and pass its user ID.

Or run everything in containers: `docker compose up --build`.

### Testing

```bash
uv run pytest
```

Tests run on in-memory SQLite with fake Clerk tokens, so no database or Clerk keys are needed.

## API

| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/api/v1/health` | — | built |
| POST | `/api/v1/guest/claims` | — | contract only (501) |
| GET | `/api/v1/guest/claims/{claim_token}` | — | contract only (501) |
| PUT | `/api/v1/guest/claims/{claim_token}/phone` | — | contract only (501) |
| GET | `/api/v1/venue/me` | Clerk | built |
| GET | `/api/v1/venue/events/current` | Clerk | contract only (501) |
| GET | `/api/v1/venue/hooks` | Clerk | contract only (501) |
| POST | `/api/v1/venue/drop-offs` | Clerk | contract only (501) |
| GET | `/api/v1/venue/claims/lookup` | Clerk | contract only (501) |
| POST | `/api/v1/venue/pickups` | Clerk | contract only (501) |

`openapi.json` in this repo is the contract with the Guest and Venue apps. Regenerate it after changing any route or schema: `uv run python -m scripts.export_openapi`.

Errors are `{"error": "<Name>", "message": "..."}`. Clients switch on `error`, e.g. `ClaimNotFoundError`, `EventNotOpenError`, `HookOccupiedError`.

## Project Structure

```
app/
  api/v1/          routers: health, guest, venue
  config/          settings, database (auto-commit sessions), logging, rate limiter
  dependencies/    Clerk auth -> current venue
  models/          venues, events, hooks, claims, claim_events (+ enums)
  schemas/         CamelModel request/response models
  services/        business logic (claim, venue)
  utils/           errors, tokens
  tests/           pytest suite (SQLite)
alembic/           migrations
scripts/           seed, export_openapi
docs/decisions.md  claim lifecycle, tokens, errors, hook assignment, auth
```

See [`AGENTS.md`](AGENTS.md) for conventions and [`docs/decisions.md`](docs/decisions.md) for the design decisions.
