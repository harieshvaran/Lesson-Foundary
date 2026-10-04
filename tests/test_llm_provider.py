"""Tests for LLMProvider implementations, hello-world generation, and forced failures."""

import pytest
from pydantic import BaseModel
from backend.app.llm.factory import get_llm_provider
from backend.app.llm.providers.mock_provider import MockLLMProvider
from backend.app.llm.providers.concrete_provider import ConcreteLLMProvider
from backend.app.core.exceptions import (
    LLMProviderError,
    LLMTimeoutError,
    LLMConfigurationError,
    LLMValidationError,
)
from tests.test_double_provider import TestDoubleLLMProvider


class SampleGapOutput(BaseModel):
    objective_id: str
    status: str
    evidence_chunk_ids: list[str]


@pytest.mark.asyncio
async def test_llm_provider_hello_world():
    """Verify Hello-World prompt call succeeds through LLMProvider interface."""
    provider = get_llm_provider("mock")
    response = await provider.generate(prompt="Hello! Test call.")

    assert response is not None
    assert response.content != ""
    assert "LessonFoundry LLM Provider is operational" in response.content
    assert response.model_id is not None
    assert response.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_llm_provider_generate_structured():
    """Verify structured output parsing and Pydantic validation."""
    provider = get_llm_provider("mock")
    result = await provider.generate_structured(
        prompt="Perform gap check for objective O1",
        schema=SampleGapOutput,
    )

    assert result.objective_id == "O1"
    assert result.status == "supported"
    assert result.evidence_chunk_ids == ["S1", "S2"]


@pytest.mark.asyncio
async def test_forced_provider_timeout_demonstration():
    """Demonstrate clean handling of provider timeout error."""
    provider = TestDoubleLLMProvider(should_timeout=True)

    with pytest.raises(LLMTimeoutError) as exc_info:
        await provider.generate(prompt="Test timeout")

    assert "forced timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_forced_provider_failure_demonstration():
    """Demonstrate clean handling of network / provider API failure."""
    provider = TestDoubleLLMProvider(should_fail=True, error_message="API connection refused")

    with pytest.raises(LLMProviderError) as exc_info:
        await provider.generate(prompt="Test failure")

    assert "API connection refused" in str(exc_info.value)


@pytest.mark.asyncio
async def test_concrete_provider_missing_api_key():
    """Verify ConcreteLLMProvider raises LLMConfigurationError if key is invalid/missing."""
    with pytest.raises(LLMConfigurationError) as exc_info:
        ConcreteLLMProvider(api_key="", model_name="gpt-4o-mini")

    assert "API key is missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_structured_validation_retry_failure():
    """Verify invalid JSON causes LLMValidationError after bounded retries."""
    provider = TestDoubleLLMProvider(canned_response="Invalid non-json response text")

    with pytest.raises(LLMValidationError) as exc_info:
        await provider.generate_structured(
            prompt="Generate gap output",
            schema=SampleGapOutput,
            max_retries=1,
        )

    assert "Failed to generate output matching schema" in str(exc_info.value)
