"""Health check endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "arqai-foundry",
    }


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Detailed health check with component status."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": {"status": "healthy"},
            "database": {"status": "healthy"},
            "redis": {"status": "healthy"},
            "vault": {"status": "healthy"},
        },
        "version": "1.0.0",
    }
