from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException

from app.api.v1 import router
from app.config.database import engine
from app.config.limiter import limiter
from app.config.logging_config import logger
from app.config.settings import settings
from app.utils.errors import (
    AppError,
    app_error_handler,
    generic_error_handler,
    http_exception_handler,
    rate_limit_handler,
    validation_error_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    yield
    logger.info("Application shutdown")
    await engine.dispose()


openapi_tags = [
    {"name": "Health", "description": "Service health checks"},
    {"name": "Guest", "description": "Guest app: claims opened from the counter QR (no auth)"},
    {"name": "Venue", "description": "Venue app: events, positions, drop-off and pickup (Clerk)"},
    {"name": "Webhooks", "description": "Clerk user lifecycle events (Svix-signed): venue account provisioning"},
]

app = FastAPI(title="Amulock API", version="0.1.0", lifespan=lifespan, openapi_tags=openapi_tags)
app.include_router(router, prefix="/api")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
