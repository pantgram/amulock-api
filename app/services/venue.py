from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.utils.errors import NotImplementedYetError


async def get_current_event(db: AsyncSession, venue: Venue):
    """The venue's open event with claim counts per status. Errors: EventNotOpenError."""
    raise NotImplementedYetError()


async def list_hooks(db: AsyncSession, venue: Venue):
    """All hooks ordered by rack, then number, with whether each holds a stored claim."""
    raise NotImplementedYetError()
