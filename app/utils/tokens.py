"""Token and short-code generation. See docs/decisions.md D2."""

import secrets
from enum import StrEnum

# Crockford base32 without I, L, O, U
SHORT_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
SHORT_CODE_LENGTH = 6


class TokenKind(StrEnum):
    COUNTER = "v"
    CLAIM = "c"


def new_token(kind: TokenKind) -> str:
    """`<prefix>_` + 22 url-safe chars (128 random bits)."""
    return f"{kind.value}_{secrets.token_urlsafe(16)}"


def token_kind(token: str) -> TokenKind | None:
    prefix, sep, body = token.partition("_")
    if not sep or len(body) != 22:
        return None
    try:
        return TokenKind(prefix)
    except ValueError:
        return None


def new_short_code() -> str:
    """Raw 6-char code, e.g. 'K7F2QX'. Display as 'K7F-2QX'."""
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH))


def format_short_code(code: str) -> str:
    return f"{code[:3]}-{code[3:]}"


def normalize_short_code(text: str) -> str:
    """Accept what the attendant types: lower case, dashes, spaces, and O/I/L confused for 0/1/1."""
    cleaned = text.upper().replace("-", "").replace(" ", "")
    return cleaned.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))
