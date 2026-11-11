import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.models.investigation import Investigation


class InvestigationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        incident_id: str,
        provider: str,
        model_name: str,
        summary: Optional[str] = None,
        structured_result: Optional[str] = None,
        status: str = "COMPLETED",
        error_message: Optional[str] = None,
        investigation_id: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> Investigation:
        inv_id = investigation_id or f"INV-{uuid.uuid4().hex[:8].upper()}"
        investigation = Investigation(
            id=inv_id,
            incident_id=incident_id,
            provider=provider,
            model_name=model_name,
            summary=summary,
            structured_result=structured_result,
            status=status,
            created_at=datetime.now(timezone.utc),
            completed_at=completed_at or datetime.now(timezone.utc),
            error_message=error_message
        )
        try:
            self.db.add(investigation)
            self.db.commit()
            self.db.refresh(investigation)
            return investigation
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, investigation_id: str) -> Optional[Investigation]:
        return self.db.query(Investigation).filter(Investigation.id == investigation_id).first()

    def list_by_incident(self, incident_id: str, skip: int = 0, limit: int = 50) -> List[Investigation]:
        return (
            self.db.query(Investigation)
            .filter(Investigation.incident_id == incident_id)
            .order_by(Investigation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_status(
        self,
        investigation_id: str,
        status: str,
        summary: Optional[str] = None,
        structured_result: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[Investigation]:
        investigation = self.get_by_id(investigation_id)
        if not investigation:
            return None
        try:
            investigation.status = status
            if summary is not None:
                investigation.summary = summary
            if structured_result is not None:
                investigation.structured_result = structured_result
            if error_message is not None:
                investigation.error_message = error_message
            investigation.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(investigation)
            return investigation
        except Exception:
            self.db.rollback()
            raise
