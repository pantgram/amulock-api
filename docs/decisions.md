# Decisions

Short records of what we agreed and why. Change a decision with a PR that edits this file, reviewed by both engineers.

## Scope for now

In: the Guest app, the Venue app, and this API.

Out, to be introduced later: the Admin app, staff users and roles, and plans/subscriptions.
Nothing in the schema or the contract depends on them, so adding them later is additive.

---

## D1. Claim lifecycle

A **claim** is one guest's right to collect one or more items from one event.

```
            guest scans counter QR
                     │
                     ▼
               ┌──────────┐   staff links it to a hook   ┌──────────┐
               │ CREATED  │ ───────────────────────────► │  STORED  │
               └──────────┘                              └──────────┘
                     │                                     │      │
   expires (2 h) or  │                          pickup scan│      │event closed
   staff cancels     ▼                                     ▼      ▼
               ┌──────────┐                        ┌──────────┐ ┌───────────┐
               │   VOID   │                        │ RETURNED │ │ UNCLAIMED │
               └──────────┘                        └──────────┘ └───────────┘
                                                         ▲            │
                                                         └────────────┘
                                                    collected after closing
```

| From | To | Trigger | Who |
|---|---|---|---|
| — | `CREATED` | Guest opens the counter QR | Guest app |
| `CREATED` | `STORED` | Drop-off: staff scan the claim QR; the API assigns the next free hook, or staff pick one | Venue app |
| `CREATED` | `VOID` | Not stored within 2 h, or staff cancel | Job / Venue app |
| `STORED` | `RETURNED` | Pickup: staff scan claim QR (or look up short code) | Venue app |
| `STORED` | `UNCLAIMED` | Event closed while the item is still on a hook | Close-event flow |
| `UNCLAIMED` | `RETURNED` | Guest collects it later | Venue app |

Rules:
- A hook holds at most one `STORED` claim at a time (enforced by a partial unique index).
- `RETURNED` and `VOID` are final.
- Every transition writes a `claim_events` row. Nothing is ever updated without one.

## D2. Tokens and QR payloads

All QR codes encode a URL, so a phone camera opens something sensible whoever scans it.

| QR | Payload | Token |
|---|---|---|
| Counter QR (one per venue) | `https://g.amulock.com/v/{counter_token}` | `v_` + 22 chars |
| Guest claim QR | `https://g.amulock.com/c/{claim_token}` | `c_` + 22 chars |

- Token body: 16 random bytes (128 bits), base64url without padding → 22 chars. Never sequential, never guessable.
- The prefix tells the Venue app what it scanned (a guest's claim, or a venue's counter QR by mistake).
- Hooks have no QR codes. They are identified by rack and number ("B-12"), which venues already paint or stick on their hooks.
- The counter token can be rotated from the Venue app (e.g. if a photo of the counter QR leaks online).

**Short code**: 6 characters from the Crockford base32 alphabet (no I, L, O, U), shown as `K7F-2QX`. Unique within an event. Used when the guest's phone is dead: staff type it in.

## D3. Errors

Same format as `homidirect-api`: every error is `{"error": "<Name>", "message": "<human text>"}`.

```json
{"error": "HookOccupiedError", "message": "B-12 already holds claim K7F-2QX"}
```

Clients switch on `error`, never on `message` (that's for humans and may change). Validation errors are `{"error": "Validation Error", "message": "Invalid request data", "details": [{"path", "message"}]}`.

| error | status | When |
|---|---|---|
| `NotImplementedYetError` | 501 | Endpoint agreed in the contract but not built yet |
| `Validation Error` | 422 | Request body or params are invalid |
| `UnauthorizedError` | 401 | Missing, expired or invalid Clerk session token |
| `NotVenueAccountError` | 403 | Valid Clerk account, but not linked to a venue |
| `CounterNotFoundError` | 404 | Unknown or rotated counter token |
| `ClaimNotFoundError` | 404 | Unknown claim token or short code |
| `HookNotFoundError` | 404 | Unknown or inactive hook (or another venue's) |
| `EventNotOpenError` | 409 | No open event at this venue |
| `ClaimWrongStateError` | 409 | The transition isn't allowed from the claim's current status |
| `HookOccupiedError` | 409 | The hook already holds a stored claim |
| `NoFreeHookError` | 409 | Every active hook holds a stored claim |

## D4a. Hook assignment

On drop-off the API picks the next free active hook: lowest rack, then lowest number, skipping hooks that hold a `STORED` claim. The attendant can pick a different hook instead (`hookId`), e.g. for a bulky coat or when a hook is physically full.
Two attendants assigning at the same moment can't get the same hook: the partial unique index on `claims(hook_id) WHERE status = 'STORED'` rejects the second, and the API retries with the next free hook.

## D4. Idempotent Venue app writes

Every Venue app write (drop-off, pickup, cancel) carries a client-generated `scan_id` (UUID v4).
The server stores it on the `claim_events` row with a unique constraint. Replaying the same `scan_id` returns the original result instead of failing or acting twice.
The Venue app's offline queue depends on this, so it is in the contract from day one.

## D5. Multi-tenancy

Top-level tables (`events`, `hooks`, `claims`) carry `venue_id`; `claim_events` is reached through its claim. Every Venue app query filters by the venue of the signed-in Clerk account, so one venue can never see another's data.
A hook is a single row: `rack` ("B") plus `number` (12), unique per venue. Racks become their own table only if they gain settings of their own.

## D6. Authentication (Clerk)

- **One Clerk account per venue** for now, signed in on the venue's counter devices. `venues.clerk_user_id` links it (the `sub` claim of the token). A Clerk account that isn't linked to a venue gets `403 not_venue_account`.
- The Venue app sends Clerk's short-lived session token as `Authorization: Bearer <token>`.
- The API verifies it locally: RS256 signature against Clerk's JWKS (cached), `exp`/`nbf`, `iss` = our Clerk Frontend API URL, and `azp` in `CLERK_AUTHORIZED_PARTIES` (so a token issued to another site is refused).
- Each claim change records `actor_clerk_user_id`, so when individual staff accounts arrive the audit trail already has the right shape.
- **Guests**: no accounts. Possession of the claim token is the authorization for that one claim.
- **Later**: individual staff accounts and roles (likely Clerk Organizations, one per venue), and admin sign-in.

## D7. Personal data

- Guest phone numbers are opt-in, stored encrypted (`guest_phone_enc`), and deleted 30 days after the event closes.
- Logs never contain phone numbers or full tokens (first 6 chars at most).

## D8. Conventions

Same as `homidirect-api` (see `AGENTS.md`):

- API paths under `/api/v1`: `/api/v1/guest/...` (no auth), `/api/v1/venue/...` (the venue's Clerk account).
- JSON in `camelCase` (via `CamelModel`); Python and the database in `snake_case`. Timestamps in UTC, ISO 8601.
- IDs are integers. Tokens are never used as primary keys.
- Enum values are uppercase strings (`STORED`, `COAT`).

## Open

- One claim per guest with `item_count`, or one claim per item. The schema supports `item_count` now.
