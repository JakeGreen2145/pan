from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pan.config.settings import (
    DatabaseSettings,
    DiscordSettings,
    OpenRouterSettings,
    PortainerSettings,
    RedisSettings,
    Settings,
)
from pan.services.database import Base


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        db=DatabaseSettings(
            host="localhost",
            port=5432,
            user="test",
            password="test",  # type: ignore[arg-type]  # noqa: S106
            name="pan_test",
        ),
        redis=RedisSettings(host="localhost", port=6379),
        discord=DiscordSettings(
            token="test-token",  # type: ignore[arg-type]  # noqa: S106
            guild_id=123456789,
            admin_user_ids=[111111111],
        ),
        openrouter=OpenRouterSettings(
            api_key="sk-test-key",  # type: ignore[arg-type]
        ),
        portainer=PortainerSettings(
            base_url="https://portainer.test:9443",
            api_key="ptr_test",  # type: ignore[arg-type]
            endpoint_id=1,
        ),
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_redis() -> AsyncMock:
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    mock.delete = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_portainer_response() -> list[dict]:
    return [
        {
            "Id": "abc123def456",
            "Names": ["/nginx-proxy"],
            "Image": "nginx:latest",
            "State": "running",
            "Status": "Up 3 days",
        },
        {
            "Id": "789ghi012jkl",
            "Names": ["/postgres-main"],
            "Image": "postgres:16",
            "State": "running",
            "Status": "Up 5 days",
        },
        {
            "Id": "mno345pqr678",
            "Names": ["/stopped-service"],
            "Image": "alpine:latest",
            "State": "exited",
            "Status": "Exited (0) 2 hours ago",
        },
    ]
