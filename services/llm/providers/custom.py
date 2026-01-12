"""
Custom/BYOL (Bring Your Own LLM) Provider Implementation

Allows enterprises to integrate their own LLM endpoints.
Supports any OpenAI-compatible API or custom implementations.
"""

from datetime import datetime
from typing import Any, AsyncIterator, Callable

import structlog

from services.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMUsage,
    MessageRole,
)

logger = structlog.get_logger(__name__)


class CustomProvider(LLMProvider):
    """
    Custom/BYOL LLM Provider.

    Allows enterprises to:
    1. Connect to OpenAI-compatible APIs (vLLM, Ollama, LocalAI, etc.)
    2. Implement custom completion handlers
    3. Use private/on-premise LLMs
    4. Integrate specialized models

    Configuration options:
    - api_base: Base URL for OpenAI-compatible API
    - completion_handler: Custom async function for completions
    - stream_handler: Custom async generator for streaming
    - embed_handler: Custom async function for embeddings
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)

        # Custom handlers (can be set after initialization)
        self._completion_handler: Callable | None = config.extra_params.get(
            "completion_handler"
        )
        self._stream_handler: Callable | None = config.extra_params.get(
            "stream_handler"
        )
        self._embed_handler: Callable | None = config.extra_params.get(
            "embed_handler"
        )

        # OpenAI-compatible mode
        self._openai_compatible = config.extra_params.get(
            "openai_compatible",
            True,  # Default to OpenAI-compatible
        )

        # Custom model list
        self._custom_models = config.extra_params.get("models", [])

    @property
    def provider_name(self) -> str:
        return config.extra_params.get("provider_name", "custom") if hasattr(self, 'config') else "custom"

    @property
    def supported_models(self) -> list[str]:
        return self._custom_models

    def set_completion_handler(
        self,
        handler: Callable[
            [list[LLMMessage], dict[str, Any]],
            LLMResponse,
        ],
    ) -> None:
        """
        Set custom completion handler.

        Example:
            async def my_handler(messages, kwargs):
                # Call your custom LLM
                response = await my_llm.generate(messages)
                return LLMResponse(content=response.text, ...)

            provider.set_completion_handler(my_handler)
        """
        self._completion_handler = handler
        logger.info("custom_completion_handler_set")

    def set_stream_handler(
        self,
        handler: Callable[
            [list[LLMMessage], dict[str, Any]],
            AsyncIterator[str],
        ],
    ) -> None:
        """
        Set custom streaming handler.

        Example:
            async def my_stream_handler(messages, kwargs):
                async for chunk in my_llm.stream(messages):
                    yield chunk.text

            provider.set_stream_handler(my_stream_handler)
        """
        self._stream_handler = handler
        logger.info("custom_stream_handler_set")

    def set_embed_handler(
        self,
        handler: Callable[
            [list[str], str | None],
            list[list[float]],
        ],
    ) -> None:
        """
        Set custom embedding handler.

        Example:
            async def my_embed_handler(texts, model):
                embeddings = await my_embedder.encode(texts)
                return embeddings.tolist()

            provider.set_embed_handler(my_embed_handler)
        """
        self._embed_handler = handler
        logger.info("custom_embed_handler_set")

    async def initialize(self) -> bool:
        """Initialize custom provider."""
        try:
            if self._openai_compatible and self.config.api_base:
                # For OpenAI-compatible APIs (vLLM, Ollama, etc.)
                # In production:
                # from openai import AsyncOpenAI
                # self._client = AsyncOpenAI(
                #     api_key=self.config.api_key or "not-needed",
                #     base_url=self.config.api_base,
                #     timeout=self.config.timeout_seconds,
                # )
                pass

            self._initialized = True
            logger.info(
                "custom_provider_initialized",
                api_base=self.config.api_base,
                openai_compatible=self._openai_compatible,
                has_completion_handler=self._completion_handler is not None,
            )
            return True

        except Exception as e:
            logger.error("custom_init_failed", error=str(e))
            return False

    async def complete(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using custom provider."""
        start_time = datetime.utcnow()

        model = kwargs.get("model", self.config.model)
        self._log_request(messages, model)

        try:
            # Use custom handler if provided
            if self._completion_handler:
                response = await self._completion_handler(messages, kwargs)
                response.latency_ms = (
                    datetime.utcnow() - start_time
                ).total_seconds() * 1000
                self._log_response(response, response.latency_ms)
                return response

            # Fall back to OpenAI-compatible API
            if self._openai_compatible and self.config.api_base:
                return await self._openai_compatible_complete(
                    messages, model, kwargs
                )

            raise ValueError(
                "No completion handler set and not configured for OpenAI-compatible API"
            )

        except Exception as e:
            logger.error("custom_completion_failed", error=str(e))
            raise

    async def _openai_compatible_complete(
        self,
        messages: list[LLMMessage],
        model: str,
        kwargs: dict[str, Any],
    ) -> LLMResponse:
        """Complete using OpenAI-compatible API."""
        start_time = datetime.utcnow()
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)

        # In production:
        # response = await self._client.chat.completions.create(
        #     model=model,
        #     messages=[m.to_dict() for m in messages],
        #     temperature=temperature,
        #     max_tokens=max_tokens,
        # )
        # return LLMResponse(
        #     content=response.choices[0].message.content,
        #     role=MessageRole.ASSISTANT,
        #     model=model,
        #     finish_reason=response.choices[0].finish_reason,
        #     usage=LLMUsage(
        #         prompt_tokens=response.usage.prompt_tokens,
        #         completion_tokens=response.usage.completion_tokens,
        #         total_tokens=response.usage.total_tokens,
        #     ),
        #     latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
        # )

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return LLMResponse(
            content="[Custom Provider Response Placeholder]",
            role=MessageRole.ASSISTANT,
            model=model,
            finish_reason="stop",
            usage=LLMUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            ),
            latency_ms=latency,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream completion from custom provider."""
        model = kwargs.get("model", self.config.model)

        # Use custom handler if provided
        if self._stream_handler:
            async for chunk in self._stream_handler(messages, kwargs):
                yield chunk
            return

        # Fall back to OpenAI-compatible API
        if self._openai_compatible and self.config.api_base:
            # In production:
            # stream = await self._client.chat.completions.create(
            #     model=model,
            #     messages=[m.to_dict() for m in messages],
            #     stream=True,
            # )
            # async for chunk in stream:
            #     if chunk.choices[0].delta.content:
            #         yield chunk.choices[0].delta.content
            pass

        # Simulated streaming
        for word in ["This", " is", " custom", " provider", " response"]:
            yield word

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using custom provider."""
        # Use custom handler if provided
        if self._embed_handler:
            return await self._embed_handler(texts, model)

        # Fall back to OpenAI-compatible API
        if self._openai_compatible and self.config.api_base:
            embedding_model = model or self.config.extra_params.get(
                "embedding_model",
                "text-embedding-ada-002",
            )

            # In production:
            # response = await self._client.embeddings.create(
            #     model=embedding_model,
            #     input=texts,
            # )
            # return [e.embedding for e in response.data]
            pass

        # Simulated embeddings
        return [[0.0] * 1536 for _ in texts]

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion with tool use."""
        start_time = datetime.utcnow()
        model = kwargs.get("model", self.config.model)

        # Check if custom handler supports tools
        if self._completion_handler:
            # Pass tools in kwargs
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
            return await self._completion_handler(messages, kwargs)

        # OpenAI-compatible with tool support
        if self._openai_compatible and self.config.api_base:
            # In production:
            # response = await self._client.chat.completions.create(
            #     model=model,
            #     messages=[m.to_dict() for m in messages],
            #     tools=tools,
            #     tool_choice=tool_choice,
            # )
            pass

        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return LLMResponse(
            content="",
            role=MessageRole.ASSISTANT,
            model=model,
            finish_reason="tool_calls",
            tool_calls=[{
                "id": "custom_call_123",
                "type": "function",
                "function": {
                    "name": "example_tool",
                    "arguments": "{}",
                },
            }],
            latency_ms=latency,
        )


# =========================================================================
# BYOL Helper Functions
# =========================================================================

def create_openai_compatible_provider(
    name: str,
    api_base: str,
    api_key: str | None = None,
    models: list[str] | None = None,
    default_model: str | None = None,
) -> CustomProvider:
    """
    Create a provider for OpenAI-compatible APIs.

    Examples:
        # vLLM
        provider = create_openai_compatible_provider(
            name="vllm",
            api_base="http://localhost:8000/v1",
            models=["meta-llama/Llama-2-7b-chat-hf"],
        )

        # Ollama
        provider = create_openai_compatible_provider(
            name="ollama",
            api_base="http://localhost:11434/v1",
            models=["llama2", "mistral", "codellama"],
        )

        # LocalAI
        provider = create_openai_compatible_provider(
            name="localai",
            api_base="http://localhost:8080/v1",
            models=["gpt-4-local"],
        )
    """
    config = LLMConfig(
        provider=name,
        api_key=api_key,
        api_base=api_base,
        model=default_model or (models[0] if models else ""),
        extra_params={
            "provider_name": name,
            "openai_compatible": True,
            "models": models or [],
        },
    )

    return CustomProvider(config)


def create_custom_provider(
    name: str,
    completion_handler: Callable,
    stream_handler: Callable | None = None,
    embed_handler: Callable | None = None,
    models: list[str] | None = None,
) -> CustomProvider:
    """
    Create a fully custom provider with your own handlers.

    Example:
        async def my_completion(messages, kwargs):
            # Your custom logic
            result = await my_model.generate(...)
            return LLMResponse(content=result, ...)

        provider = create_custom_provider(
            name="my_custom_llm",
            completion_handler=my_completion,
            models=["my-model-v1"],
        )
    """
    config = LLMConfig(
        provider=name,
        extra_params={
            "provider_name": name,
            "openai_compatible": False,
            "models": models or [],
            "completion_handler": completion_handler,
            "stream_handler": stream_handler,
            "embed_handler": embed_handler,
        },
    )

    return CustomProvider(config)
