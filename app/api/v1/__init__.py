from fastapi import APIRouter

from . import guest, health, venue

router = APIRouter(prefix="/v1")

router.include_router(health.router)
router.include_router(guest.router)
router.include_router(venue.router)
