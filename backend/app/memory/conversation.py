import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ConversationMemory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: AsyncConnectionPool | None = None
        self._checkpointer: BaseCheckpointSaver | None = None
        self._started = False

    @property
    def checkpointer(self) -> BaseCheckpointSaver:
        if self._checkpointer is None:
            raise RuntimeError("Conversation memory has not been started.")

        return self._checkpointer

    async def start(self) -> None:
        if self._started:
            return

        if self._settings.conversation_memory_backend == "memory":
            self._checkpointer = InMemorySaver()
            self._started = True

            logger.info("Conversation memory started with in-memory backend.")

            return

        database_url = self._get_psycopg_database_url()

        self._pool = AsyncConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=self._settings.conversation_memory_pool_size,
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )

        await self._pool.open()
        await self._pool.wait()

        checkpointer = AsyncPostgresSaver(self._pool)

        await checkpointer.setup()

        self._checkpointer = checkpointer
        self._started = True

        logger.info("Conversation memory started with PostgreSQL backend")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

        self._checkpointer = None
        self._started = False

        logger.info("Conversation memory resources closed.")

    def _get_psycopg_database_url(self) -> str:
        database_url = self._settings.job_database_url

        if not database_url:
            raise ValueError(
                "JOB_DATABASE_URL is required when "
                "CONVERSATION_MEMORY_BACKEND=postgres."
            )

        if database_url.startswith("postgresql+asyncpg://"):
            return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

        if database_url.startswith("postgresql://"):
            return database_url

        raise ValueError(
            "JOB_DATABASE_URL must use postgresql+asyncpg:// or postgresql://."
        )
