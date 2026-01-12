"""
LLM Provider Base Classes

Defines the abstract interface for all LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator

import structlog

logger = structlog.get_logger(__name__)


class MessageRole(str, Enum):
    """Message role in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


@dataclass
class LLMMessage:
    """A message in a conversation."""
    role: MessageRole
    content: str
    name: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.function_call:
            d["function_call"] = self.function_call
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


@dataclass
class LLMUsage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    role: MessageRole = MessageRole.ASSISTANT
    model: str = ""
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider: str
    api_key: str | None = None
    api_base: str | None = None
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: list[str] = field(default_factory=list)
    timeout_seconds: int = 60
    max_retries: int = 3

    # Provider-specific
    organization: str | None = None  # OpenAI
    project: str | None = None  # Google
    region: str | None = None  # AWS Bedrock, Azure
    deployment_name: str | None = None  # Azure OpenAI

    # Additional parameters
    extra_params: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All provider implementations must inherit from this class
    and implement the required methods.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._initialized = False

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Return list of supported models."""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider client."""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a completion for the given messages.

        Args:
            messages: List of conversation messages
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated content
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a completion for the given messages.

        Args:
            messages: List of conversation messages
            **kwargs: Additional provider-specific parameters

        Yields:
            String chunks of the response
        """
        pass

    async def complete_with_functions(
        self,
        messages: list[LLMMessage],
        functions: list[dict[str, Any]],
        function_call: str | dict[str, str] = "auto",
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate completion with function calling support.

        Args:
            messages: List of conversation messages
            functions: List of function definitions
            function_call: How to handle function calls ("auto", "none", or specific function)
            **kwargs: Additional parameters

        Returns:
            LLMResponse with potential function_call
        """
        # Default implementation - providers override if supported
        raise NotImplementedError(
            f"{self.provider_name} does not support function calling"
        )

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate completion with tool use support.

        Args:
            messages: List of conversation messages
            tools: List of tool definitions
            tool_choice: How to handle tool use
            **kwargs: Additional parameters

        Returns:
            LLMResponse with potential tool_calls
        """
        # Default implementation - providers override if supported
        raise NotImplementedError(
            f"{self.provider_name} does not support tool use"
        )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding vectors
        """
        raise NotImplementedError(
            f"{self.provider_name} does not support embeddings"
        )

    async def count_tokens(
        self,
        messages: list[LLMMessage],
    ) -> int:
        """
        Count tokens in messages.

        Args:
            messages: Messages to count tokens for

        Returns:
            Token count
        """
        # Simple estimation - providers can override with accurate counting
        total = 0
        for msg in messages:
            # Rough estimate: ~4 chars per token
            total += len(msg.content) // 4
        return total

    def validate_model(self, model: str) -> bool:
        """Check if model is supported."""
        return model in self.supported_models

    async def health_check(self) -> bool:
        """Check if provider is healthy."""
        try:
            # Simple health check via minimal completion
            response = await self.complete([
                LLMMessage(role=MessageRole.USER, content="Hi")
            ])
            return bool(response.content)
        except Exception as e:
            logger.error(
                "llm_health_check_failed",
                provider=self.provider_name,
                error=str(e),
            )
            return False

    def _log_request(
        self,
        messages: list[LLMMessage],
        model: str,
        **kwargs: Any,
    ) -> None:
        """Log LLM request."""
        logger.info(
            "llm_request",
            provider=self.provider_name,
            model=model,
            message_count=len(messages),
        )

    def _log_response(
        self,
        response: LLMResponse,
        latency_ms: float,
    ) -> None:
        """Log LLM response."""
        logger.info(
            "llm_response",
            provider=self.provider_name,
            model=response.model,
            finish_reason=response.finish_reason,
            tokens=response.usage.total_tokens if response.usage else 0,
            latency_ms=latency_ms,
        )
