"""Application configuration settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "LessonFoundry"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./lesson_foundry.db"

    # LLM Settings
    LLM_PROVIDER: str = "mock"  # mock | openai | gemini | custom
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "gpt-4o-mini"
    LLM_API_BASE: str = "https://api.openai.com/v1"
    LLM_TIMEOUT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_api_key_configured(self) -> bool:
        """Returns True if a non-placeholder API key is set."""
        key = self.LLM_API_KEY.strip()
        return bool(key and key != "your_api_key_here")


settings = Settings()
