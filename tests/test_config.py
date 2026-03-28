from src.shared.config import Settings


def test_settings_loads_defaults():
    settings = Settings(DATABASE_URL="postgresql+asyncpg://test:test@localhost/test")
    assert settings.DATABASE_URL == "postgresql+asyncpg://test:test@localhost/test"
    assert settings.API_PAGE_SIZE_DEFAULT == 50
    assert settings.API_PAGE_SIZE_MAX == 500
    assert settings.RATE_LIMIT_FREE == 100
    assert settings.RATE_LIMIT_PRO == 1000
