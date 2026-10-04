"""Mock LLM Provider for local development and deterministic execution."""

import time
from typing import Any
from backend.app.llm.base import LLMProvider
from backend.app.llm.schemas import LLMResponse


class MockLLMProvider(LLMProvider):
    """Production mock provider used when LLM_PROVIDER=mock in development."""

    def __init__(self, model_id: str = "mock-v1", latency_ms: float = 10.0):
        self.model_id = model_id
        self.latency_ms = latency_ms

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> LLMResponse:
        start_time = time.perf_counter()

        # Simple keyword matching for mock responses
        if "hello" in prompt.lower() or "ping" in prompt.lower():
            content = "Hello! LessonFoundry LLM Provider is operational."
        elif "gap" in prompt.lower():
            content = '{"objective_id": "O1", "status": "supported", "evidence_chunk_ids": ["S1", "S2"], "missing_concepts": [], "reason": "Chunks S1 and S2 cover inputs and outputs."}'
        else:
            content = '{"status": "ok", "message": "Mock provider response", "prompt_summary": "' + prompt[:50] + '"}'

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0 + self.latency_ms

        return LLMResponse(
            content=content,
            raw_response={"mock": True, "prompt": prompt},
            model_id=self.model_id,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(content.split()),
            latency_ms=elapsed_ms,
        )
