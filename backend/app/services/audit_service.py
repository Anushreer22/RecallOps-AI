import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.auth import AuditLog


class AuditService:
    """Records audit logs for security, authorization, and administrative events."""

    def log(
        self,
        db: Session,
        action: str,
        resource_type: str,
        actor_user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Persists an audit log entry.
        Guarantees that sensitive data (passwords, tokens, credentials) is stripped.
        """
        sanitized_metadata = self._sanitize_metadata(metadata) if metadata else None
        metadata_json = json.dumps(sanitized_metadata) if sanitized_metadata else None

        audit_entry = AuditLog(
            id=f"AUD-{uuid.uuid4().hex[:12]}",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action.upper(),
            resource_type=resource_type.lower(),
            resource_id=str(resource_id) if resource_id is not None else None,
            request_id=request_id,
            ip_address=ip_address,
            metadata_json=metadata_json,
            created_at=datetime.now(timezone.utc)
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry

    def list_logs(
        self,
        db: Session,
        organization_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditLog]:
        query = db.query(AuditLog)
        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)
        if action:
            query = query.filter(AuditLog.action == action.upper())
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type.lower())

        return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    def _sanitize_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redacts sensitive keys from metadata dictionary."""
        sensitive_keys = {
            "password", "hashed_password", "token", "access_token", "secret",
            "api_key", "authorization", "bearer", "cookie"
        }
        clean = {}
        for k, v in data.items():
            if any(s in k.lower() for s in sensitive_keys):
                clean[k] = "[REDACTED]"
            elif isinstance(v, dict):
                clean[k] = self._sanitize_metadata(v)
            else:
                clean[k] = v
        return clean


audit_service = AuditService()
