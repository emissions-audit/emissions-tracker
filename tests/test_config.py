from src.shared.config import Settings


def test_settings_loads_defaults():
    settings = Settings(DATABASE_URL="postgresql+asyncpg://test:test@localhost/test")
    assert settings.DATABASE_URL == "postgresql+asyncpg://test:test@localhost/test"
    assert settings.API_PAGE_SIZE_DEFAULT == 50
    assert settings.API_PAGE_SIZE_MAX == 500
    assert settings.RATE_LIMIT_FREE == 100
    assert settings.RATE_LIMIT_PRO == 1000


def test_settings_port_default():
    from src.shared.config import Settings
    s = Settings(DATABASE_URL="postgresql+asyncpg://x:x@localhost/x")
    assert s.PORT == 8000


def test_settings_port_from_env(monkeypatch):
    monkeypatch.setenv("PORT", "3000")
    from src.shared.config import Settings
    s = Settings(DATABASE_URL="postgresql+asyncpg://x:x@localhost/x")
    assert s.PORT == 3000
