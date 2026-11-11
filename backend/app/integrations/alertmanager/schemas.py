from __future__ import annotations
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class AlertmanagerAlert(BaseModel):
    status: str = Field("firing", description="firing or resolved")
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = Field(None, description="Unique alert fingerprint hash")


class AlertmanagerWebhookPayload(BaseModel):
    version: Optional[Union[str, int]] = "4"
    groupKey: Optional[str] = None
    truncatedAlerts: Optional[int] = 0
    status: str = Field("firing", description="Group status: firing or resolved")
    receiver: Optional[str] = None
    groupLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonAnnotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    alerts: List[AlertmanagerAlert] = Field(default_factory=list, description="Array of alert objects")
