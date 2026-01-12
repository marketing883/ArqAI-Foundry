"""
ArqAI Foundry API

FastAPI application providing REST endpoints for:
- Agent Builder Studio
- Template Management
- Agent Operations
- Evidence & Audit
- System Administration
"""

from api.app import create_app

__all__ = ["create_app"]
