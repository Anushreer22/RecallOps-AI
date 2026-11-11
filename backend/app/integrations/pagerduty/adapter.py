import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.integrations.base import BaseWebhookAdapter, NormalizedAlertEvent, redact_sensitive_data
from backend.app.integrations.pagerduty.schemas import PagerDutyV3Payload, PagerDutyV2Payload
from backend.app.integrations.pagerduty.security import verify_pagerduty_signature


class PagerDutyAdapter(BaseWebhookAdapter):
    """
    Adapter for PagerDuty Webhooks (supporting V3 standard and V2 legacy messages).
    """

    @property
    def provider(self) -> str:
        return "pagerduty"

    def verify_security(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        if not settings.WEBHOOK_AUTH_REQUIRED and not settings.PAGERDUTY_WEBHOOK_SECRET:
            return True
        return verify_pagerduty_signature(raw_body, headers, settings.PAGERDUTY_WEBHOOK_SECRET)

    def validate_payload(self, raw_body: bytes) -> Dict[str, Any]:
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Invalid JSON payload: {str(e)}")

        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object")

        # Try V3 schema first
        if "event" in data:
            try:
                validated = PagerDutyV3Payload.model_validate(data)
                return validated.model_dump()
            except ValidationError as e:
                raise ValueError(f"Invalid PagerDuty v3 payload format: {str(e)}")

        # Try V2 schema
        elif "messages" in data:
            try:
                validated = PagerDutyV2Payload.model_validate(data)
                return validated.model_dump()
            except ValidationError as e:
                raise ValueError(f"Invalid PagerDuty v2 payload format: {str(e)}")

        raise ValueError("Payload does not match PagerDuty v3 ('event') or v2 ('messages') format")

    def normalize(self, validated_payload: Dict[str, Any], headers: Dict[str, str]) -> List[NormalizedAlertEvent]:
        events: List[NormalizedAlertEvent] = []
        now = datetime.now(timezone.utc)

        # Handle V3
        if "event" in validated_payload:
            evt = validated_payload["event"]
            evt_id = evt["id"]
            evt_type_raw = evt.get("event_type", "incident.triggered").lower()
            data = evt.get("data", {})
            inc_id = data.get("id", evt_id)
            inc_key = data.get("incident_key") or inc_id

            # Map lifecycle event type & status
            if "trigger" in evt_type_raw:
                event_type = "triggered"
                status = "OPEN"
            elif "ack" in evt_type_raw:
                event_type = "acknowledged"
                status = "INVESTIGATING"
            elif "resolve" in evt_type_raw:
                event_type = "resolved"
                status = "RESOLVED"
            else:
                event_type = evt_type_raw
                status = "OPEN"

            urgency = (data.get("urgency") or "high").lower()
            severity = "CRITICAL" if urgency == "high" else "LOW"

            service_info = data.get("service") or {}
            service_name = service_info.get("name") or service_info.get("summary") or "default-service"

            occurred_at = evt.get("occurred_at")
            if isinstance(occurred_at, str):
                try:
                    occurred_at_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
                except Exception:
                    occurred_at_dt = now
            else:
                occurred_at_dt = now

            events.append(
                NormalizedAlertEvent(
                    provider=self.provider,
                    provider_event_id=evt_id,
                    incident_key=str(inc_key),
                    event_type=event_type,
                    service_name=service_name,
                    alert_title=data.get("title", f"PagerDuty Incident {inc_id}"),
                    description=json.dumps(data.get("details", {})) if data.get("details") else data.get("title", ""),
                    severity=severity,
                    status=status,
                    environment="production",
                    occurred_at=occurred_at_dt,
                    received_at=now,
                    raw_payload=redact_sensitive_data(validated_payload),
                    metadata={
                        "pagerduty_incident_id": inc_id,
                        "pagerduty_incident_number": data.get("number"),
                        "html_url": data.get("html_url"),
                        "urgency": urgency
                    }
                )
            )

        # Handle V2
        elif "messages" in validated_payload:
            for msg in validated_payload["messages"]:
                msg_id = msg["id"]
                event_raw = msg.get("event", "incident.trigger").lower()
                inc = msg.get("incident", {})
                inc_id = inc.get("id", msg_id)
                inc_key = inc.get("incident_key") or inc_id

                if "trigger" in event_raw:
                    event_type = "triggered"
                    status = "OPEN"
                elif "ack" in event_raw:
                    event_type = "acknowledged"
                    status = "INVESTIGATING"
                elif "resolve" in event_raw:
                    event_type = "resolved"
                    status = "RESOLVED"
                else:
                    event_type = event_raw
                    status = "OPEN"

                urgency = (inc.get("urgency") or "high").lower()
                severity = "CRITICAL" if urgency == "high" else "LOW"

                service_name = (inc.get("service") or {}).get("name", "default-service")

                events.append(
                    NormalizedAlertEvent(
                        provider=self.provider,
                        provider_event_id=msg_id,
                        incident_key=str(inc_key),
                        event_type=event_type,
                        service_name=service_name,
                        alert_title=inc.get("title", f"PagerDuty Incident {inc_id}"),
                        description=inc.get("title", ""),
                        severity=severity,
                        status=status,
                        environment="production",
                        occurred_at=now,
                        received_at=now,
                        raw_payload=redact_sensitive_data(msg),
                        metadata={
                            "pagerduty_incident_id": inc_id,
                            "pagerduty_incident_number": inc.get("incident_number"),
                            "urgency": urgency
                        }
                    )
                )

        return events
