from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import engine, SessionLocal
from backend.app.api.v1.router import api_router
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import IncidentCreate
from backend.app.services.triage_service import triage_service


def seed_initial_demo_incidents():
    """Seeds a demonstration active incident on first run if database is empty."""
    db = SessionLocal()
    try:
        repo = IncidentRepository(db)
        existing = repo.list_all(limit=1)
        if not existing:
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
            created = repo.create(demo_incident, incident_id="INC-DEMO-01")
            triage_service.enqueue(
                incident_id=created.id,
                title=created.title,
                severity=created.severity,
                service_tier=created.service_tier,
                impacted_users=created.impacted_users
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed demo data
    Base.metadata.create_all(bind=engine)
    seed_initial_demo_incidents()
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
