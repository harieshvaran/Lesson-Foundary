"""Test Double for LLMProvider. Strictly residing inside tests/ directory."""

from typing import Any
from backend.app.llm.base import LLMProvider
from backend.app.llm.schemas import LLMResponse
from backend.app.core.exceptions import LLMTimeoutError, LLMProviderError


class TestDoubleLLMProvider(LLMProvider):
    """Test double provider used for invariant tests and offline pytest runs.
    
    NEVER importable from production code paths.
    """
    __test__ = False

    def __init__(

        self,
        canned_response: str = "Test double response",
        should_timeout: bool = False,
        should_fail: bool = False,
        error_message: str = "Forced test failure",
    ):
        self.canned_response = canned_response
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.error_message = error_message
        self.call_history: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.call_history.append({"prompt": prompt, "system_prompt": system_prompt, "settings": settings})

        if self.should_timeout:
            raise LLMTimeoutError("Test double forced timeout after 30.0s")
        if self.should_fail:
            raise LLMProviderError(f"Test double forced error: {self.error_message}")

        return LLMResponse(
            content=self.canned_response,
            raw_response={"test_double": True},
            model_id="test-double-v1",
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=1.5,
        )
