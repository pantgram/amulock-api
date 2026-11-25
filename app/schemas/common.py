from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator

from app.schemas.base import CamelModel
from app.utils import contact
from app.utils.tokens import TOKEN_PATTERN

# Mirrors app/models/enums.py.
EventStatus = Literal["draft", "open", "closed"]
ClaimStatus = Literal["pending", "stored", "collected", "unclaimed", "cancelled"]
ContactType = Literal["phone", "email"]
ClaimSource = Literal["guest", "staff"]

Token = Annotated[str, Field(pattern=TOKEN_PATTERN, examples=["c_q3V1bm9HZ0NvYXQxMjM0NQ"])]


class ContactInput(CamelModel):
    """A guest's phone (E.164, e.g. +306912345678) or email. `contact` comes back normalized."""

    contact_type: ContactType
    contact: str = Field(min_length=3, max_length=254)

    @field_validator("contact")
    @classmethod
    def _normalize(cls, value: str, info: ValidationInfo) -> str:
        contact_type = info.data.get("contact_type")
        return contact.normalize(contact_type, value) if contact_type else value


class HealthResponse(CamelModel):
    status: str
    timestamp: str
