import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.integrations.base import BaseWebhookAdapter, NormalizedAlertEvent, redact_sensitive_data
from backend.app.integrations.alertmanager.schemas import AlertmanagerWebhookPayload
from backend.app.integrations.alertmanager.security import verify_alertmanager_auth


class AlertmanagerAdapter(BaseWebhookAdapter):
    """
    Adapter for Prometheus Alertmanager Webhooks (v4 format).
    """

    @property
    def provider(self) -> str:
        return "alertmanager"

    def verify_security(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        if not settings.WEBHOOK_AUTH_REQUIRED and not settings.ALERTMANAGER_WEBHOOK_TOKEN:
            return True
        return verify_alertmanager_auth(headers, settings.ALERTMANAGER_WEBHOOK_TOKEN)

    def validate_payload(self, raw_body: bytes) -> Dict[str, Any]:
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Invalid JSON payload: {str(e)}")

        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object")

        try:
            validated = AlertmanagerWebhookPayload.model_validate(data)
            return validated.model_dump()
        except ValidationError as e:
            raise ValueError(f"Invalid Alertmanager payload format: {str(e)}")

    def normalize(self, validated_payload: Dict[str, Any], headers: Dict[str, str]) -> List[NormalizedAlertEvent]:
        events: List[NormalizedAlertEvent] = []
        now = datetime.now(timezone.utc)
        payload = validated_payload

        common_labels = payload.get("commonLabels") or {}
        common_annotations = payload.get("commonAnnotations") or {}
        raw_alerts = payload.get("alerts") or []

        # If payload has no alerts listed, construct one from group/common fields
        if not raw_alerts:
            raw_alerts = [{
                "status": payload.get("status", "firing"),
                "labels": common_labels,
                "annotations": common_annotations,
                "fingerprint": hashlib.sha256(str(payload.get("groupKey", "default")).encode("utf-8")).hexdigest()[:16]
            }]

        for alert in raw_alerts:
            # Merge labels (alert-specific overrides common)
            labels = {**common_labels, **(alert.get("labels") or {})}
            annotations = {**common_annotations, **(alert.get("annotations") or {})}

            service_name = (
                labels.get("service")
                or labels.get("app")
                or labels.get("job")
                or labels.get("alertname")
                or "prometheus-service"
            )
            environment = labels.get("env") or labels.get("environment") or "production"

            alert_status = (alert.get("status") or payload.get("status") or "firing").lower()
            if alert_status == "resolved":
                event_type = "resolved"
                status = "RESOLVED"
            else:
                event_type = "triggered"
                status = "OPEN"

            # Severity mapping
            raw_sev = (labels.get("severity") or "warning").lower()
            if raw_sev in ("critical", "page", "fatal", "disaster"):
                severity = "CRITICAL"
            elif raw_sev in ("warning", "warn", "high"):
                severity = "HIGH"
            elif raw_sev in ("info", "low", "notice"):
                severity = "LOW"
            else:
                severity = "MEDIUM"

            # Correlation key: fingerprint or deterministic hash of labels
            fingerprint = alert.get("fingerprint")
            if not fingerprint:
                label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
                fingerprint = hashlib.sha256(label_str.encode("utf-8")).hexdigest()[:16]

            incident_key = f"alertmanager-{fingerprint}"

            # Occurred at
            time_str = alert.get("endsAt") if alert_status == "resolved" else alert.get("startsAt")
            if time_str and isinstance(time_str, str):
                try:
                    occurred_at_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                except Exception:
                    occurred_at_dt = now
            else:
                occurred_at_dt = now

            # Unique provider event ID
            # Deterministic fallback without volatile timestamps for retry stability
            if time_str:
                event_seed = f"alertmanager:{fingerprint}:{event_type}:{time_str}"
            else:
                alert_name_val = labels.get("alertname") or ""
                summary_val = annotations.get("summary") or annotations.get("title") or ""
                event_seed = f"alertmanager:{fingerprint}:{event_type}:{alert_name_val}:{summary_val}"
            provider_event_id = hashlib.sha256(event_seed.encode("utf-8")).hexdigest()

            title = (
                annotations.get("summary")
                or annotations.get("title")
                or labels.get("alertname")
                or f"Prometheus Alert: {service_name}"
            )
            desc = annotations.get("description") or annotations.get("message") or ""

            events.append(
                NormalizedAlertEvent(
                    provider=self.provider,
                    provider_event_id=provider_event_id,
                    incident_key=incident_key,
                    event_type=event_type,
                    service_name=service_name,
                    alert_title=title,
                    description=desc,
                    severity=severity,
                    status=status,
                    environment=environment,
                    occurred_at=occurred_at_dt,
                    received_at=now,
                    raw_payload=redact_sensitive_data(alert),
                    metadata={
                        "labels": labels,
                        "annotations": annotations,
                        "groupKey": payload.get("groupKey"),
                        "receiver": payload.get("receiver"),
                        "externalURL": payload.get("externalURL"),
                        "generatorURL": alert.get("generatorURL"),
                        "fingerprint": fingerprint,
                    }
                )
            )

        return events
