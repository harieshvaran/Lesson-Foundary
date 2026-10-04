"""Factory function for instantiating configured LLMProvider."""

from backend.app.core.config import settings
from backend.app.llm.base import LLMProvider
from backend.app.llm.providers.mock_provider import MockLLMProvider
from backend.app.llm.providers.concrete_provider import ConcreteLLMProvider


def get_llm_provider(
    provider_type: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    timeout_seconds: float | None = None,
) -> LLMProvider:
    """Instantiate and return the configured LLMProvider implementation.
    
    Defaults to settings loaded from .env file.
    """
    provider_name = (provider_type or settings.LLM_PROVIDER).lower()
    key = api_key if api_key is not None else settings.LLM_API_KEY
    model = model_name or settings.LLM_MODEL_NAME
    timeout = timeout_seconds or settings.LLM_TIMEOUT_SECONDS

    if provider_name == "mock":
        return MockLLMProvider(model_id=model)
    elif provider_name in ("openai", "concrete", "httpx"):
        return ConcreteLLMProvider(
            api_key=key,
            model_name=model,
            api_base=settings.LLM_API_BASE,
            timeout_seconds=timeout,
        )
    else:
        # Default fallback to MockLLMProvider for unknown types
        return MockLLMProvider(model_id=model)
