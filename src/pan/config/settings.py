"""Pydantic settings hierarchy for Pan.

All env vars use PAN_ prefix with __ for nesting.
Example: PAN_DB__HOST=localhost → settings.db.host
"""

from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """PostgreSQL connection settings. Env: PAN_DB__HOST, etc."""

    host: str = "localhost"
    port: int = 5432
    user: str = "pan"
    password: SecretStr = SecretStr("changeme")
    name: str = "pan"

    @property
    def async_url(self) -> str:
        """SQLAlchemy async URL for asyncpg driver."""
        pwd = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        """Synchronous URL for Alembic migrations."""
        pwd = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"

    @property
    def psycopg_url(self) -> str:
        """psycopg3 URL for LangGraph checkpointer (uses psycopg, not asyncpg)."""
        pwd = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseModel):
    """Redis connection settings. Env: PAN_REDIS__HOST, etc."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None
    key_prefix: str = "pan:"

    @property
    def url(self) -> str:
        if self.password:
            pwd = self.password.get_secret_value()
            return f"redis://:{pwd}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class DiscordSettings(BaseModel):
    """Discord bot settings. Env: PAN_DISCORD__TOKEN, etc."""

    token: SecretStr
    guild_id: int | None = None
    admin_user_ids: list[int] = []
    notification_channel_id: int | None = None


class OpenRouterSettings(BaseModel):
    """OpenRouter LLM API settings. Env: PAN_OPENROUTER__API_KEY, etc."""

    api_key: SecretStr
    base_url: str = "https://openrouter.ai/api/v1"


class PortainerInstanceSettings(BaseModel):
    base_url: str
    api_key: SecretStr = SecretStr("")
    endpoint_id: int | None = None
    verify_ssl: bool = False


class PortainerSettings(BaseModel):
    """Portainer API settings. Env: PAN_PORTAINER__INSTANCES__<NAME>__BASE_URL, etc."""

    instances: dict[str, PortainerInstanceSettings] = {}


class TrueNASSettings(BaseModel):
    base_url: str = "https://truenas.local/api/v2.0"
    api_key: SecretStr = SecretStr("")
    verify_ssl: bool = False


class ProxmoxSettings(BaseModel):
    base_url: str = "https://proxmox.local:8006"
    api_token: SecretStr = SecretStr("")
    node_name: str = "pve"
    verify_ssl: bool = False


class UniFiSettings(BaseModel):
    base_url: str = "https://unifi.local"
    api_key: SecretStr = SecretStr("")
    verify_ssl: bool = False


class Settings(BaseSettings):
    """Root settings. All env vars use PAN_ prefix, __ for nesting."""

    model_config = SettingsConfigDict(
        env_prefix="PAN_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    discord: DiscordSettings  # Required — no default
    openrouter: OpenRouterSettings  # Required — no default
    portainer: PortainerSettings = PortainerSettings()
    truenas: TrueNASSettings = TrueNASSettings()
    proxmox: ProxmoxSettings = ProxmoxSettings()
    unifi: UniFiSettings = UniFiSettings()

    debug: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()  # type: ignore[call-arg]
