"""Concrete HTTP LLM Provider for OpenAI / Gemini / OpenAI-compatible APIs."""

import time
import httpx
from typing import Any
from backend.app.llm.base import LLMProvider
from backend.app.llm.schemas import LLMResponse
from backend.app.core.exceptions import (
    LLMProviderError,
    LLMTimeoutError,
    LLMConfigurationError,
)


class ConcreteLLMProvider(LLMProvider):
    """Concrete LLM Provider using httpx to call OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        api_base: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ):
        if not api_key or api_key == "your_api_key_here":
            raise LLMConfigurationError(
                "API key is missing or set to placeholder. Please configure LLM_API_KEY in server-side .env"
            )

        self.api_key = api_key
        self.model_name = model_name
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> LLMResponse:
        settings = settings or {}
        temperature = settings.get("temperature", 0.3)
        max_tokens = settings.get("max_tokens", 2000)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.api_base}/chat/completions"
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                if response.status_code != 200:
                    error_detail = response.text
                    raise LLMProviderError(
                        f"LLM Provider API returned status {response.status_code}: {error_detail}",
                        details={"status_code": response.status_code, "raw_response": error_detail},
                    )

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMProviderError("LLM Provider returned empty choices array.")

                content = choices[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    raw_response=data,
                    model_id=data.get("model", self.model_name),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    latency_ms=elapsed_ms,
                )

        except httpx.TimeoutException as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            raise LLMTimeoutError(
                f"LLM request timed out after {self.timeout_seconds} seconds.",
                details={"timeout_seconds": self.timeout_seconds, "latency_ms": elapsed_ms},
            ) from e
        except httpx.RequestError as e:
            raise LLMProviderError(
                f"Network request to LLM provider failed: {str(e)}",
                details={"error": str(e)},
            ) from e
