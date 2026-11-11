import json
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.models.webhook_event import WebhookEvent
from backend.app.integrations.base import NormalizedAlertEvent


class DeduplicationService:
    """
    Handles idempotency tracking and deduplication for webhook events
    backed by the database unique constraint on (provider, provider_event_id).
    """

    def check_duplicate(self, db: Session, provider: str, provider_event_id: str) -> Optional[WebhookEvent]:
        """
        Returns existing WebhookEvent if previously received, else None.
        """
        return (
            db.query(WebhookEvent)
            .filter(
                WebhookEvent.provider == provider,
                WebhookEvent.provider_event_id == provider_event_id
            )
            .first()
        )

    def record_processed_event(
        self,
        db: Session,
        event: NormalizedAlertEvent,
        internal_incident_id: Optional[str] = None,
        status: str = "PROCESSED",
        error_message: Optional[str] = None
    ) -> Tuple[WebhookEvent, bool]:
        """
        Records the webhook event into the database.
        Returns (WebhookEvent, is_duplicate).
        Handles race conditions gracefully via UniqueConstraint and rollback.
        """
        # First check
        existing = self.check_duplicate(db, event.provider, event.provider_event_id)
        if existing:
            if existing.status == "PROCESSED":
                return existing, True
            # If previous attempt failed, allow retry to re-process and update status
            try:
                existing.status = status
                existing.internal_incident_id = internal_incident_id
                existing.processed_at = datetime.now(timezone.utc)
                existing.error_message = error_message
                db.commit()
                db.refresh(existing)
                return existing, False
            except Exception:
                db.rollback()
                raise

        raw_summary = json.dumps(event.raw_payload) if event.raw_payload else None

        db_event = WebhookEvent(
            provider=event.provider,
            provider_event_id=event.provider_event_id,
            incident_key=event.incident_key,
            event_type=event.event_type,
            service_name=event.service_name,
            alert_title=event.alert_title,
            status=status,
            received_at=event.received_at or datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            internal_incident_id=internal_incident_id,
            raw_payload_summary=raw_summary,
            error_message=error_message
        )

        try:
            db.add(db_event)
            db.commit()
            db.refresh(db_event)
            return db_event, False
        except IntegrityError:
            # Race condition: another thread/worker inserted the exact same event
            db.rollback()
            existing = self.check_duplicate(db, event.provider, event.provider_event_id)
            if existing:
                return existing, True
            raise
        except Exception:
            db.rollback()
            raise

    def list_events(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 50,
        provider: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[WebhookEvent]:
        query = db.query(WebhookEvent)
        if provider:
            query = query.filter(WebhookEvent.provider == provider.lower())
        if status:
            query = query.filter(WebhookEvent.status == status.upper())
        return query.order_by(WebhookEvent.received_at.desc()).offset(skip).limit(limit).all()


deduplication_service = DeduplicationService()
