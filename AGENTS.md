# AGENTS.md — Amulock API

FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL REST API for Amulock, the digital cloakroom. Package manager is **uv** (always `uv run ...`, never plain `python`/`pytest`). Same layout and conventions as `homidirect-api` (`develop`).

`CLAUDE.md` is just a pointer to this file — update this file, not that one.

## Commands

```bash
uv sync                                              # install deps (dev group included)
uv run pytest                                        # full suite (<1s, SQLite, no external services)
uv run pytest app/tests/test_auth.py -k name         # focused test
uv run ruff check . && uv run ruff format .          # lint (line length 120; rules E,F,I,N,W) — baseline is clean
uv run uvicorn app.main:app --reload --port 5000     # dev server (docs at /docs)
uv run alembic upgrade head                          # apply migrations
uv run alembic revision --autogenerate -m "..."      # generate migration
uv run python -m scripts.seed --clerk-user-id user_x # demo venue with hooks and an open event
uv run python -m scripts.export_openapi              # refresh openapi.json (the frontend contract)
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest and `export_openapi --check`.

## Environment gotchas

- `app/config/settings.py` loads `.env` from the **current working directory**. Environment variables take priority over the file.
- Required settings with no default: `DATABASE_URL`, `CLERK_SECRET_KEY`. Alembic and the app import `settings` at module load, so anything touching `app.*` fails without them.
- `LOG_FILE` defaults to `/tmp/amulock_api.log`; `FileHandler` does not create parent dirs.
- `settings.async_database_url` strips libpq-only query params (`sslmode`, ...) from `DATABASE_URL` for asyncpg; use it, not `database_url`, for engines.

## Scope for now

In: Guest endpoints (no auth) and Venue endpoints (Clerk). Out until later: staff users/roles, an Admin app, plans/billing. Don't add them without a decision in `docs/decisions.md`.

## Architecture

- Layering: `app/api/v1/` (routers) → `app/services/` (business logic, one module per domain) → `app/models/` (SQLAlchemy) and `app/schemas/` (Pydantic).
- Adding a domain requires touching: new router in `app/api/v1/`, registration in `app/api/v1/__init__.py` (everything mounts under `/api/v1`), tag in `openapi_tags` in `app/main.py`, and model import in `app/models/__init__.py` (needed for Alembic autogenerate and test `create_all`).
- Sessions auto-commit: `get_db` in `app/config/database.py` commits at request end and rolls back on exception. Services/routers never call `db.commit()`.
- Errors: raise `AppError` subclasses from `app/utils/errors.py`. Handlers emit `{"error", "message"}` where `error` is the class name; unhandled exceptions are masked as a generic 500 (logged). Domain errors (`ClaimNotFoundError`, `HookOccupiedError`, `EventNotOpenError`, ...) exist so the Guest and Venue apps can switch on `error`. Add a new subclass rather than reusing a generic one when a client needs to tell the cases apart.
- Endpoints agreed in the contract but not built yet call a service that raises `NotImplementedYetError` (501).
- Enums are uppercase strings defined once in `app/models/enums.py` (`create_type=False`); mirror them as `Literal[...]` in `app/schemas/common.py`.
- IDs are integer autoincrement. Tokens (`c_...`, `v_...`) are random, never primary keys, and never sequential.

### camelCase contract

- Every schema extends `CamelModel` (`app/schemas/base.py` — snake_case attributes, camelCase aliases, `populate_by_name=True`).
- Every route must declare `response_model` (guarded by `app/tests/test_response_conventions.py`).
- Return ORM rows directly where the schema matches; Pydantic serializes them (`from_attributes=True`).
- Eagerly load (`joinedload`/`selectinload`) any relationship a schema touches to avoid `MissingGreenlet`.
- After changing a route or schema, run `scripts.export_openapi` and commit `openapi.json`.

### Auth (Clerk)

- Session tokens verified by `authenticate_clerk_request` in `app/dependencies/auth.py` — a thin wrapper around the `clerk-backend-api` SDK's `authenticate_request` (`accepts_token=["session_token"]`, `azp` allowlist via `CLERK_AUTHORIZED_PARTIES`, optional networkless verification via `CLERK_JWT_KEY`).
- One Clerk account per venue (`venues.clerk_user_id`), shared on its counter devices. `get_current_venue` maps the token's `sub` to the venue; an unlinked account is a 403 `NotVenueAccountError`. It also sets `request.state.clerk_user_id`, recorded on claim history as the actor.
- Every Venue query filters by the current venue's id. One venue never sees another's data.
- Guests have no accounts: holding the claim token is the authorization for that claim. `POST /guest/claims` is rate limited (slowapi).

### Domain rules the database enforces

- One `STORED` claim per hook (partial unique index `uq_claims_one_stored_per_hook`).
- One non-`CLOSED` event per venue (`uq_events_one_active_per_venue`).
- A `STORED` claim always has a hook; `item_count` is 1–20; hook `(venue_id, rack, number)` is unique.
- `claim_events.scan_id` is unique: replays of a Venue app write are detected, not applied twice.

Partial indexes carry both `postgresql_where` and `sqlite_where` so the SQLite test DB enforces them too. Keep both when adding one.

## Testing (`app/tests/`)

- `conftest.py` injects fake env vars **before** importing the app, using `os.environ.setdefault` — real exported env vars leak into tests.
- Tests run on in-memory SQLite (aiosqlite). Postgres-only constructs need a SQLite path (see the partial indexes, and `JSONB` via `sa.JSON().with_variant(...)`).
- Clerk verification is replaced with HS256 test tokens (`sub="user_<hex>"`). Use `make_test_token`, `create_venue`, `auth_headers_for`, and the `venue`/`venue_headers` fixtures.
- Rate limiting is disabled by an autouse fixture.

## Alembic

- Migrations live in `alembic/versions/`. Enum types are created by the first `op.create_table` that uses them and dropped explicitly at the end of `downgrade`.
- Check a new migration with `upgrade head`, `downgrade base`, `upgrade head`, `alembic check` against a real Postgres.
