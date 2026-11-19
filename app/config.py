"""Environment-backed configuration shared by the application layers."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configure API access, campaign defaults, persistence, and application logs.

    Values are read from environment variables, with an optional local ``.env``
    file for development. Defaults keep the application importable without API
    credentials so that health checks and local tests can run independently.
    """

    keitaro_url: str = ""

    keitaro_api_key: str = ""

    campaign_prefix: str = "test_lkmavi_"

    redirect_url: str = "https://www.google.com/"

    keitaro_timeout: float = 20.0

    service_name: str = "adrobot"

    log_level: str = "INFO"

    offer_creation_enabled: bool = True

    log_file: str = ""

    database_path: str = "adrobot.sqlite3"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
