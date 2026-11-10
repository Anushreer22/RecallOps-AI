from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    WebhookAlertPayload,
    TriageQueueItem,
    DiagnosisResponse,
    ResolutionCreate,
    ResolutionResponse,
    BlastRadiusSummary,
    HistoricalRecallMatch
)
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.services.memory_service import memory_service
from backend.app.services.topology_service import topology_service
from backend.app.services.triage_service import triage_service
from backend.app.services.ai_agent_service import ai_agent

router = APIRouter(prefix="/incidents", tags=["Incidents & Ops"])


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    """Creates a new incident, persists it, and enqueues into priority triage."""
    repo = IncidentRepository(db)
    incident = repo.create(incident_in)
    
    # Enqueue to priority triage queue
    triage_service.enqueue(
        incident_id=incident.id,
        title=incident.title,
        severity=incident.severity,
        service_tier=incident.service_tier,
        impacted_users=incident.impacted_users
    )
    return incident


@router.post("/webhook", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def ingest_webhook_alert(payload: WebhookAlertPayload, db: Session = Depends(get_db)):
    """
    Ingests an incoming alert from PagerDuty, Datadog, Prometheus, or Grafana,
    maps it to an Incident model, and enqueues it for triage.
    """
    incident_in = IncidentCreate(
        title=f"[{payload.service}] {payload.alert_name}",
        description=payload.details,
        service_name=payload.service,
        severity=payload.severity,
        service_tier=payload.tier,
        impacted_users=payload.impacted_users,
        raw_logs=payload.logs,
        source=f"Webhook:{payload.event_type}"
    )
    repo = IncidentRepository(db)
    incident = repo.create(incident_in)

    triage_service.enqueue(
        incident_id=incident.id,
        title=incident.title,
        severity=incident.severity,
        service_tier=incident.service_tier,
        impacted_users=incident.impacted_users
    )
    return incident


@router.get("", response_model=List[IncidentResponse])
def list_incidents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by OPEN, INVESTIGATING, MITIGATED, RESOLVED"),
    db: Session = Depends(get_db)
):
    """Lists all recorded incidents with pagination and status filters."""
    repo = IncidentRepository(db)
    return repo.list_all(skip=skip, limit=limit, status=status)


@router.get("/triage/queue", response_model=List[TriageQueueItem])
def get_triage_queue():
    """Returns all active, unmitigated incidents ordered by calculated Priority Score (Max-Heap)."""
    return triage_service.list_queue()


@router.get("/topology/blast-radius", response_model=BlastRadiusSummary)
def get_blast_radius(service: str = Query(..., description="Service to analyze")):
    """
    Traverses the microservice dependency DAG to compute downstream blast radius
    and impact weight when a specific service fails.
    """
    data = topology_service.get_blast_radius(service)
    return BlastRadiusSummary(**data)


@router.get("/memory/search", response_model=List[HistoricalRecallMatch])
def search_episodic_memory(
    q: str = Query(..., description="Error message, stack trace, or incident summary"),
    limit: int = Query(3, ge=1, le=10)
):
    """
    Queries the vector episodic memory using Cosine Similarity k-NN
    to recall relevant historical outages and past runbooks.
    """
    matches = memory_service.recall(q, top_k=limit)
    return [
        HistoricalRecallMatch(
            incident_id=m["incident_id"],
            similarity_score=m["similarity_score"],
            title=m["metadata"].get("title", m["incident_id"]),
            root_cause=m["metadata"].get("root_cause"),
            verified_fix=m["metadata"].get("verified_fix"),
            caution_notes=m["metadata"].get("caution_notes")
        )
        for m in matches
    ]


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Retrieves detailed incident information including resolution status."""
    repo = IncidentRepository(db)
    incident = repo.get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.post("/{incident_id}/diagnose", response_model=DiagnosisResponse)
def diagnose_incident(incident_id: str, db: Session = Depends(get_db)):
    """
    Runs the AI Agent on an incident:
    1. Parses raw logs through Prefix Trie to extract error codes.
    2. Performs k-NN vector search on episodic memory for past outages.
    3. Calculates downstream blast radius on the service dependency graph.
    4. Generates a prioritized diagnosis and safe remediation runbook.
    """
    repo = IncidentRepository(db)
    incident = repo.get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    repo.update_status(incident_id, "INVESTIGATING")

    diagnosis = ai_agent.diagnose(
        incident_id=incident.id,
        title=incident.title,
        description=incident.description,
        service_name=incident.service_name,
        raw_logs=incident.raw_logs or ""
    )
    return diagnosis


@router.post("/{incident_id}/resolve", response_model=ResolutionResponse)
def resolve_incident(incident_id: str, resolution_in: ResolutionCreate, db: Session = Depends(get_db)):
    """
    Resolves an active incident, removes it from the triage queue,
    and indexes the verified resolution into the episodic vector memory
    to train future AI incident recall.
    """
    repo = IncidentRepository(db)
    resolution = repo.resolve(incident_id, resolution_in)
    if not resolution:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    # Remove from priority queue
    triage_service.remove(incident_id)

    # Re-index into episodic memory for future recall (only if verified)
    incident = repo.get_by_id(incident_id)
    if incident and resolution.verified_by:
        memory_service.record_resolution(
            incident_id=incident.id,
            title=incident.title,
            description=incident.description,
            service_name=incident.service_name,
            root_cause=resolution.root_cause,
            action_taken=resolution.action_taken,
            prevention_steps=resolution.prevention_steps,
            raw_logs=incident.raw_logs,
            verified_by=resolution.verified_by
        )

    return resolution
