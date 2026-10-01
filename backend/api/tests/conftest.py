from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


# ============================================================
# PROJECT ROOT CONFIGURATION
# ============================================================

BACKEND_ROOT = Path(__file__).resolve().parents[2]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ============================================================
# REGISTER MODULE-SPECIFIC FIXTURES
# ============================================================

pytest_plugins = (
    "api.tests.fixtures.party_fixtures",
    "api.tests.fixtures.customer_fixtures",
)


# ============================================================
# APPLICATION IMPORTS
# ============================================================

from api.config.database import Base
from api.dependencies.dependencies import get_db

from api.router.party import router as party_router
from api.router.customer import router as customer_router

# These imports register the models in Base.metadata.
from api.model.party import Party  # noqa: F401, E402
from api.model.customer import Customer  # noqa: F401, E402


# ============================================================
# TEST DATABASE CONFIGURATION
# ============================================================

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture
def test_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        dbapi_connection,
        connection_record,
    ) -> None:
        del connection_record

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    try:
        yield engine

    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ============================================================
# TEST SESSION FACTORY
# ============================================================

@pytest.fixture
def test_session_factory(
    test_engine: Engine,
):
    return sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


# ============================================================
# DIRECT DATABASE SESSION FIXTURE
# ============================================================

@pytest.fixture
def db_session(
    test_session_factory,
) -> Generator[Session, None, None]:
    session = test_session_factory()

    try:
        yield session

    finally:
        session.rollback()
        session.close()


# ============================================================
# TEST FASTAPI APPLICATION
# ============================================================

@pytest.fixture
def test_app(
    test_session_factory,
) -> Generator[FastAPI, None, None]:
    application = FastAPI(
        title="Billing System Test API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    application.include_router(party_router)
    application.include_router(customer_router)

    def override_get_db() -> Generator[Session, None, None]:
        session = test_session_factory()

        try:
            yield session

        finally:
            session.rollback()
            session.close()

    application.dependency_overrides[get_db] = override_get_db

    @application.get("/test-health")
    def test_health() -> dict[str, str]:
        return {
            "status": "ok",
            "database": "sqlite-memory",
        }

    try:
        yield application

    finally:
        application.dependency_overrides.clear()


# ============================================================
# FASTAPI TEST CLIENT
# ============================================================

@pytest.fixture
def client(
    test_app: FastAPI,
) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as test_client:
        yield test_client