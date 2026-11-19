"""Application settings loaded from the environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional dotenv file."""

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
