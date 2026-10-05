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

    # Guardrail Thresholds
    GUARDRAIL_DUP_JACCARD_THRESHOLD: float = 0.70
    GUARDRAIL_ANSWER_LEAKAGE_MIN_WORDS: int = 3
    GUARDRAIL_CLAIM_OVERLAP_MIN_THRESHOLD: float = 0.20
    GUARDRAIL_ENABLE_LLM_ENTAILMENT: bool = True
    GUARDRAIL_MIN_OBJ_COVERAGE_RATIO: float = 0.15
    GUARDRAIL_OBJ_IMBALANCE_STD_DEV_MULTIPLIER: float = 0.50
    GUARDRAIL_EASY_BLOOM_MAX_RANK: int = 2
    GUARDRAIL_ADVANCED_BLOOM_MIN_RANK: int = 3

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
