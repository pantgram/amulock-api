import sqlalchemy as sa

# Postgres enum types are created and dropped explicitly in migrations (create_type=False).
event_status_enum = sa.Enum("OPEN", "CLOSING", "CLOSED", name="event_status", create_type=False)
claim_status_enum = sa.Enum(
    "CREATED", "STORED", "RETURNED", "UNCLAIMED", "VOID", name="claim_status", create_type=False
)
item_category_enum = sa.Enum("COAT", "BAG", "KEYS", "OTHER", name="item_category", create_type=False)
claim_event_type_enum = sa.Enum(
    "CREATED",
    "STORED",
    "RETURNED",
    "UNCLAIMED",
    "VOIDED",
    "PHONE_ADDED",
    "NOTE_CHANGED",
    name="claim_event_type",
    create_type=False,
)

ALL_ENUMS = (event_status_enum, claim_status_enum, item_category_enum, claim_event_type_enum)
