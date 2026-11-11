from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Incident Schemas
# ---------------------------------------------------------------------------

class IncidentBase(BaseModel):
    title: str = Field(..., example="Database connection pool exhausted in auth-service")
    description: str = Field(..., example="Postgres connection pool saturated, returning 500 errors to callers.")
    service_name: str = Field(..., example="auth-service")
    severity: str = Field("HIGH", example="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    service_tier: str = Field("TIER_1", example="TIER_1")  # TIER_0, TIER_1, TIER_2, TIER_3
    impacted_users: int = Field(0, ge=0, example=1200)
    raw_logs: Optional[str] = Field(None, example="FATAL: remaining connection slots are reserved for non-replication superuser connections")
    source: str = Field("API", example="PagerDuty")
    incident_key: Optional[str] = Field(None, example="pagerduty:PD-1234")


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    impacted_users: Optional[int] = None
    raw_logs: Optional[str] = None


class ResolutionCreate(BaseModel):
    root_cause: str = Field(..., example="Leaked connections in auth token validation middleware due to unclosed db session.")
    action_taken: str = Field(..., example="Restarted auth-service pods and added context manager to properly yield/close DB sessions.")
    prevention_steps: Optional[str] = Field(None, example="Added PgBouncer connection pooler and automated pool healthcheck alert.")
    verified_by: str = Field("SRE-Lead", example="SRE-Lead")


class ResolutionResponse(BaseModel):
    id: str
    incident_id: str
    root_cause: str
    action_taken: str
    prevention_steps: Optional[str]
    verified_by: str
    resolved_at: datetime

    class Config:
        from_attributes = True


class IncidentResponse(IncidentBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolution: Optional[ResolutionResponse] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Webhook Alert Ingestion (PagerDuty/Datadog Format)
# ---------------------------------------------------------------------------

class WebhookAlertPayload(BaseModel):
    event_type: str = Field("alert.triggered", example="alert.triggered")
    alert_name: str = Field(..., example="HighErrorRate_PaymentGateway")
    service: str = Field(..., example="payment-service")
    severity: str = Field("HIGH", example="CRITICAL")
    tier: str = Field("TIER_0", example="TIER_0")
    details: str = Field(..., example="Upstream payment provider returned HTTP 504 Gateway Timeout")
    impacted_users: int = Field(500, example=5000)
    logs: Optional[str] = Field(None, example="[ERR_504_TIMEOUT] payment processing timed out after 30000ms")


# ---------------------------------------------------------------------------
# Triage & Priority Queue
# ---------------------------------------------------------------------------

class TriageQueueItem(BaseModel):
    incident_id: str
    title: str
    severity: str
    service_tier: str
    impacted_users: int
    score: float
    timestamp: float


# ---------------------------------------------------------------------------
# Memory Recall & AI Diagnosis
# ---------------------------------------------------------------------------

class HistoricalRecallMatch(BaseModel):
    incident_id: str
    similarity_score: float
    title: str
    root_cause: Optional[str] = None
    verified_fix: Optional[str] = None
    caution_notes: Optional[str] = None


class BlastRadiusSummary(BaseModel):
    origin_service: str
    total_impacted_services: int
    impacted_services: List[Dict[str, Any]]
    max_depth: int


class DiagnosisResponse(BaseModel):
    incident_id: str
    detected_signatures: List[Dict[str, str]]
    blast_radius: BlastRadiusSummary
    historical_matches: List[HistoricalRecallMatch]
    hypothesized_root_cause: str
    recommended_runbook_steps: List[str]
    cautions_and_anti_patterns: List[str]
    confidence_score: float
    ai_generated_at: datetime


# ---------------------------------------------------------------------------
# Health Schema
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    project: str
    version: str
    indexed_memories: int
    active_triage_count: int
    services_in_graph: int
