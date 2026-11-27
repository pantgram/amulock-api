import urllib.parse

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 5000
    database_url: str
    node_env: str = "development"
    log_file: str = "/tmp/amulock_api.log"
    log_level: str = "INFO"

    # Comma-separated browser origins allowed by CORS (Guest app, Venue app).
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    clerk_secret_key: str
    # Optional PEM public key: networkless verification. Empty → JWKS fallback.
    clerk_jwt_key: str = ""
    # Comma-separated `azp` allowlist; parsed into clerk_authorized_parties_list.
    clerk_authorized_parties: str = ""
    # Svix signing secret of the Clerk webhook endpoint (whsec_...). Empty → every delivery is rejected.
    clerk_webhook_secret: str = ""

    # Secret for guest contacts: the encryption and lookup-hash keys are derived from it.
    # Changing it makes existing contacts unreadable and unsearchable.
    contact_secret_key: str

    # Per client IP on POST /guest/claims (slowapi syntax). Guests on the venue's Wi-Fi or a carrier
    # network share one public IP, so keep it high enough for a busy door; it only stops floods.
    # Behind a reverse proxy, set FORWARDED_ALLOW_IPS (read by uvicorn) so the real client IP is used.
    guest_claim_rate_limit: str = "120/minute"

    @computed_field
    @property
    def clerk_authorized_parties_list(self) -> list[str]:
        # Never pass the raw comma-separated string to AuthenticateRequestOptions:
        # it would become a single allowlist element and every request would fail.
        return [party.strip() for party in self.clerk_authorized_parties.split(",") if party.strip()]

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field
    @property
    def async_database_url(self) -> str:
        # asyncpg rejects libpq-only query params (sslmode, ...); strip them.
        parsed = urllib.parse.urlparse(self.database_url)
        query = urllib.parse.parse_qs(parsed.query)
        unsupported = {"sslmode", "channel_binding", "ssl", "sslrootcert", "sslcert", "sslkey"}
        filtered = {k: v for k, v in query.items() if k not in unsupported}
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(filtered, doseq=True)))

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
