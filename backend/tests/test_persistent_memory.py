import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.models.incident import Incident, IncidentResolution
from backend.app.schemas.incident import IncidentCreate, ResolutionCreate
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.memory_service import EpisodicMemoryService
from backend.app.services.ai_agent_service import IncidentAIAgent
from backend.app.core.algorithms import EpisodicMemoryIndex


@pytest.fixture
def isolated_db():
    """Provides a fresh, isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Test 1: Adding a verified resolution to memory
# ---------------------------------------------------------------------------
def test_add_verified_resolution_to_memory(isolated_db):
    repo = IncidentRepository(isolated_db)
    mem_service = EpisodicMemoryService()

    inc = repo.create(IncidentCreate(
        title="Postgres pool exhausted in auth",
        description="Pool saturated at 100 conns",
        service_name="auth-service",
        severity="CRITICAL",
        service_tier="TIER_1",
        impacted_users=1000,
        raw_logs="FATAL: remaining connection slots are reserved"
    ))
    res = repo.resolve(inc.id, ResolutionCreate(
        root_cause="Leaked session in token validator",
        action_taken="Used context manager and increased pool size",
        prevention_steps="Add PgBouncer pool healthcheck",
        verified_by="Staff-SRE"
    ))

    indexed = mem_service.record_resolution(
        incident_id=inc.id,
        title=inc.title,
        description=inc.description,
        service_name=inc.service_name,
        root_cause=res.root_cause,
        action_taken=res.action_taken,
        prevention_steps=res.prevention_steps,
        raw_logs=inc.raw_logs,
        verified_by=res.verified_by
    )

    assert indexed is True
    assert mem_service.count() == 1

    matches = mem_service.recall("postgres pool exhaustion in auth", top_k=1)
    assert len(matches) == 1
    assert matches[0]["incident_id"] == inc.id
    assert matches[0]["metadata"]["verified_by"] == "Staff-SRE"
    assert "PgBouncer" in matches[0]["metadata"]["caution_notes"]


# ---------------------------------------------------------------------------
# Test 2: Persistence across service recreation
# ---------------------------------------------------------------------------
def test_persistence_across_service_recreation(isolated_db):
    repo = IncidentRepository(isolated_db)
    service_a = EpisodicMemoryService()

    inc = repo.create(IncidentCreate(
        title="Redis OOM evicted all cache",
        description="Keys without TTL caused cache crash",
        service_name="redis-session-cache",
        severity="HIGH",
        service_tier="TIER_0",
        impacted_users=2500
    ))
    res = repo.resolve(inc.id, ResolutionCreate(
        root_cause="Missing TTL on session cookies",
        action_taken="Configured 24h TTL and volatile-lru",
        verified_by="Lead-Platform"
    ))

    # Rehydrate service A
    count_a = service_a.rehydrate_from_db(isolated_db)
    assert count_a == 1
    assert service_a.count() == 1

    # Recreate a completely new service instance (service B)
    service_b = EpisodicMemoryService()
    assert service_b.count() == 0  # Starts empty without hardcoded seed
    assert service_b.is_ready is False

    # Rehydrate service B from the same database
    count_b = service_b.rehydrate_from_db(isolated_db)
    assert count_b == 1
    assert service_b.count() == 1
    assert service_b.is_ready is True

    # Validate memory retrieval from recreated service B
    matches = service_b.recall("redis oom missing ttl on cookies")
    assert len(matches) >= 1
    assert matches[0]["incident_id"] == inc.id
    assert matches[0]["metadata"]["root_cause"] == res.root_cause


# ---------------------------------------------------------------------------
# Test 3: Persistence across application restart using a temporary test database
# ---------------------------------------------------------------------------
def test_persistence_across_application_restart_temp_db():
    temp_dir = tempfile.gettempdir()
    db_path = os.path.join(temp_dir, f"test_recallops_restart_{os.getpid()}.db")
    db_url = f"sqlite:///{db_path}"

    try:
        # --- Lifecycle 1: Application running, incident created & resolved ---
        engine1 = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine1)
        Session1 = sessionmaker(bind=engine1)
        session1 = Session1()

        repo1 = IncidentRepository(session1)
        inc = repo1.create(IncidentCreate(
            title="CoreDNS 504 gateway timeout",
            description="DNS queries timed out intermittently under high load",
            service_name="payment-service",
            severity="CRITICAL",
            service_tier="TIER_1",
            impacted_users=5000,
            raw_logs="dns_timeout resolving api.stripe.com"
        ))
        res = repo1.resolve(inc.id, ResolutionCreate(
            root_cause="Default ndots:5 caused redundant search domain lookups",
            action_taken="Set dnsConfig with ndots:2 and added trailing dot",
            verified_by="Kubernetes-SRE"
        ))
        inc_id = inc.id
        root_cause = res.root_cause

        session1.close()
        engine1.dispose()  # Simulates total process exit and server teardown

        # --- Lifecycle 2: Application restarted from persistent database file ---
        engine2 = create_engine(db_url, connect_args={"check_same_thread": False})
        Session2 = sessionmaker(bind=engine2)
        session2 = Session2()

        fresh_memory_service = EpisodicMemoryService()
        assert fresh_memory_service.count() == 0

        # Startup rehydration
        rehydrated_count = fresh_memory_service.rehydrate_from_db(session2)
        assert rehydrated_count == 1
        assert fresh_memory_service.count() == 1
        assert fresh_memory_service.is_ready is True

        # Query restarted service
        results = fresh_memory_service.recall("CoreDNS gateway timeout ndots", top_k=1)
        assert len(results) == 1
        assert results[0]["incident_id"] == inc_id
        assert results[0]["metadata"]["root_cause"] == root_cause

        session2.close()
        engine2.dispose()

    finally:
        # Clean up temporary database file
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Test 4: Unverified resolutions are not saved as trusted memories
# ---------------------------------------------------------------------------
def test_unverified_resolutions_not_saved_as_trusted_memories(isolated_db):
    repo = IncidentRepository(isolated_db)
    mem_service = EpisodicMemoryService()

    # 1. Open incident without resolution
    inc_open = repo.create(IncidentCreate(
        title="Unconfirmed CPU anomaly",
        description="Spike detected",
        service_name="api-gateway",
        severity="MEDIUM",
        service_tier="TIER_1"
    ))

    # 2. Attempting to record resolution without verification
    indexed = mem_service.record_resolution(
        incident_id=inc_open.id,
        title=inc_open.title,
        description=inc_open.description,
        service_name=inc_open.service_name,
        root_cause="Guessed memory leak",
        action_taken="Restarted",
        verified_by=""  # Empty/unverified
    )
    assert indexed is False
    assert mem_service.count() == 0

    indexed_none = mem_service.record_resolution(
        incident_id=inc_open.id,
        title=inc_open.title,
        description=inc_open.description,
        service_name=inc_open.service_name,
        root_cause="Guessed memory leak",
        action_taken="Restarted",
        verified_by=None  # None/unverified
    )
    assert indexed_none is False
    assert mem_service.count() == 0

    # 3. Database rehydration must also ignore any record lacking verification
    mem_service.rehydrate_from_db(isolated_db)
    assert mem_service.count() == 0


# ---------------------------------------------------------------------------
# Test 5: Duplicate resolutions do not create duplicate memories
# ---------------------------------------------------------------------------
def test_duplicate_resolutions_do_not_create_duplicate_memories(isolated_db):
    repo = IncidentRepository(isolated_db)
    mem_service = EpisodicMemoryService()

    inc = repo.create(IncidentCreate(
        title="Payment rate limit 429",
        description="Exceeded provider rate limit",
        service_name="payment-service",
        severity="HIGH",
        service_tier="TIER_1"
    ))

    res1 = ResolutionCreate(
        root_cause="Provider lowered rate limit from 500 to 150",
        action_taken="Added token bucket limiter",
        verified_by="Lead-Dev"
    )
    repo.resolve(inc.id, res1)

    # Initial indexing
    mem_service.record_resolution(
        incident_id=inc.id,
        title=inc.title,
        description=inc.description,
        service_name=inc.service_name,
        root_cause=res1.root_cause,
        action_taken=res1.action_taken,
        verified_by=res1.verified_by
    )
    assert mem_service.count() == 1

    # Update resolution on same incident (resolving again)
    res2 = ResolutionCreate(
        root_cause="Provider lowered rate limit from 500 to 150 - updated notes",
        action_taken="Added token bucket limiter with jitter",
        verified_by="Lead-Dev-2"
    )
    repo.resolve(inc.id, res2)

    # Recording updated resolution for same incident ID
    mem_service.record_resolution(
        incident_id=inc.id,
        title=inc.title,
        description=inc.description,
        service_name=inc.service_name,
        root_cause=res2.root_cause,
        action_taken=res2.action_taken,
        verified_by=res2.verified_by
    )

    # Count must remain 1, not 2
    assert mem_service.count() == 1
    assert mem_service.index.total_docs == 1

    # Search should return exactly one matching item with updated metadata
    results = mem_service.recall("payment rate limit token bucket")
    assert len(results) == 1
    assert results[0]["incident_id"] == inc.id
    assert results[0]["metadata"]["verified_by"] == "Lead-Dev-2"


# ---------------------------------------------------------------------------
# Test 6: Historical memory rehydration with multiple records
# ---------------------------------------------------------------------------
def test_historical_memory_rehydration_multiple_records(isolated_db):
    repo = IncidentRepository(isolated_db)
    mem_service = EpisodicMemoryService()

    incidents_data = [
        ("Kafka partition rebalance lag", "Consumer took too long to poll", "notification-service", "Long sync call", "Decoupled into async worker", "Data-SRE"),
        ("Postgres deadlock during checkout", "Row locks on orders table", "checkout-service", "Concurrent updates without sorted IDs", "Sorted order item IDs before locking", "DB-SRE"),
        ("Kubernetes pod OOMKilled", "Container memory exceeded 512Mi", "search-service", "Memory leak in query cache", "Fixed cache maxsize", "Platform-SRE")
    ]

    for title, desc, svc, cause, fix, verifier in incidents_data:
        inc = repo.create(IncidentCreate(
            title=title,
            description=desc,
            service_name=svc,
            severity="HIGH",
            service_tier="TIER_1"
        ))
        repo.resolve(inc.id, ResolutionCreate(
            root_cause=cause,
            action_taken=fix,
            verified_by=verifier
        ))

    count = mem_service.rehydrate_from_db(isolated_db)
    assert count == 3
    assert mem_service.count() == 3

    # Query Kafka issue
    kafka_match = mem_service.recall("kafka consumer rebalance lag", top_k=1)
    assert len(kafka_match) == 1
    assert "Kafka" in kafka_match[0]["metadata"]["title"]

    # Query Deadlock issue
    deadlock_match = mem_service.recall("postgres row lock deadlock in checkout", top_k=1)
    assert len(deadlock_match) == 1
    assert "deadlock" in deadlock_match[0]["metadata"]["title"].lower()


# ---------------------------------------------------------------------------
# Test 7: Empty memory retrieval
# ---------------------------------------------------------------------------
def test_empty_memory_retrieval():
    empty_service = EpisodicMemoryService()
    assert empty_service.count() == 0

    # Querying empty memory returns empty list without exceptions
    assert empty_service.recall("database crash") == []
    assert empty_service.recall("") == []
    assert empty_service.recall("   ") == []

    # AI agent handling of empty memory
    agent = IncidentAIAgent()
    diag = agent.diagnose(
        incident_id="INC-EMPTY-01",
        title="Unknown system failure",
        description="No historical data exists yet",
        service_name="new-service"
    )
    assert diag.historical_matches == []
    assert diag.confidence_score == 0.0
    assert "No historical matches found" in diag.hypothesized_root_cause


# ---------------------------------------------------------------------------
# Test 8: Database failure handling
# ---------------------------------------------------------------------------
def test_database_failure_handling():
    mem_service = EpisodicMemoryService()

    class FaultySession:
        def query(self, *args, **kwargs):
            raise RuntimeError("Database connection timed out or disk I/O error")

    faulty_db = FaultySession()

    with pytest.raises(RuntimeError):
        mem_service.rehydrate_from_db(faulty_db)

    # Service state must indicate failure and not falsely claim it is ready
    assert mem_service.is_ready is False
    assert mem_service.last_error is not None
    assert "Database connection timed out" in mem_service.last_error
