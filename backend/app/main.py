from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import engine, SessionLocal
from backend.app.api.v1.router import api_router
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import IncidentCreate, ResolutionCreate
from backend.app.services.triage_service import triage_service
from backend.app.services.memory_service import memory_service


def seed_initial_demo_incidents(db):
    """Seeds demonstration historical resolved incidents and an active alert if database is empty."""
    repo = IncidentRepository(db)
    existing = repo.list_all(limit=1)
    if not existing:
        # 1. Seed historical verified outages into database
        historical_seeds = [
            (
                IncidentCreate(
                    title="Database connection pool saturated in auth-service",
                    description="PostgreSQL connection pool exhaustion under high traffic load in auth-service. Error: remaining connection slots are reserved. Callers received 500 internal server errors.",
                    service_name="auth-service",
                    severity="CRITICAL",
                    service_tier="TIER_1",
                    impacted_users=4500,
                    raw_logs="FATAL: remaining connection slots are reserved for non-replication superuser connections\n[ERR_503] service unavailable",
                    source="Historical"
                ),
                ResolutionCreate(
                    root_cause="Unclosed SQLAlchemy db sessions in JWT verification middleware led to idle connection leak.",
                    action_taken="Applied context manager 'with get_db() as db' and configured PgBouncer connection pooler with max_client_conn=500.",
                    prevention_steps="Do not simply increase max_connections on Postgres without PgBouncer, as it will cause OOM on the database primary.",
                    verified_by="Principal-SRE"
                ),
                "HIST-001"
            ),
            (
                IncidentCreate(
                    title="Redis out-of-memory cache eviction collapse",
                    description="Redis OOM command not allowed when used memory > maxmemory. Session cache eviction storm caused high database CPU spike.",
                    service_name="redis-session-cache",
                    severity="HIGH",
                    service_tier="TIER_0",
                    impacted_users=2800,
                    raw_logs="OOM command not allowed when used memory > maxmemory",
                    source="Historical"
                ),
                ResolutionCreate(
                    root_cause="User sessions created without an explicit TTL, accumulating stale session keys indefinitely until memory saturated.",
                    action_taken="Configured maxmemory-policy volatile-lru, applied default 24h TTL on all session keys, and flushed expired keys via cron.",
                    prevention_steps="Do not use 'KEYS *' to debug Redis memory in production, use 'SCAN' with count limit.",
                    verified_by="Platform-Lead"
                ),
                "HIST-002"
            ),
            (
                IncidentCreate(
                    title="CoreDNS timeout during external API resolution",
                    description="Kubernetes CoreDNS resolution timeout 504 gateway error in payment-service. Upstream external payment provider DNS queries failing intermittently.",
                    service_name="payment-service",
                    severity="CRITICAL",
                    service_tier="TIER_1",
                    impacted_users=3100,
                    raw_logs="dns_timeout in CoreDNS pod [ERR_504] gateway error",
                    source="Historical"
                ),
                ResolutionCreate(
                    root_cause="Default k8s resolv.conf ndots:5 caused 5 internal domain lookups before querying public DNS, causing CoreDNS query spikes and timeouts.",
                    action_taken="Appended trailing dot '.' to external API hostnames and set dnsConfig with ndots:2 and single-request-reopen.",
                    prevention_steps="Restarting CoreDNS pods only provides temporary relief; dnsConfig is the permanent solution.",
                    verified_by="Infra-SRE"
                ),
                "HIST-003"
            ),
            (
                IncidentCreate(
                    title="Third-party payment provider rate limit throttle",
                    description="Checkout payment gateway HTTP 429 Too Many Requests rate limit breach. Payment provider blocked checkout transactions for 15 minutes.",
                    service_name="payment-service",
                    severity="HIGH",
                    service_tier="TIER_1",
                    impacted_users=1900,
                    raw_logs="HTTP 429 Too Many Requests from api.stripe.com",
                    source="Historical"
                ),
                ResolutionCreate(
                    root_cause="Payment provider lowered API rate limit from 500 req/sec to 150 req/sec without prior deprecation notice.",
                    action_taken="Implemented client-side token bucket rate limiter with jittered exponential backoff and graceful request queueing.",
                    prevention_steps="Do not retry failed 429 requests immediately; it exacerbates provider throttling.",
                    verified_by="Payments-Lead"
                ),
                "HIST-004"
            ),
            (
                IncidentCreate(
                    title="Kafka partition rebalancing storm",
                    description="Kafka consumer group partition rebalance storm causing extreme message processing lag in notification-service.",
                    service_name="notification-service",
                    severity="HIGH",
                    service_tier="TIER_2",
                    impacted_users=1200,
                    raw_logs="org.apache.kafka.clients.consumer.CommitFailedException",
                    source="Historical"
                ),
                ResolutionCreate(
                    root_cause="Synchronous email delivery exceeded max.poll.interval.ms (300s), causing broker to consider consumer dead and trigger rebalances.",
                    action_taken="Decoupled message consumption from processing via internal async worker threadpool and increased max.poll.interval.ms to 600s.",
                    prevention_steps="Avoid long synchronous network calls directly inside the Kafka message poll loop.",
                    verified_by="Data-Platform-SRE"
                ),
                "HIST-005"
            )
        ]

        for inc_create, res_create, hist_id in historical_seeds:
            created = repo.create(inc_create, incident_id=hist_id)
            repo.resolve(created.id, res_create)

        # 2. Seed active demo incident into priority queue
        demo_incident = IncidentCreate(
            title="Postgres connection pool exhausted in auth-service",
            description="Database connections exceeded 100 max limit. API gateway returning HTTP 500.",
            service_name="auth-service",
            severity="CRITICAL",
            service_tier="TIER_1",
            impacted_users=3200,
            raw_logs="FATAL: remaining connection slots are reserved for non-replication superuser connections\n[ERR_503] service unavailable",
            source="PagerDuty:AlertManager"
        )
        created_demo = repo.create(demo_incident, incident_id="INC-DEMO-01")
        triage_service.enqueue(
            incident_id=created_demo.id,
            title=created_demo.title,
            severity=created_demo.severity,
            service_tier=created_demo.service_tier,
            impacted_users=created_demo.impacted_users
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize database state and rehydrate episodic memory from verified database records
    db = SessionLocal()
    try:
        seed_initial_demo_incidents(db)
        memory_service.rehydrate_from_db(db)
    except Exception as exc:
        memory_service.is_ready = False
        memory_service.last_error = str(exc)
    finally:
        db.close()

    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "RecallOps-AI: Incident Response & Operational Memory System.\n\n"
        "Engineered with Core Concepts: Data Structures & Algorithms (Vector Cosine Similarity, Max-Heap Priority Triage, "
        "Dependency DAG Blast Radius, Log Signature Trie), API Integration, Prototyping, Testing, and Technical Documentation."
    ),
    lifespan=lifespan
)

# CORS setup for frontend dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "documentation": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
