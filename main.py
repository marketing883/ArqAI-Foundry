"""
ArqAI Foundry - Main Entry Point

Enterprise AI Agent Foundry for building trusted AI agents.
"""

import uvicorn

from api.app import create_app

app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
