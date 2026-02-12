import redis.asyncio as aioredis
import structlog

from pan.config.settings import RedisSettings

logger = structlog.get_logger()


class RedisService:
    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings
        self._prefix = settings.key_prefix
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            self._settings.url,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("redis_connected", host=self._settings.host)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            logger.info("redis_closed")

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> str | None:
        return await self.client.get(self._key(key))

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        await self.client.set(self._key(key), value, ex=ex)

    async def delete(self, key: str) -> bool:
        result = await self.client.delete(self._key(key))
        return bool(result)

    async def publish(self, channel: str, message: str) -> int:
        return await self.client.publish(self._key(channel), message)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(self._key(key)))

    async def setex(self, key: str, seconds: int, value: str) -> None:
        await self.client.setex(self._key(key), seconds, value)
