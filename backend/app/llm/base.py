"""Abstract LLM Provider interface."""

import json
import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Type, Any
from pydantic import BaseModel, ValidationError

from backend.app.llm.schemas import LLMResponse
from backend.app.core.exceptions import LLMValidationError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract interface for all model providers.
    
    All LLM calls in LessonFoundry MUST pass through an implementation of this interface.
    No direct SDK calls outside provider modules.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a text generation request against the model provider.
        
        Args:
            prompt: The main user prompt (placeholders already filled).
            system_prompt: Optional system prompt instructions.
            settings: Runtime settings (temperature, max_tokens, etc.).
            
        Returns:
            LLMResponse object containing text content and latency metadata.
            
        Raises:
            LLMTimeoutError: If the request exceeds the configured timeout.
            LLMProviderError: If the provider returns an error or network fails.
        """
        pass

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: str | None = None,
        settings: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> T:
        """Execute structured generation, enforcing Pydantic validation on the model output.
        
        Retries up to max_retries if validation fails, appending the validation error.
        
        Args:
            prompt: Main prompt.
            schema: Pydantic model class to validate output against.
            system_prompt: System prompt instructions.
            settings: Runtime parameters.
            max_retries: Maximum validation retry attempts.
            
        Returns:
            Validated instance of type T.
            
        Raises:
            LLMValidationError: If output fails validation after max_retries.
        """
        current_prompt = prompt
        last_error = None

        for attempt in range(max_retries + 1):
            response = await self.generate(
                prompt=current_prompt,
                system_prompt=system_prompt,
                settings=settings,
            )

            raw_text = response.content.strip()
            # Clean markdown code block formatting if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            try:
                parsed_json = json.loads(raw_text)
                return schema.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)
                logger.warning(
                    f"LLM output validation failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                if attempt < max_retries:
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"[SYSTEM ERROR NOTICE: Your previous output failed JSON/Pydantic validation with error: {last_error}. "
                        f"Please respond with VALID JSON matching the schema strictly.]"
                    )

        raise LLMValidationError(
            f"Failed to generate output matching schema {schema.__name__} after {max_retries + 1} attempts. Last error: {last_error}",
            details={"schema": schema.__name__, "last_error": last_error},
        )
