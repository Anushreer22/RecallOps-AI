from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Evidence Models
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    id: str = Field(..., description="Stable, unique evidence identifier e.g. EVID-INC-1")
    source_type: str = Field(..., description="incident, logs, historical_resolution, topology, telemetry_status")
    title: str = Field(..., description="Short title describing this evidence item")
    content: str = Field(..., description="Actual evidence content or observations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured attributes (e.g. similarity, tier)")


class EvidenceCollection(BaseModel):
    items: List[EvidenceItem] = Field(default_factory=list)

    def add(self, item: EvidenceItem) -> None:
        self.items.append(item)

    def get_item(self, evidence_id: str) -> Optional[EvidenceItem]:
        for item in self.items:
            if item.id == evidence_id:
                return item
        return None

    def all_ids(self) -> Set[str]:
        return {item.id for item in self.items}

    def format_for_prompt(self) -> str:
        lines = []
        for item in self.items:
            lines.append(f"[{item.id}] Source: {item.source_type} | {item.title}")
            lines.append(f"Content: {item.content.strip()}")
            if item.metadata:
                lines.append(f"Metadata: {item.metadata}")
            lines.append("-" * 40)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Structured LLM Output Schemas
# ---------------------------------------------------------------------------

class ProbableRootCause(BaseModel):
    hypothesis: str = Field(..., description="Specific hypothesized failure mechanism")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this hypothesis [0.0 - 1.0]")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence supporting this hypothesis")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence contradicting this hypothesis")
    reasoning: str = Field(..., description="Step-by-step SRE deductive reasoning grounded in evidence")


class StructuredInvestigationReport(BaseModel):
    incident_id: str = Field(..., description="Incident ID investigated")
    summary: str = Field(..., description="Concise investigation executive summary")
    probable_root_causes: List[ProbableRootCause] = Field(default_factory=list)
    observed_facts: List[str] = Field(default_factory=list, description="Verified facts directly observed in evidence")
    evidence_gaps: List[str] = Field(default_factory=list, description="Missing telemetry, logs, or uninstrumented dependencies")
    suggested_investigation_steps: List[str] = Field(default_factory=list, description="Safe diagnostics to confirm or rule out hypotheses")
    suggested_resolution: List[str] = Field(default_factory=list, description="Proposed remediation runbook actions")
    related_historical_incidents: List[str] = Field(default_factory=list, description="Referenced historical incident IDs")
    requires_human_review: bool = Field(True, description="Always requires human on-call engineer review before execution")
    hallucinated_evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs rejected during validation")


# ---------------------------------------------------------------------------
# Investigation API Schemas
# ---------------------------------------------------------------------------

class InvestigationResponse(BaseModel):
    id: str
    incident_id: str
    provider: str
    model_name: str
    status: str
    summary: Optional[str] = None
    report: Optional[StructuredInvestigationReport] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class InvestigationFeedbackCreate(BaseModel):
    approved: bool = Field(..., description="Whether the proposed resolution is verified and approved by the engineer")
    verified_by: str = Field(..., description="Name or role of the verifying engineer (e.g. SRE-Lead)")
    root_cause: Optional[str] = Field(None, description="Corrected or confirmed root cause summary")
    action_taken: Optional[str] = Field(None, description="Corrected or confirmed action taken to resolve outage")
    prevention_steps: Optional[str] = Field(None, description="Long-term prevention steps or guardrails")
    notes: Optional[str] = Field(None, description="Optional engineering feedback notes")


class InvestigationFeedbackResponse(BaseModel):
    investigation_id: str
    incident_id: str
    approved: bool
    verified_by: str
    memory_indexed: bool
    resolution_id: Optional[str] = None
    incident_status: str
    message: str
