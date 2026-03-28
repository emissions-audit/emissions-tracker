import pytest
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import Session, sessionmaker

from src.shared.models import Base


@pytest.fixture
def db_session():
    engine = create_sync_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()
