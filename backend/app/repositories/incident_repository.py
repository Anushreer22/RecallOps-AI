from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session
from backend.app.models.incident import Incident, IncidentResolution
from backend.app.schemas.incident import IncidentCreate, ResolutionCreate


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, incident_in: IncidentCreate, incident_id: Optional[str] = None) -> Incident:
        inc_id = incident_id or f"INC-{uuid.uuid4().hex[:8].upper()}"
        db_incident = Incident(
            id=inc_id,
            title=incident_in.title,
            description=incident_in.description,
            service_name=incident_in.service_name,
            severity=incident_in.severity.upper(),
            status="OPEN",
            service_tier=incident_in.service_tier.upper(),
            impacted_users=incident_in.impacted_users,
            raw_logs=incident_in.raw_logs,
            source=incident_in.source
        )
        try:
            self.db.add(db_incident)
            self.db.commit()
            self.db.refresh(db_incident)
            return db_incident
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        return self.db.query(Incident).filter(Incident.id == incident_id).first()

    def list_all(self, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[Incident]:
        query = self.db.query(Incident)
        if status:
            query = query.filter(Incident.status == status.upper())
        return query.order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()

    def update_status(self, incident_id: str, new_status: str) -> Optional[Incident]:
        incident = self.get_by_id(incident_id)
        if not incident:
            return None
        try:
            incident.status = new_status.upper()
            self.db.commit()
            self.db.refresh(incident)
            return incident
        except Exception:
            self.db.rollback()
            raise

    def resolve(self, incident_id: str, resolution_in: ResolutionCreate) -> Optional[IncidentResolution]:
        incident = self.get_by_id(incident_id)
        if not incident:
            return None

        try:
            incident.status = "RESOLVED"
            # If resolution already exists for this incident, update it in place
            if incident.resolution:
                db_resolution = incident.resolution
                db_resolution.root_cause = resolution_in.root_cause
                db_resolution.action_taken = resolution_in.action_taken
                db_resolution.prevention_steps = resolution_in.prevention_steps
                db_resolution.verified_by = resolution_in.verified_by
                db_resolution.resolved_at = datetime.now(timezone.utc)
            else:
                res_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
                db_resolution = IncidentResolution(
                    id=res_id,
                    incident_id=incident_id,
                    root_cause=resolution_in.root_cause,
                    action_taken=resolution_in.action_taken,
                    prevention_steps=resolution_in.prevention_steps,
                    verified_by=resolution_in.verified_by,
                    resolved_at=datetime.now(timezone.utc)
                )
                self.db.add(db_resolution)

            self.db.commit()
            self.db.refresh(db_resolution)
            self.db.refresh(incident)
            return db_resolution
        except Exception:
            self.db.rollback()
            raise

    def get_all_resolved(self) -> List[Incident]:
        """Fetch all incidents that have an associated, verified resolution."""
        return (
            self.db.query(Incident)
            .join(Incident.resolution)
            .filter(
                Incident.status == "RESOLVED",
                IncidentResolution.verified_by.isnot(None),
                IncidentResolution.verified_by != ""
            )
            .all()
        )
