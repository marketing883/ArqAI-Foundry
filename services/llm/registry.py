"""
LLM Registry

Manages LLM providers and provides a unified interface for the platform.
"""

from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from services.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
)

logger = structlog.get_logger(__name__)


class LLMRegistry:
    """
    Central registry for LLM providers.

    Features:
    - Register multiple providers
    - Select default provider
    - Route requests to appropriate provider
    - Health monitoring
    - Usage tracking
    - Fallback support
    """

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._default_provider: str | None = None
        self._model_to_provider: dict[str, str] = {}
        self._usage_stats: dict[str, dict[str, Any]] = {}

    async def register_provider(
        self,
        provider: LLMProvider,
        set_as_default: bool = False,
    ) -> bool:
        """
        Register an LLM provider.

        Args:
            provider: LLM provider instance
            set_as_default: Whether to set as default provider

        Returns:
            True if registration successful
        """
        name = provider.provider_name

        # Initialize the provider
        if not await provider.initialize():
            logger.error("provider_init_failed", provider=name)
            return False

        self._providers[name] = provider

        # Map models to provider
        for model in provider.supported_models:
            self._model_to_provider[model] = name

        # Initialize usage stats
        self._usage_stats[name] = {
            "requests": 0,
            "tokens": 0,
            "errors": 0,
            "total_latency_ms": 0,
        }

        if set_as_default or self._default_provider is None:
            self._default_provider = name

        logger.info(
            "llm_provider_registered",
            provider=name,
            models=len(provider.supported_models),
            is_default=name == self._default_provider,
        )

        return True

    def register_provider_sync(
        self,
        provider: LLMProvider,
        set_as_default: bool = False,
    ) -> None:
        """
        Register provider synchronously (deferred initialization).

        The provider will be initialized on first use.
        """
        name = provider.provider_name
        self._providers[name] = provider

        for model in provider.supported_models:
            self._model_to_provider[model] = name

        self._usage_stats[name] = {
            "requests": 0,
            "tokens": 0,
            "errors": 0,
            "total_latency_ms": 0,
        }

        if set_as_default or self._default_provider is None:
            self._default_provider = name

        logger.info("llm_provider_registered_deferred", provider=name)

    async def unregister_provider(self, name: str) -> bool:
        """Unregister a provider."""
        if name not in self._providers:
            return False

        provider = self._providers[name]

        # Remove model mappings
        self._model_to_provider = {
            m: p for m, p in self._model_to_provider.items()
            if p != name
        }

        del self._providers[name]

        # Update default if needed
        if self._default_provider == name:
            self._default_provider = (
                next(iter(self._providers.keys()), None)
            )

        logger.info("llm_provider_unregistered", provider=name)
        return True

    def set_default_provider(self, name: str) -> bool:
        """Set the default provider."""
        if name not in self._providers:
            return False
        self._default_provider = name
        logger.info("default_provider_set", provider=name)
        return True

    def get_provider(
        self,
        name: str | None = None,
        model: str | None = None,
    ) -> LLMProvider | None:
        """
        Get a provider by name or model.

        Args:
            name: Provider name
            model: Model name (will look up provider)

        Returns:
            Provider instance or None
        """
        if name:
            return self._providers.get(name)

        if model:
            provider_name = self._model_to_provider.get(model)
            if provider_name:
                return self._providers.get(provider_name)

        # Return default
        if self._default_provider:
            return self._providers.get(self._default_provider)

        return None

    def list_providers(self) -> list[str]:
        """List registered provider names."""
        return list(self._providers.keys())

    def list_models(
        self,
        provider: str | None = None,
    ) -> list[str]:
        """List available models."""
        if provider:
            p = self._providers.get(provider)
            return p.supported_models if p else []

        return list(self._model_to_provider.keys())

    # =========================================================================
    # Unified Completion Interface
    # =========================================================================

    async def complete(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate completion using appropriate provider.

        Args:
            messages: Conversation messages
            provider: Specific provider name (optional)
            model: Model to use (optional, can determine provider)
            **kwargs: Additional parameters

        Returns:
            LLM response
        """
        llm = self._resolve_provider(provider, model)

        if not llm:
            raise ValueError("No LLM provider available")

        # Ensure initialized
        if not llm._initialized:
            await llm.initialize()

        try:
            if model:
                kwargs["model"] = model

            response = await llm.complete(messages, **kwargs)

            # Track usage
            self._track_usage(llm.provider_name, response)

            return response

        except Exception as e:
            self._usage_stats[llm.provider_name]["errors"] += 1
            logger.error(
                "llm_completion_failed",
                provider=llm.provider_name,
                error=str(e),
            )
            raise

    async def stream(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream completion from appropriate provider.

        Args:
            messages: Conversation messages
            provider: Specific provider name
            model: Model to use
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        llm = self._resolve_provider(provider, model)

        if not llm:
            raise ValueError("No LLM provider available")

        if not llm._initialized:
            await llm.initialize()

        if model:
            kwargs["model"] = model

        async for chunk in llm.stream(messages, **kwargs):
            yield chunk

    async def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        provider: str | None = None,
        model: str | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate completion with tool use support.

        Args:
            messages: Conversation messages
            tools: Tool definitions
            provider: Specific provider
            model: Model to use
            tool_choice: How to handle tool selection
            **kwargs: Additional parameters

        Returns:
            LLM response (may contain tool_calls)
        """
        llm = self._resolve_provider(provider, model)

        if not llm:
            raise ValueError("No LLM provider available")

        if not llm._initialized:
            await llm.initialize()

        if model:
            kwargs["model"] = model

        return await llm.complete_with_tools(
            messages, tools, tool_choice, **kwargs
        )

    async def embed(
        self,
        texts: list[str],
        provider: str | None = None,
        model: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings.

        Args:
            texts: Texts to embed
            provider: Specific provider
            model: Embedding model

        Returns:
            List of embedding vectors
        """
        llm = self._resolve_provider(provider, model)

        if not llm:
            raise ValueError("No LLM provider available")

        if not llm._initialized:
            await llm.initialize()

        return await llm.embed(texts, model)

    # =========================================================================
    # Health & Monitoring
    # =========================================================================

    async def health_check(
        self,
        provider: str | None = None,
    ) -> dict[str, bool]:
        """
        Check health of providers.

        Args:
            provider: Specific provider to check (or all if None)

        Returns:
            Dict of provider name to health status
        """
        results = {}

        providers_to_check = (
            [self._providers[provider]] if provider
            else self._providers.values()
        )

        for p in providers_to_check:
            try:
                if not p._initialized:
                    await p.initialize()
                results[p.provider_name] = await p.health_check()
            except Exception as e:
                logger.error(
                    "health_check_failed",
                    provider=p.provider_name,
                    error=str(e),
                )
                results[p.provider_name] = False

        return results

    def get_usage_stats(
        self,
        provider: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get usage statistics."""
        if provider:
            return {provider: self._usage_stats.get(provider, {})}
        return self._usage_stats.copy()

    def reset_usage_stats(
        self,
        provider: str | None = None,
    ) -> None:
        """Reset usage statistics."""
        if provider:
            self._usage_stats[provider] = {
                "requests": 0,
                "tokens": 0,
                "errors": 0,
                "total_latency_ms": 0,
            }
        else:
            for p in self._usage_stats:
                self._usage_stats[p] = {
                    "requests": 0,
                    "tokens": 0,
                    "errors": 0,
                    "total_latency_ms": 0,
                }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _resolve_provider(
        self,
        provider: str | None,
        model: str | None,
    ) -> LLMProvider | None:
        """Resolve the provider to use."""
        # Explicit provider
        if provider:
            return self._providers.get(provider)

        # From model
        if model:
            provider_name = self._model_to_provider.get(model)
            if provider_name:
                return self._providers.get(provider_name)

        # Default
        if self._default_provider:
            return self._providers.get(self._default_provider)

        return None

    def _track_usage(
        self,
        provider_name: str,
        response: LLMResponse,
    ) -> None:
        """Track usage statistics."""
        stats = self._usage_stats.get(provider_name, {})
        stats["requests"] = stats.get("requests", 0) + 1

        if response.usage:
            stats["tokens"] = stats.get("tokens", 0) + response.usage.total_tokens

        stats["total_latency_ms"] = (
            stats.get("total_latency_ms", 0) + response.latency_ms
        )

        self._usage_stats[provider_name] = stats


# =========================================================================
# Factory Functions
# =========================================================================

def create_registry_with_providers(
    configs: list[dict[str, Any]],
    default_provider: str | None = None,
) -> LLMRegistry:
    """
    Create a registry with multiple providers from config.

    Example config:
        [
            {
                "provider": "openai",
                "api_key": "sk-...",
                "model": "gpt-4",
            },
            {
                "provider": "anthropic",
                "api_key": "sk-ant-...",
                "model": "claude-3-sonnet-20240229",
            },
            {
                "provider": "custom",
                "api_base": "http://localhost:8000/v1",
                "model": "local-model",
                "extra_params": {"openai_compatible": True},
            }
        ]
    """
    from services.llm.providers import (
        AnthropicProvider,
        AzureOpenAIProvider,
        BedrockProvider,
        CohereProvider,
        CustomProvider,
        GoogleProvider,
        MistralProvider,
        OpenAIProvider,
    )

    provider_classes = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "azure_openai": AzureOpenAIProvider,
        "bedrock": BedrockProvider,
        "cohere": CohereProvider,
        "mistral": MistralProvider,
        "custom": CustomProvider,
    }

    registry = LLMRegistry()

    for config_dict in configs:
        provider_type = config_dict.get("provider")
        provider_class = provider_classes.get(provider_type)

        if not provider_class:
            logger.warning(
                "unknown_provider_type",
                provider=provider_type,
            )
            continue

        config = LLMConfig(**config_dict)
        provider = provider_class(config)

        is_default = (
            provider_type == default_provider or
            (default_provider is None and len(registry._providers) == 0)
        )

        registry.register_provider_sync(provider, set_as_default=is_default)

    return registry
