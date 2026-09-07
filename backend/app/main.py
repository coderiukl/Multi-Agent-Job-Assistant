import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import (
    close_job_search_resources,
    start_conversation_memory_resources,
)
from app.api.router import create_api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware

settings = get_settings()
configure_logging(settings)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = settings

    await start_conversation_memory_resources()

    logger.info(
        "Application started: %s version=%s environment=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    try:
        yield
    finally:
        await close_job_search_resources()
        logger.info("Application stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=settings.backend_cors_allow_credentials,
    allow_methods=[
        "GET",
        "PUT",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600
)

app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)
app.include_router(create_api_router(settings))