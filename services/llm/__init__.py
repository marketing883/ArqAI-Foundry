"""
LLM Abstraction Layer

Provides a unified interface for multiple LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Cohere
- Mistral
- Azure OpenAI
- AWS Bedrock
- BYOL (Bring Your Own LLM)
"""

from services.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMUsage,
)
from services.llm.registry import LLMRegistry

__all__ = [
    "LLMProvider",
    "LLMConfig",
    "LLMMessage",
    "LLMResponse",
    "LLMUsage",
    "LLMRegistry",
]
