from app.schemas.base import CamelModel


class WebhookAckResponse(CamelModel):
    received: bool = True
