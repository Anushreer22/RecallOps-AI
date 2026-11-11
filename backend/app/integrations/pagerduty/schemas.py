from __future__ import annotations
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pydantic import BaseModel, Field


class PagerDutyV3Service(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = "unknown-service"
    summary: Optional[str] = None


class PagerDutyV3IncidentData(BaseModel):
    id: str = Field(..., description="PagerDuty Incident ID (e.g. P12345)")
    number: Optional[int] = None
    title: str = Field(..., description="Incident title")
    status: str = Field("triggered", description="triggered, acknowledged, resolved")
    urgency: Optional[str] = "high"
    incident_key: Optional[str] = None
    service: Optional[PagerDutyV3Service] = None
    created_at: Optional[Union[datetime, str]] = None
    html_url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PagerDutyV3Event(BaseModel):
    id: str = Field(..., description="Unique event message delivery ID")
    event_type: str = Field(..., description="e.g. incident.triggered, incident.acknowledged, incident.resolved")
    resource_type: Optional[str] = "incident"
    occurred_at: Optional[Union[datetime, str]] = None
    data: PagerDutyV3IncidentData


class PagerDutyV3Payload(BaseModel):
    event: PagerDutyV3Event


class PagerDutyV2Incident(BaseModel):
    id: str
    incident_number: Optional[int] = None
    title: str
    status: str = "triggered"
    urgency: Optional[str] = "high"
    incident_key: Optional[str] = None
    service: Optional[Dict[str, Any]] = None


class PagerDutyV2Message(BaseModel):
    id: str
    event: str  # incident.trigger, incident.acknowledge, incident.resolve
    created_on: Optional[Union[datetime, str]] = None
    incident: PagerDutyV2Incident


class PagerDutyV2Payload(BaseModel):
    messages: List[PagerDutyV2Message]
