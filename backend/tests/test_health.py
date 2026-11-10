import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import root, seed_initial_demo_incidents
from backend.app.api.v1.endpoints.health import health_check
from backend.app.db.base import Base
from backend.app.services.memory_service import memory_service

test_health_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestHealthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_health_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_health_db():
    Base.metadata.create_all(bind=test_health_engine)
    db = TestHealthSessionLocal()
    try:
        seed_initial_demo_incidents(db)
        memory_service.rehydrate_from_db(db)
    finally:
        db.close()
    yield


def test_root_endpoint():
    data = root()
    assert data["system"] == "RecallOps-AI"
    assert "version" in data
    assert data["documentation"] == "/docs"


def test_health_endpoint():
    data = health_check()
    assert data.status == "healthy"
    assert data.project == "RecallOps-AI"
    assert data.indexed_memories >= 5
    assert data.services_in_graph >= 10
