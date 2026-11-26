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
uv run python -m scripts.seed --clerk-user-id user_x # demo venue with positions and an open event
uv run python -m scripts.export_openapi              # refresh openapi.json (the frontend contract)
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest and `export_openapi --check`.

## Environment gotchas

- `app/config/settings.py` loads `.env` from the **current working directory**. Environment variables take priority over the file.
- Required settings with no default: `DATABASE_URL`, `CLERK_SECRET_KEY`, `CONTACT_SECRET_KEY`. Alembic and the app import `settings` at module load, so anything touching `app.*` fails without them.
- `LOG_FILE` defaults to `/tmp/amulock_api.log`; `FileHandler` does not create parent dirs.
- `settings.async_database_url` strips libpq-only query params (`sslmode`, ...) from `DATABASE_URL` for asyncpg; use it, not `database_url`, for engines.

## Scope for now

In: Guest endpoints (no auth: counter QR, own claim) and Venue endpoints (Clerk: events, positions, claims). Out until later: staff users/roles, an Admin app, plans/billing, notifications (SMS/email) and contact retention jobs.

## Architecture

- Layering: `app/api/v1/` (routers) → `app/services/` (business logic, one module per domain) → `app/models/` (SQLAlchemy) and `app/schemas/` (Pydantic).
- Adding a domain requires touching: new router in `app/api/v1/`, registration in `app/api/v1/__init__.py` (everything mounts under `/api/v1`), tag in `openapi_tags` in `app/main.py`, and model import in `app/models/__init__.py` (needed for Alembic autogenerate and test `create_all`).
- Sessions auto-commit: `get_db` in `app/config/database.py` commits at request end and rolls back on exception. Services/routers never call `db.commit()`.
- Errors: raise `AppError` subclasses from `app/utils/errors.py`. Handlers emit `{"error", "message"}` where `error` is the class name; unhandled exceptions are masked as a generic 500 (logged). Domain errors (`ClaimNotFoundError`, `PositionOccupiedError`, `EventNotOpenError`, ...) exist so the Guest and Venue apps can switch on `error`. Add a new subclass rather than reusing a generic one when a client needs to tell the cases apart.
- Endpoints agreed in the contract but not built yet call a service that raises `NotImplementedYetError` (501). None are left right now.
- Enums are lowercase strings (`open`, `stored`) defined once in `app/models/enums.py` (`create_type=False`); mirror them as `Literal[...]` in `app/schemas/common.py`.
- IDs are UUIDs (`uuid_pk()` in `app/models/base.py`: generated in Python, `gen_random_uuid()` as the DB default). Tokens (`v_...` counter, `c_...` guest claim) are random, never primary keys.
- Guest contacts are normalized (`app/utils/contact.py`), stored Fernet-encrypted plus an HMAC-SHA256 lookup hash, both keyed from `CONTACT_SECRET_KEY`. Responses only ever carry a masked `contactHint`; search goes through `POST /venue/claims/search` so contacts stay out of URLs and logs.
- Claim lifecycle (`app/services/claim.py`): `pending → stored → collected`, `pending → cancelled`; closing an event turns `stored` into `unclaimed` (still collectable) and cancels `pending`.

### camelCase contract

- Every schema extends `CamelModel` (`app/schemas/base.py` — snake_case attributes, camelCase aliases, `populate_by_name=True`).
- Every route must declare `response_model` (guarded by `app/tests/test_response_conventions.py`).
- Return ORM rows directly where the schema matches; Pydantic serializes them (`from_attributes=True`).
- Eagerly load (`joinedload`/`selectinload`) any relationship a schema touches to avoid `MissingGreenlet`.
- After changing a route or schema, run `scripts.export_openapi` and commit `openapi.json`.

### Auth (Clerk)

- Session tokens verified by `authenticate_clerk_request` in `app/dependencies/auth.py` — a thin wrapper around the `clerk-backend-api` SDK's `authenticate_request` (`accepts_token=["session_token"]`, `azp` allowlist via `CLERK_AUTHORIZED_PARTIES`, optional networkless verification via `CLERK_JWT_KEY`).
- One Clerk account per venue (`venues.clerk_id`), shared on its counter devices. `get_current_venue` maps the token's `sub` to the venue; an unlinked account is a 403 `NotVenueAccountError`.
- Venue accounts are provisioned by the Clerk webhook (`POST /webhooks/clerk`, `app/api/v1/webhook.py`, Svix-signed with `CLERK_WEBHOOK_SECRET`; empty secret rejects everything): `user.created` creates an empty venue named from `public_metadata.venueName` (else the account's name), `user.updated` renames it only from that metadata, `user.deleted` removes it only if it never had an event. Handlers are idempotent; tests sign real deliveries with `svix.Webhook.sign`.
- Every Venue query filters by the current venue's id (claims through `events.venue_id`). One venue never sees another's data.
- Guests have no accounts: the counter token opens a claim, and holding the guest token is the authorization for that claim. `POST /guest/claims` is rate limited (slowapi; disabled in tests by an autouse fixture).

### Domain rules the database enforces

- One `open` event per venue (`events_one_open_per_venue`); drafts are unlimited.
- One `stored` claim per position per event (`claims_one_per_position`); a `stored` claim always has a position (`claims_check`).
- Position `(venue_id, zone, number)` is unique and `number > 0`.

Partial indexes carry both `postgresql_where` and `sqlite_where` so the SQLite test DB enforces them too. Keep both when adding one.

## Testing (`app/tests/`)

- `conftest.py` injects fake env vars **before** importing the app, using `os.environ.setdefault` — real exported env vars leak into tests.
- Tests run on in-memory SQLite (aiosqlite) by default. Set `TEST_DATABASE_URL` to an empty Postgres database to run them there (CI does both; the database is wiped after each test). Postgres-only constructs need a SQLite path (see the partial indexes; `conftest.py` registers `NOW()` and `gen_random_uuid()` as SQLite functions).
- Clerk verification is replaced with HS256 test tokens (`sub="user_<hex>"`). Use `make_test_token`, `create_venue`, `auth_headers_for`, and the `venue`/`venue_headers` fixtures.

## Alembic

- Migrations live in `alembic/versions/`. `0001` is the baseline (re-created on 2026-11-25 for the UUID schema; databases from before that must be dropped and re-created). Enum types are created by the first `op.create_table` that uses them and dropped explicitly at the end of `downgrade`.
- Check a new migration with `upgrade head`, `downgrade base`, `upgrade head`, `alembic check` against a real Postgres.
