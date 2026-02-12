"""LangGraph checkpointer using psycopg3 AsyncConnectionPool.

Uses a separate connection pool from SQLAlchemy because
langgraph-checkpoint-postgres requires psycopg3's native async support.
"""

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger()

_checkpointer: AsyncPostgresSaver | None = None
_connection_pool: AsyncConnectionPool | None = None
_initialized: bool = False


async def init_checkpointer(db_url: str) -> AsyncPostgresSaver:
    global _checkpointer, _connection_pool, _initialized

    _connection_pool = AsyncConnectionPool(
        conninfo=db_url,
        min_size=2,
        max_size=10,
        max_lifetime=1800,
        max_idle=300,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    await _connection_pool.open(wait=True)

    _checkpointer = AsyncPostgresSaver(conn=_connection_pool)
    await _checkpointer.setup()
    _initialized = True

    logger.info("checkpointer_initialized")
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None or not _initialized:
        raise RuntimeError("Checkpointer not initialized. Call init_checkpointer() first.")
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _connection_pool, _initialized

    if _connection_pool is not None:
        await _connection_pool.close()
        logger.info("checkpointer_closed")

    _checkpointer = None
    _connection_pool = None
    _initialized = False
