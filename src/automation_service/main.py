"""Main entry point for the Automation Service."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from automation_service.api.routes import router
from automation_service.core.config import settings
from automation_service.core.logging import setup_logging
from automation_service.services.browser import BrowserManager

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    setup_logging()
    logger.info(
        "Starting Automation Service",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )

    # Initialize browser manager
    app.state.browser_manager = BrowserManager()
    await app.state.browser_manager.initialize()

    yield

    # Shutdown
    logger.info("Shutting down Automation Service")
    await app.state.browser_manager.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SDA Automation Service",
        description="Web automation service for Club Virtual IASD",
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router, prefix="/api/v1")

    return app


app = create_app()


def main() -> None:
    """Run the application."""
    uvicorn.run(
        "automation_service.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
