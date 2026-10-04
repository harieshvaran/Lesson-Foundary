"""Pydantic schemas for LLM provider input, output, and usage metadata."""

from typing import Any
from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Standard response object returned by all LLMProvider instances."""
    content: str = Field(..., description="Raw text response content from the model")
    raw_response: dict[str, Any] | str = Field(default_factory=dict, description="Raw provider API payload")
    model_id: str = Field(..., description="Model identifier used for generation")
    prompt_tokens: int = Field(default=0, description="Tokens used in prompt")
    completion_tokens: int = Field(default=0, description="Tokens generated in output")
    latency_ms: float = Field(default=0.0, description="Execution latency in milliseconds")
