"""Seed a demo venue for local development.

    uv run python -m scripts.seed --clerk-user-id user_2abc...

Creates "Demo Club" with positions A-1..A-20 and B-1..B-20 and an open event, linked to a Clerk
account so the Venue app can call the venue endpoints once signed in with it.
Create that account in the Clerk dashboard (Users) and copy its user ID.
Safe to re-run: it does nothing if that Clerk account already has a venue.
"""

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.config.database import async_session_factory, engine
from app.models import Event, Position, Venue
from app.utils.tokens import TokenKind, new_token

POSITIONS_PER_ZONE = 20


async def seed(clerk_id: str) -> None:
    async with async_session_factory() as db:
        if await db.scalar(select(Venue).where(Venue.clerk_id == clerk_id)):
            print("That Clerk account already has a venue. Nothing to do.")
            await engine.dispose()
            return

        venue = Venue(name="Demo Club", clerk_id=clerk_id, counter_token=new_token(TokenKind.COUNTER))
        db.add(venue)
        await db.flush()
        for zone in ("A", "B"):
            for number in range(1, POSITIONS_PER_ZONE + 1):
                db.add(Position(venue_id=venue.id, zone=zone, number=number))
        db.add(
            Event(
                venue_id=venue.id,
                name="Demo night",
                starts_at=datetime.now(timezone.utc),
                offer_text="Show your claim at the bar for a free shot",
                status="open",
                opened_at=func.now(),
            )
        )
        await db.commit()
        counter_token = venue.counter_token
    await engine.dispose()

    print("Seeded Demo Club\n")
    print(f"Clerk user:     {clerk_id}")
    print(f"Counter token:  {counter_token}")
    print(f"Positions:      A-1 to A-{POSITIONS_PER_ZONE}, B-1 to B-{POSITIONS_PER_ZONE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clerk-user-id", required=True, help="e.g. user_2abc... from Clerk")
    args = parser.parse_args()
    asyncio.run(seed(args.clerk_user_id))
