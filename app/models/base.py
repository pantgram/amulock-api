import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID primary key. Generated in Python so the id is known before flush; the database default
    (gen_random_uuid()) covers rows inserted outside the app."""
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4, server_default=sa.func.gen_random_uuid())
