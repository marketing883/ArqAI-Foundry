"""Integration framework base classes."""

from services.integrations.framework.base import IntegrationConnector
from services.integrations.framework.registry import IntegrationRegistry

__all__ = ["IntegrationConnector", "IntegrationRegistry"]
