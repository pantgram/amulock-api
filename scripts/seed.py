"""Seed a demo venue for local development and the thin slice.

    uv run python -m scripts.seed --clerk-user-id user_2abc...

Creates "Demo Club" with hooks A-1..A-20 and B-1..B-20 and an open event, linked to a Clerk
account so the Venue app can call the venue endpoints once signed in with it.
Create that account in the Clerk dashboard (Users) and copy its user ID.
Safe to re-run: it does nothing if the demo venue already exists.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.config.database import async_session_factory, engine
from app.config.settings import settings
from app.models import Event, Hook, Venue
from app.utils.tokens import TokenKind, new_token

DEMO_SLUG = "demo-club"
HOOKS_PER_RACK = 20


async def seed(clerk_user_id: str) -> None:
    async with async_session_factory() as db:
        if (await db.execute(select(Venue).where(Venue.slug == DEMO_SLUG))).scalar_one_or_none():
            print("Demo venue already exists. Nothing to do.")
            return

        venue = Venue(
            name="Demo Club",
            slug=DEMO_SLUG,
            counter_token=new_token(TokenKind.COUNTER),
            clerk_user_id=clerk_user_id,
        )
        db.add(venue)
        await db.flush()
        for rack in ("A", "B"):
            for number in range(1, HOOKS_PER_RACK + 1):
                db.add(Hook(venue_id=venue.id, rack=rack, number=number))
        db.add(Event(venue_id=venue.id, name="Demo night"))
        await db.commit()
    await engine.dispose()

    print("Seeded Demo Club\n")
    print(f"Counter QR:  {settings.guest_base_url}/v/{venue.counter_token}")
    print(f"Clerk user:  {clerk_user_id}")
    print(f"Hooks:       A-1 to A-{HOOKS_PER_RACK}, B-1 to B-{HOOKS_PER_RACK}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clerk-user-id", required=True, help="e.g. user_2abc... from Clerk")
    args = parser.parse_args()
    asyncio.run(seed(args.clerk_user_id))
