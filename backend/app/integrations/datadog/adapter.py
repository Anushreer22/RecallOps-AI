import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.integrations.base import BaseWebhookAdapter, NormalizedAlertEvent, redact_sensitive_data
from backend.app.integrations.datadog.schemas import DatadogWebhookPayload
from backend.app.integrations.datadog.security import verify_datadog_token


class DatadogAdapter(BaseWebhookAdapter):
    """
    Adapter for Datadog Monitor & Event Webhooks.
    """

    @property
    def provider(self) -> str:
        return "datadog"

    def verify_security(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        if not settings.WEBHOOK_AUTH_REQUIRED and not settings.DATADOG_WEBHOOK_TOKEN:
            return True
        return verify_datadog_token(headers, settings.DATADOG_WEBHOOK_TOKEN)

    def validate_payload(self, raw_body: bytes) -> Dict[str, Any]:
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Invalid JSON payload: {str(e)}")

        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object")

        try:
            validated = DatadogWebhookPayload.model_validate(data)
            return validated.model_dump()
        except ValidationError as e:
            raise ValueError(f"Invalid Datadog payload format: {str(e)}")

    def normalize(self, validated_payload: Dict[str, Any], headers: Dict[str, str]) -> List[NormalizedAlertEvent]:
        now = datetime.now(timezone.utc)
        payload = validated_payload

        # Tags extraction: service, env, etc.
        tags = payload.get("tags") or []
        tag_dict = {}
        for tag in tags:
            if ":" in tag:
                k, v = tag.split(":", 1)
                tag_dict[k.strip().lower()] = v.strip()
            elif "=" in tag:
                k, v = tag.split("=", 1)
                tag_dict[k.strip().lower()] = v.strip()

        service_name = tag_dict.get("service") or tag_dict.get("app") or "datadog-service"
        environment = tag_dict.get("env") or tag_dict.get("environment") or "production"

        alert_type = (payload.get("alert_type") or "error").lower()
        transition = (payload.get("alert_transition") or "").lower()

        # Map lifecycle event_type & status
        if transition == "recovered" or alert_type == "success":
            event_type = "resolved"
            status = "RESOLVED"
        elif transition in ("warn", "warning"):
            event_type = "warning"
            status = "OPEN"
        elif transition in ("no data", "nodata"):
            event_type = "warning"
            status = "OPEN"
        elif transition in ("triggered", "re-triggered", "renotified") or alert_type == "error":
            event_type = "triggered"
            status = "OPEN"
        else:
            event_type = alert_type or "triggered"
            status = "OPEN"

        # Map severity
        if alert_type == "error" or "critical" in (payload.get("title") or "").lower():
            severity = "CRITICAL"
        elif alert_type in ("warn", "warning") or transition in ("warn", "warning"):
            severity = "HIGH"
        elif alert_type == "info":
            severity = "LOW"
        else:
            severity = "MEDIUM"

        alert_id = payload.get("alert_id")
        raw_id = payload.get("id")

        incident_key = str(alert_id) if alert_id is not None else (str(raw_id) if raw_id is not None else "datadog-default")

        # Timestamp parsing
        raw_date = payload.get("date")
        if raw_date:
            try:
                # Could be seconds or milliseconds
                epoch_sec = float(raw_date)
                if epoch_sec > 1e11:  # milliseconds
                    epoch_sec = epoch_sec / 1000.0
                occurred_at_dt = datetime.fromtimestamp(epoch_sec, tz=timezone.utc)
            except Exception:
                occurred_at_dt = now
        else:
            occurred_at_dt = now

        # Provider event ID
        if raw_id is not None:
            provider_event_id = str(raw_id)
        else:
            # Deterministic fallback without volatile timestamps for retry stability
            raw_title = payload.get("title") or ""
            raw_body_text = payload.get("body") or ""
            seed = f"datadog:{incident_key}:{transition or alert_type}:{raw_date if raw_date is not None else ''}:{raw_title}:{raw_body_text}"
            provider_event_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()

        title = payload.get("title") or "Datadog Monitor Alert"
        body = payload.get("body") or ""

        event = NormalizedAlertEvent(
            provider=self.provider,
            provider_event_id=provider_event_id,
            incident_key=incident_key,
            event_type=event_type,
            service_name=service_name,
            alert_title=title,
            description=body,
            severity=severity,
            status=status,
            environment=environment,
            occurred_at=occurred_at_dt,
            received_at=now,
            raw_payload=redact_sensitive_data(payload),
            metadata={
                "tags": tags,
                "parsed_tags": tag_dict,
                "hostname": payload.get("hostname"),
                "link": payload.get("link"),
                "alert_type": alert_type,
                "alert_transition": transition,
                "org": payload.get("org"),
            }
        )

        return [event]
