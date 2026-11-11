from __future__ import annotations
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field


class DatadogOrg(BaseModel):
    id: Optional[Union[str, int]] = None
    name: Optional[str] = None


class DatadogWebhookPayload(BaseModel):
    id: Optional[Union[str, int]] = Field(None, description="Event or notification ID")
    alert_id: Optional[Union[str, int]] = Field(None, description="Datadog Monitor/Alert ID")
    event_type: Optional[str] = "metric_alert_monitor"
    title: str = Field(..., description="Monitor alert title")
    body: Optional[str] = Field(None, description="Alert message or query summary")
    date: Optional[Union[int, float]] = Field(None, description="POSIX epoch timestamp of event")
    last_updated: Optional[Union[int, float]] = None
    org: Optional[DatadogOrg] = None
    tags: Optional[List[str]] = Field(default_factory=list, description="Monitor tags (e.g. service:auth-service)")
    alert_type: Optional[str] = Field("error", description="error, warning, success, info")
    alert_transition: Optional[str] = Field(None, description="Triggered, Recovered, Warn, No Data")
    hostname: Optional[str] = None
    link: Optional[str] = None
    snapshot: Optional[str] = None
