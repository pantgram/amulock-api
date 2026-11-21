from typing import Annotated, Literal

from pydantic import Field

from app.schemas.base import CamelModel

ClaimToken = Annotated[str, Field(pattern=r"^c_[A-Za-z0-9_-]{22}$", examples=["c_Q2xhaW1Ub2tlbkV4YW1wbGU"])]
CounterToken = Annotated[str, Field(pattern=r"^v_[A-Za-z0-9_-]{22}$", examples=["v_Q291bnRlclRva2VuRXhhbXA"])]
ShortCode = Annotated[str, Field(description="Display form, e.g. 'K7F-2QX'", examples=["K7F-2QX"])]

ClaimStatus = Literal["CREATED", "STORED", "RETURNED", "UNCLAIMED", "VOID"]
EventStatus = Literal["OPEN", "CLOSING", "CLOSED"]
ItemCategory = Literal["COAT", "BAG", "KEYS", "OTHER"]


class MessageResponse(CamelModel):
    message: str


class HealthResponse(CamelModel):
    status: str
    timestamp: str
