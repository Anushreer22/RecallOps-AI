from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WebhookIngestResultItem(BaseModel):
    event_id: str
    incident_key: Optional[str] = None
    event_type: str
    internal_incident_id: Optional[str] = None
    already_processed: bool = False
    status: str = "PROCESSED"


class WebhookIngestResponse(BaseModel):
    provider: str
    events_count: int
    processed_count: int
    duplicate_count: int
    results: List[WebhookIngestResultItem]


class WebhookEventResponse(BaseModel):
    id: int
    provider: str
    provider_event_id: str
    incident_key: Optional[str] = None
    event_type: str
    service_name: Optional[str] = None
    alert_title: Optional[str] = None
    status: str
    received_at: datetime
    processed_at: datetime
    internal_incident_id: Optional[str] = None

    class Config:
        from_attributes = True
