"""Mint a Clerk session token for a user, to call the Venue endpoints without the Venue app.

    uv run python -m scripts.clerk_token --clerk-user-id user_2abc...
    uv run python -m scripts.clerk_token --clerk-user-id user_2abc... --template amulock
    TOKEN=$(uv run python -m scripts.clerk_token --clerk-user-id user_2abc...)
    curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/v1/venue/...

Uses the Backend API with CLERK_SECRET_KEY (read from the environment or `.env`). Reuses the user's
active session if there is one, otherwise creates one. Creating sessions from the backend only works
on development instances (sk_test_...).

Tokens minted this way carry no `azp` claim, so the API rejects them while CLERK_AUTHORIZED_PARTIES
is set. Leave it empty in your local `.env` to use them.
"""

import argparse
import sys

from clerk_backend_api import Clerk
from clerk_backend_api.models import QueryParamStatus
from pydantic_settings import BaseSettings


class _Settings(BaseSettings):
    # Only the key this script needs, so it runs without DATABASE_URL and the rest.
    clerk_secret_key: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def mint_token(clerk: Clerk, user_id: str, template: str | None, expires_in: int) -> str:
    active = clerk.sessions.list(user_id=user_id, status=QueryParamStatus.ACTIVE, limit=1)
    if active:
        session_id = active[0].id
        print(f"Reusing active session {session_id}", file=sys.stderr)
    else:
        session_id = clerk.sessions.create(request={"user_id": user_id}).id
        print(f"Created session {session_id}", file=sys.stderr)

    if template:
        # Same as the frontend's getToken({ template }): the template's claims, signed by Clerk.
        token = clerk.sessions.create_token_from_template(
            session_id=session_id, template_name=template, expires_in_seconds=expires_in
        )
    else:
        # Same as the frontend's getToken(): the default session token.
        token = clerk.sessions.create_token(session_id=session_id, expires_in_seconds=expires_in)
    if not token.jwt:
        raise RuntimeError("Clerk returned no token")
    return token.jwt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clerk-user-id", required=True, help="Clerk user ID (user_...)")
    parser.add_argument("--template", help="JWT template name (Clerk dashboard: JWT templates)")
    parser.add_argument("--expires-in", type=int, default=3600, help="Token lifetime in seconds (default 3600)")
    args = parser.parse_args()

    settings = _Settings()
    if not settings.clerk_secret_key.startswith("sk_test_"):
        print("Warning: not a development key; creating sessions may be refused.", file=sys.stderr)

    with Clerk(bearer_auth=settings.clerk_secret_key) as clerk:
        jwt = mint_token(clerk, args.clerk_user_id, args.template, args.expires_in)

    # The token alone on stdout, so `TOKEN=$(...)` works; everything else goes to stderr.
    print(jwt)


if __name__ == "__main__":
    main()
