from backend.app.main import root
from backend.app.api.v1.endpoints.health import health_check


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
