"""Random tokens encoded in QR codes. Never sequential, never guessable, never primary keys."""

import secrets
from enum import StrEnum


class TokenKind(StrEnum):
    COUNTER = "v"  # venues.counter_token: the permanent counter QR
    CLAIM = "c"  # claims.guest_token: the guest's claim QR


TOKEN_PATTERN = r"^[vc]_[A-Za-z0-9_-]{22}$"


def new_token(kind: TokenKind) -> str:
    """`<prefix>_` + 22 url-safe chars (128 random bits). The prefix tells a scanner what it read."""
    return f"{kind.value}_{secrets.token_urlsafe(16)}"


def token_kind(token: str) -> TokenKind | None:
    prefix, sep, body = token.partition("_")
    if not sep or len(body) != 22:
        return None
    try:
        return TokenKind(prefix)
    except ValueError:
        return None
