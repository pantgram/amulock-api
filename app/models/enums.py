import sqlalchemy as sa

# Postgres enum types are created and dropped explicitly in migrations (create_type=False).
# Values are lowercase, as in the database schema; app/schemas/common.py mirrors them.
event_status_enum = sa.Enum("draft", "open", "closed", name="event_status", create_type=False)
claim_status_enum = sa.Enum(
    "pending", "stored", "collected", "unclaimed", "cancelled", name="claim_status", create_type=False
)
contact_type_enum = sa.Enum("phone", "email", name="contact_type", create_type=False)
claim_source_enum = sa.Enum("guest", "staff", name="claim_source", create_type=False)

ALL_ENUMS = (event_status_enum, claim_status_enum, contact_type_enum, claim_source_enum)
