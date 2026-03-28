from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    ANTHROPIC_API_KEY: str = ""

    API_PAGE_SIZE_DEFAULT: int = 50
    API_PAGE_SIZE_MAX: int = 500

    RATE_LIMIT_FREE: int = 100
    RATE_LIMIT_PRO: int = 1000

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
