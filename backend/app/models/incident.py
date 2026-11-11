from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db.base import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    service_name = Column(String(128), nullable=False, index=True)
    severity = Column(String(32), default="MEDIUM", index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    status = Column(String(32), default="OPEN", index=True)      # OPEN, INVESTIGATING, MITIGATED, RESOLVED
    service_tier = Column(String(32), default="TIER_1")          # TIER_0, TIER_1, TIER_2, TIER_3
    impacted_users = Column(Integer, default=0)
    raw_logs = Column(Text, nullable=True)
    source = Column(String(64), default="API")                   # PagerDuty, Datadog, Prometheus, Manual
    incident_key = Column(String(128), nullable=True, index=True) # External provider correlation key
    organization_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    resolution = relationship("IncidentResolution", back_populates="incident", uselist=False, cascade="all, delete-orphan")
    investigations = relationship("Investigation", back_populates="incident", cascade="all, delete-orphan", order_by="desc(Investigation.created_at)")


class IncidentResolution(Base):
    __tablename__ = "incident_resolutions"

    id = Column(String(64), primary_key=True, index=True)
    incident_id = Column(String(64), ForeignKey("incidents.id"), unique=True, nullable=False)
    root_cause = Column(Text, nullable=False)
    action_taken = Column(Text, nullable=False)
    prevention_steps = Column(Text, nullable=True)
    verified_by = Column(String(128), default="SRE-OnCall")
    resolved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="resolution")


# Import and re-export ServiceDependency from auth models for backwards compatibility
from backend.app.models.auth import ServiceDependency
