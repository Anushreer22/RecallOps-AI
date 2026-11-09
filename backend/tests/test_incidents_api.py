import pytest
from backend.app.db.session import SessionLocal, engine
from backend.app.db.base import Base
from backend.app.schemas.incident import (
    IncidentCreate,
    WebhookAlertPayload,
    ResolutionCreate
)
from backend.app.api.v1.endpoints.incidents import (
    create_incident,
    ingest_webhook_alert,
    get_triage_queue,
    get_incident,
    diagnose_incident,
    resolve_incident,
    get_blast_radius,
    search_episodic_memory
)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_create_incident_flow(db_session):
    payload = IncidentCreate(
        title="Kafka partition lag in notification-service",
        description="Email queue processing is stalled with 50,000 lag count.",
        service_name="notification-service",
        severity="HIGH",
        service_tier="TIER_2",
        impacted_users=1500,
        raw_logs="org.apache.kafka.clients.consumer.CommitFailedException",
        source="Datadog"
    )
    incident = create_incident(payload, db_session)
    assert incident.id.startswith("INC-")
    assert incident.title == payload.title
    assert incident.status == "OPEN"


def test_webhook_alert_ingestion(db_session):
    webhook_data = WebhookAlertPayload(
        event_type="alert.triggered",
        alert_name="DatabasePoolExhausted",
        service="auth-service",
        severity="CRITICAL",
        tier="TIER_1",
        details="Connection count at 100% capacity",
        impacted_users=5000,
        logs="FATAL: remaining connection slots are reserved for non-replication superuser connections"
    )
    incident = ingest_webhook_alert(webhook_data, db_session)
    assert "auth-service" in incident.title
    assert incident.severity == "CRITICAL"


def test_triage_queue_endpoint():
    queue = get_triage_queue()
    assert isinstance(queue, list)
    assert len(queue) >= 1
    # Check that items are sorted descending by calculated multivariate score
    if len(queue) > 1:
        assert queue[0]["score"] >= queue[1]["score"]


def test_diagnose_incident_with_memory_recall(db_session):
    # 1. Ingest incident matching seeded episodic memory (CoreDNS)
    payload = IncidentCreate(
        title="Payment gateway coredns resolution timeout",
        description="DNS queries to payment provider timed out intermittently.",
        service_name="payment-service",
        severity="CRITICAL",
        service_tier="TIER_1",
        impacted_users=2000,
        raw_logs="dns_timeout in CoreDNS pod [ERR_504] gateway error",
        source="Prometheus"
    )
    incident = create_incident(payload, db_session)

    # 2. Diagnose incident
    diag = diagnose_incident(incident.id, db_session)
    assert diag.incident_id == incident.id
    assert len(diag.detected_signatures) >= 1
    assert diag.confidence_score > 0.6
    assert len(diag.recommended_runbook_steps) > 0
    # Blast radius traversal should trace downstream impact from payment-service
    assert diag.blast_radius.origin_service == "payment-service"
    assert diag.blast_radius.total_impacted_services >= 1


def test_resolve_incident_and_memory_feedback_loop(db_session):
    # 1. Create active incident
    payload = IncidentCreate(
        title="Severe connection pool leak under heavy checkout traffic",
        description="Postgres connection count saturated at max limit.",
        service_name="auth-service",
        severity="HIGH",
        service_tier="TIER_1",
        impacted_users=800
    )
    incident = create_incident(payload, db_session)

    # 2. Resolve incident
    resolution_in = ResolutionCreate(
        root_cause="Unbounded connection acquisition in token auth middleware without close.",
        action_taken="Wrapped DB sessions in context manager and tuned PgBouncer pool.",
        prevention_steps="Configured automated pool alert when connections exceed 80%.",
        verified_by="Lead-SRE"
    )
    resolution = resolve_incident(incident.id, resolution_in, db_session)
    assert resolution.root_cause == resolution_in.root_cause

    # 3. Verify status changed to RESOLVED
    fetched = get_incident(incident.id, db_session)
    assert fetched.status == "RESOLVED"

    # 4. Search episodic memory and verify the newly verified resolution is recalled
    matches = search_episodic_memory(q="Unbounded connection acquisition in token auth middleware", limit=3)
    assert len(matches) > 0


def test_topology_blast_radius_endpoint():
    blast = get_blast_radius(service="user-db")
    assert blast.origin_service == "user-db"
    # user-db is Tier 0: auth-service, payment-service, inventory-service, api-gateway depend on it
    impacted_services = [s["service"] for s in blast.impacted_services]
    assert "auth-service" in impacted_services or "payment-service" in impacted_services
