"""Error format: every error response is {"error": <name>, "message": <human text>}.

Clients switch on `error` (a stable class name), never on `message`.
Raise AppError subclasses from services and routers; unhandled exceptions are masked as a generic 500.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config.logging_config import logger

_ERROR_NAMES_BY_STATUS = {
    400: "ValidationError",
    401: "UnauthorizedError",
    403: "ForbiddenError",
    404: "NotFoundError",
    405: "MethodNotAllowedError",
    409: "ConflictError",
    422: "ValidationError",
}


class AppError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class ValidationError(AppError):
    def __init__(self, message: str = "Validation Error"):
        super().__init__(400, message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(401, message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(403, message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not Found"):
        super().__init__(404, message)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict"):
        super().__init__(409, message)


class InternalServerError(AppError):
    def __init__(self, message: str = "Internal Server Error"):
        super().__init__(500, message)


class NotImplementedYetError(AppError):
    """Endpoint agreed in the contract (openapi.json) but not built yet."""

    def __init__(self, message: str = "Not implemented yet"):
        super().__init__(501, message)


# --- Domain errors: specific names so the Guest and Venue apps can switch on them ---


class NotVenueAccountError(ForbiddenError):
    def __init__(self, message: str = "This account isn't linked to a venue"):
        super().__init__(message)


class CounterNotFoundError(NotFoundError):
    def __init__(self, message: str = "Unknown counter QR"):
        super().__init__(message)


class EventNotFoundError(NotFoundError):
    def __init__(self, message: str = "Event not found"):
        super().__init__(message)


class PositionNotFoundError(NotFoundError):
    def __init__(self, message: str = "Position not found or inactive"):
        super().__init__(message)


class ClaimNotFoundError(NotFoundError):
    def __init__(self, message: str = "Claim not found"):
        super().__init__(message)


class EventNotOpenError(ConflictError):
    def __init__(self, message: str = "The cloakroom isn't open"):
        super().__init__(message)


class EventAlreadyOpenError(ConflictError):
    def __init__(self, message: str = "An event is already open; close it first"):
        super().__init__(message)


class EventWrongStateError(ConflictError):
    """The change isn't allowed from the event's current status (e.g. reopening a closed event)."""

    def __init__(self, message: str = "Not allowed in the event's current status"):
        super().__init__(message)


class PositionAlreadyExistsError(ConflictError):
    def __init__(self, message: str = "A position with that zone and number already exists"):
        super().__init__(message)


class PositionOccupiedError(ConflictError):
    def __init__(self, message: str = "That position already holds a stored claim"):
        super().__init__(message)


class NoFreePositionError(ConflictError):
    def __init__(self, message: str = "Every active position holds a stored claim"):
        super().__init__(message)


class ClaimWrongStateError(ConflictError):
    def __init__(self, message: str = "Not allowed in the claim's current status"):
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "message": exc.message},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        error_name = "InternalServerError"
    else:
        error_name = _ERROR_NAMES_BY_STATUS.get(exc.status_code, "HttpError")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_name, "message": str(exc.detail)},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "path": ".".join(str(p) for p in err["loc"] if p != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Invalid request data",
            "details": details,
        },
    )


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "RateLimitedError", "message": "Too many requests; try again in a minute"},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "An unexpected error occurred"},
    )
