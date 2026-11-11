from __future__ import annotations
import abc
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(password|secret|token|api_?key|auth|bearer|credentials|private_?key|cert)"
)


def redact_sensitive_data(data: Any) -> Any:
    """
    Recursively scrubs sensitive keys (tokens, secrets, credentials) from payloads
    before storage or logging to prevent credential leakage.
    """
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive_data(value)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


class NormalizedAlertEvent(BaseModel):
    """
    Standardized internal event representation normalized across all
    external observability providers (PagerDuty, Datadog, Alertmanager).
    """
    provider: str = Field(..., description="Provider source identifier (pagerduty, datadog, alertmanager, custom)")
    provider_event_id: str = Field(..., description="Unique event ID from provider for deduplication")
    incident_key: str = Field(..., description="Correlation key mapping to specific ongoing incident/alert")
    event_type: str = Field(..., description="Lifecycle event type: triggered, acknowledged, resolved, warning, info")
    service_name: str = Field(..., description="Target service/application affected")
    alert_title: str = Field(..., description="Human-readable title/summary")
    description: str = Field("", description="Detailed incident message or stack trace")
    severity: str = Field("MEDIUM", description="Normalized severity: CRITICAL, HIGH, MEDIUM, LOW")
    status: str = Field("OPEN", description="Normalized incident status: OPEN, INVESTIGATING, RESOLVED")
    environment: str = Field("production", description="Runtime environment: production, staging, dev")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Sanitized/redacted copy of provider payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary provider labels, tags, URLs")


class BaseWebhookAdapter(abc.ABC):
    """
    Abstract interface for provider-specific webhook adapters.
    """

    @property
    @abc.abstractmethod
    def provider(self) -> str:
        """Provider identifier string."""
        pass

    @abc.abstractmethod
    def verify_security(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        """
        Validates cryptographic signatures or security tokens according
        to provider-specific authentication protocols.
        """
        pass

    @abc.abstractmethod
    def validate_payload(self, raw_body: bytes) -> Dict[str, Any]:
        """
        Parses raw bytes into structured validated payload dictionaries using Pydantic.
        Raises ValueError or ValidationError if invalid.
        """
        pass

    @abc.abstractmethod
    def normalize(self, validated_payload: Dict[str, Any], headers: Dict[str, str]) -> List[NormalizedAlertEvent]:
        """
        Transforms provider payload into one or more normalized internal alert events.
        """
        pass
