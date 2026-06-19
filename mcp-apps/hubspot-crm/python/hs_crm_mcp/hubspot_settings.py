"""HubSpot CRM settings — pydantic-settings with dotenv support."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class HubSpotSettings(BaseSettings):
    """Configuration loaded from environment / .env file."""

    # HubSpot auth (Private App Token for now)
    hubspot_access_token: str = ""

    # Server
    port: int = 8082
    cors_origins: str = "*"

    # Telemetry (optional)
    appinsights_connection_string: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> HubSpotSettings:
    """Return cached settings singleton."""
    return HubSpotSettings()


def reset_settings_cache() -> None:
    """Clear settings cache (useful for testing)."""
    get_settings.cache_clear()
