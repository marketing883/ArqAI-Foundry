"""
FastAPI Application Factory

Creates and configures the ArqAI Foundry API application.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    agents,
    builder,
    evidence,
    health,
    integrations,
    llm,
    templates,
    workspaces,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    logger.info("arqai_foundry_starting")

    # Initialize services
    await _initialize_services()

    yield

    # Shutdown
    logger.info("arqai_foundry_shutting_down")
    await _shutdown_services()


async def _initialize_services() -> None:
    """Initialize application services."""
    # Register vertical templates
    from services.templates.registry import get_template_registry
    from services.templates.verticals import register_all_vertical_templates

    registry = get_template_registry()
    count = register_all_vertical_templates(registry)
    logger.info("vertical_templates_registered", count=count)


async def _shutdown_services() -> None:
    """Shutdown application services."""
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ArqAI Foundry",
        description="Enterprise AI Agent Foundry - Build Trusted AI Agents",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(templates.router, prefix="/api/v1/templates", tags=["Templates"])
    app.include_router(builder.router, prefix="/api/v1/builder", tags=["Agent Builder"])
    app.include_router(workspaces.router, prefix="/api/v1/workspaces", tags=["Workspaces"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
    app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
    app.include_router(llm.router, prefix="/api/v1/llm", tags=["LLM"])

    logger.info("arqai_foundry_app_created")

    return app
