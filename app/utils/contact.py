"""Guest contacts (phone or email): normalized, then stored encrypted and as a keyed hash.

The hash (HMAC-SHA256) lets staff find claims by contact without decrypting every row.
Both keys are derived from CONTACT_SECRET_KEY; rotating it orphans existing rows.
"""

import base64
import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config.settings import settings

PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize(contact_type: str, value: str) -> str:
    """Canonical form, so the same contact always hashes the same. Raises ValueError if invalid."""
    if contact_type == "phone":
        phone = re.sub(r"[\s().-]", "", value)
        if phone.startswith("00"):
            phone = "+" + phone[2:]
        if not PHONE_PATTERN.match(phone):
            raise ValueError("Phone must be in international format, e.g. +306912345678")
        return phone
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email address")
    return email


def _subkey(purpose: bytes) -> bytes:
    return hmac.new(settings.contact_secret_key.encode(), purpose, hashlib.sha256).digest()


@lru_cache
def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_subkey(b"amulock-contact-encryption")))


def hash_contact(normalized: str) -> bytes:
    return hmac.new(_subkey(b"amulock-contact-hash"), normalized.encode(), hashlib.sha256).digest()


def encrypt(normalized: str) -> bytes:
    return _fernet().encrypt(normalized.encode())


def decrypt(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode()


def mask(contact_type: str, normalized: str) -> str:
    if contact_type == "phone":
        return normalized[:3] + "•" * (len(normalized) - 7) + normalized[-4:]
    local, _, domain = normalized.partition("@")
    return f"{local[0]}•••@{domain}"
