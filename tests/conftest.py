import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - register every ORM table
from app.models.base import Base
from factories import acceptance_environment, operational_environment


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def acceptance_data(db_session):
    return acceptance_environment(db_session)


@pytest.fixture()
def operational_data(db_session, acceptance_data):
    return operational_environment(db_session, acceptance_data)
