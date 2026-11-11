from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String(64), primary_key=True, index=True)
    incident_id = Column(String(64), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(32), nullable=False, default="openai")
    model_name = Column(String(64), nullable=False, default="gpt-4o-mini")
    summary = Column(Text, nullable=True)
    structured_result = Column(Text, nullable=True)  # JSON-encoded StructuredInvestigationReport
    status = Column(String(32), nullable=False, default="COMPLETED", index=True)  # COMPLETED, FAILED, PENDING
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="investigations")
