from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from backend.app.db.base import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False, index=True)       # pagerduty, datadog, alertmanager, custom
    provider_event_id = Column(String(128), nullable=False, index=True)
    incident_key = Column(String(128), nullable=True, index=True)    # Correlation key with external alerts
    event_type = Column(String(64), nullable=False)                 # triggered, acknowledged, resolved, etc.
    service_name = Column(String(128), nullable=True)
    alert_title = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="PROCESSED") # PROCESSED, DUPLICATE, FAILED, IGNORED
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    internal_incident_id = Column(String(64), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    raw_payload_summary = Column(Text, nullable=True)               # Redacted JSON string
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_webhook_provider_event"),
    )
