from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    ANTHROPIC_API_KEY: str = ""
    PORT: int = 8000

    API_PAGE_SIZE_DEFAULT: int = 50
    API_PAGE_SIZE_MAX: int = 500

    RATE_LIMIT_FREE: int = 100
    RATE_LIMIT_PRO: int = 1000

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _fix_database_url(self) -> "Settings":
        """Railway provides postgresql:// but asyncpg needs postgresql+asyncpg://."""
        if self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self


def get_settings() -> Settings:
    return Settings()
