import threading
from typing import Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.integrations.registry import adapter_registry
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.incident import IncidentCreate
from backend.app.schemas.webhook import WebhookIngestResponse, WebhookIngestResultItem
from backend.app.services.deduplication_service import deduplication_service
from backend.app.services.triage_service import triage_service


class WebhookProcessingService:
    """
    Orchestrates the ingestion, security verification, parsing, normalization,
    deduplication, and incident lifecycle transitions for incoming webhooks.
    """

    def __init__(self):
        self._lock = threading.RLock()

    def process_webhook(
        self,
        provider: str,
        raw_body: bytes,
        headers: Dict[str, str],
        db: Session
    ) -> WebhookIngestResponse:
        # 1. Enforce payload size limit
        if len(raw_body) > settings.WEBHOOK_MAX_PAYLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Webhook payload ({len(raw_body)} bytes) exceeds maximum configured limit of {settings.WEBHOOK_MAX_PAYLOAD_BYTES} bytes."
            )

        # 2. Locate adapter
        adapter = adapter_registry.get(provider)
        if not adapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No webhook adapter registered for provider '{provider}'"
            )

        # 3. Security verification
        if not adapter.verify_security(raw_body, headers):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Webhook authentication or signature verification failed for provider '{provider}'"
            )

        # 4. Payload validation
        try:
            validated_payload = adapter.validate_payload(raw_body)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid payload format for provider '{provider}': {str(e)}"
            )

        # 5. Normalization
        normalized_events = adapter.normalize(validated_payload, headers)
        if not normalized_events:
            return WebhookIngestResponse(
                provider=provider,
                events_count=0,
                processed_count=0,
                duplicate_count=0,
                results=[]
            )

        repo = IncidentRepository(db)
        results: List[WebhookIngestResultItem] = []
        processed_count = 0
        duplicate_count = 0

        # 6. Deduplication & Incident Lifecycle Management (Thread-Safe Transaction)
        with self._lock:
            for event in normalized_events:
                # Check if this exact webhook event has already been recorded and processed
                existing_event = deduplication_service.check_duplicate(
                    db=db,
                    provider=event.provider,
                    provider_event_id=event.provider_event_id
                )

                if existing_event and existing_event.status == "PROCESSED":
                    duplicate_count += 1
                    results.append(
                        WebhookIngestResultItem(
                            event_id=existing_event.provider_event_id,
                            incident_key=existing_event.incident_key,
                            event_type=existing_event.event_type,
                            internal_incident_id=existing_event.internal_incident_id,
                            already_processed=True,
                            status="DUPLICATE"
                        )
                    )
                    continue

                try:
                    # Event is new (or retry of failed event): correlate by incident_key
                    existing_incident = repo.get_by_incident_key(event.incident_key) if event.incident_key else None
                    internal_incident_id = None

                    if event.event_type == "resolved":
                        if existing_incident:
                            internal_incident_id = existing_incident.id
                            repo.update_status(existing_incident.id, "RESOLVED")
                            triage_service.remove(existing_incident.id)
                            # CRITICAL: Resolved webhooks must NEVER automatically create
                            # a verified IncidentResolution or trusted episodic memory.
                            # Only human SREs create verified resolutions.
                        else:
                            # Received resolved event for an untracked incident
                            inc_in = IncidentCreate(
                                title=event.alert_title,
                                description=event.description or "Auto-resolved alert",
                                service_name=event.service_name,
                                severity=event.severity,
                                service_tier="TIER_1",
                                impacted_users=0,
                                raw_logs=event.description,
                                source=provider.capitalize(),
                                incident_key=event.incident_key
                            )
                            new_inc = repo.create(inc_in)
                            internal_incident_id = new_inc.id
                            repo.update_status(new_inc.id, "RESOLVED")
                            triage_service.remove(new_inc.id)

                    elif event.event_type == "acknowledged":
                        if existing_incident:
                            internal_incident_id = existing_incident.id
                            if existing_incident.status == "OPEN":
                                repo.update_status(existing_incident.id, "INVESTIGATING")
                        else:
                            inc_in = IncidentCreate(
                                title=event.alert_title,
                                description=event.description or "Acknowledged incident",
                                service_name=event.service_name,
                                severity=event.severity,
                                service_tier="TIER_1",
                                impacted_users=50,
                                raw_logs=event.description,
                                source=provider.capitalize(),
                                incident_key=event.incident_key
                            )
                            new_inc = repo.create(inc_in)
                            internal_incident_id = new_inc.id
                            repo.update_status(new_inc.id, "INVESTIGATING")

                    else:
                        # Triggered / Warning / New alert
                        if existing_incident:
                            internal_incident_id = existing_incident.id
                            if existing_incident.status == "RESOLVED":
                                # Re-opened incident
                                repo.update_status(existing_incident.id, "OPEN")
                                triage_service.enqueue(
                                    incident_id=existing_incident.id,
                                    title=existing_incident.title,
                                    severity=existing_incident.severity,
                                    service_tier=existing_incident.service_tier,
                                    impacted_users=existing_incident.impacted_users
                                )
                        else:
                            inc_in = IncidentCreate(
                                title=event.alert_title,
                                description=event.description or "Ingested alert",
                                service_name=event.service_name,
                                severity=event.severity,
                                service_tier="TIER_1",
                                impacted_users=500 if event.severity in ("CRITICAL", "HIGH") else 50,
                                raw_logs=event.description,
                                source=provider.capitalize(),
                                incident_key=event.incident_key
                            )
                            new_inc = repo.create(inc_in)
                            internal_incident_id = new_inc.id

                            # Enqueue in priority triage queue
                            triage_service.enqueue(
                                incident_id=new_inc.id,
                                title=new_inc.title,
                                severity=new_inc.severity,
                                service_tier=new_inc.service_tier,
                                impacted_users=new_inc.impacted_users
                            )

                    # Record event in WebhookEvent table for idempotency
                    db_event, is_dup = deduplication_service.record_processed_event(
                        db=db,
                        event=event,
                        internal_incident_id=internal_incident_id,
                        status="PROCESSED"
                    )

                    if is_dup:
                        duplicate_count += 1
                    else:
                        processed_count += 1

                    results.append(
                        WebhookIngestResultItem(
                            event_id=db_event.provider_event_id,
                            incident_key=db_event.incident_key,
                            event_type=db_event.event_type,
                            internal_incident_id=internal_incident_id,
                            already_processed=is_dup,
                            status=db_event.status
                        )
                    )

                except Exception as exc:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Database transaction failure processing event '{event.provider_event_id}': {str(exc)}"
                    )

        return WebhookIngestResponse(
            provider=provider,
            events_count=len(normalized_events),
            processed_count=processed_count,
            duplicate_count=duplicate_count,
            results=results
        )


webhook_service = WebhookProcessingService()
