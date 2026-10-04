"""Hello-World execution script for Phase 0 exit criteria demonstration."""

import asyncio
from backend.app.llm.factory import get_llm_provider
from backend.app.core.exceptions import LLMProviderError, LLMTimeoutError


async def run_hello_world():
    print("--- 1. Testing Hello-World Call via LLMProvider ---")
    provider = get_llm_provider("mock")
    response = await provider.generate(prompt="Hello! Verify LLMProvider connection.")
    print(f"Provider Model ID: {response.model_id}")
    print(f"Latency: {response.latency_ms:.2f} ms")
    print(f"Output Content: {response.content}\n")

    print("--- 2. Testing Forced Provider Failure Demonstration ---")
    try:
        # Simulate a forced failure using test params
        from tests.test_double_provider import TestDoubleLLMProvider
        failing_provider = TestDoubleLLMProvider(should_fail=True, error_message="Simulated connection timeout to LLM provider")
        await failing_provider.generate(prompt="Test failure handling")
    except (LLMProviderError, LLMTimeoutError) as exc:
        print(f"SUCCESS: Caught structured exception cleanly: {exc.__class__.__name__}")
        print(f"Exception Message: {str(exc)}")
        print(f"Exception Details: {getattr(exc, 'details', {})}")


if __name__ == "__main__":
    asyncio.run(run_hello_world())
