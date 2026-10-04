"""Custom exception definitions for LessonFoundry."""

class LessonFoundryException(Exception):
    """Base exception for all LessonFoundry errors."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LLMProviderError(LessonFoundryException):
    """Raised when an LLM provider operation fails."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM provider request times out."""
    pass


class LLMValidationError(LLMProviderError):
    """Raised when LLM output fails schema validation after retries."""
    pass


class LLMConfigurationError(LLMProviderError):
    """Raised when LLM provider configuration or API key is missing/invalid."""
    pass


class DatabaseError(LessonFoundryException):
    """Raised when database operational issues occur."""
    pass
