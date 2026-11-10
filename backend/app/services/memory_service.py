import threading
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.core.algorithms import EpisodicMemoryIndex
from backend.app.repositories.incident_repository import IncidentRepository


class EpisodicMemoryService:
    """
    Manages episodic memory for production incidents.
    Bridges durable database persistence (SQLAlchemy) with in-memory
    sparse vector TF-IDF retrieval (EpisodicMemoryIndex).
    """

    def __init__(self, index: Optional[EpisodicMemoryIndex] = None):
        self.index = index or EpisodicMemoryIndex()
        self._lock = threading.RLock()
        self.is_ready: bool = False
        self.last_error: Optional[str] = None

    def rehydrate_from_db(self, db: Session) -> int:
        """
        Loads verified historical resolutions from the database and rebuilds the index.
        If no historical records exist, initializes an empty index cleanly.
        Returns the count of verified indexed records.
        """
        with self._lock:
            try:
                repo = IncidentRepository(db)
                resolved_incidents = repo.get_all_resolved()
                self.index.clear()
                count = 0

                for inc in resolved_incidents:
                    # Guard: Must have an associated resolution
                    if not inc.resolution:
                        continue
                    
                    # Guard: Resolution must be verified by an SRE/engineer
                    if not inc.resolution.verified_by or not inc.resolution.root_cause:
                        continue

                    combined_text = (
                        f"{inc.title} {inc.description} "
                        f"Service: {inc.service_name} "
                        f"Logs: {inc.raw_logs or ''} "
                        f"Root cause: {inc.resolution.root_cause} "
                        f"Action: {inc.resolution.action_taken} "
                        f"Prevention: {inc.resolution.prevention_steps or ''}"
                    )
                    metadata = {
                        "title": inc.title,
                        "service": inc.service_name,
                        "root_cause": inc.resolution.root_cause,
                        "verified_fix": inc.resolution.action_taken,
                        "caution_notes": inc.resolution.prevention_steps,
                        "verified_by": inc.resolution.verified_by,
                        "resolved_at": inc.resolution.resolved_at.isoformat() if inc.resolution.resolved_at else None
                    }
                    self.index.add_document(inc.id, combined_text, metadata)
                    count += 1

                self.is_ready = True
                self.last_error = None
                return count
            except Exception as e:
                self.is_ready = False
                self.last_error = str(e)
                raise

    def recall(self, query_text: str, top_k: int = 3, threshold: float = 0.05) -> List[Dict[str, Any]]:
        """
        Queries episodic memory for similar historical outages.
        Safely returns empty list for blank queries or empty memory index.
        """
        with self._lock:
            if not query_text or not query_text.strip():
                return []
            if self.index.total_docs == 0:
                return []
            return self.index.search_similar(query_text, top_k=top_k, threshold=threshold)

    def record_resolution(
        self,
        incident_id: str,
        title: str,
        description: str,
        service_name: str,
        root_cause: str,
        action_taken: str,
        prevention_steps: Optional[str] = None,
        raw_logs: Optional[str] = None,
        verified_by: Optional[str] = None
    ) -> bool:
        """
        Indexes a verified resolution into the episodic vector memory.
        Rejects unverified resolutions (verified_by is required).
        Returns True if indexed, False if rejected as unverified.
        """
        with self._lock:
            # Guard: Never save unverified AI diagnoses or unverified resolutions
            if not verified_by or not verified_by.strip():
                return False

            combined_text = (
                f"{title} {description} "
                f"Service: {service_name} "
                f"Logs: {raw_logs or ''} "
                f"Root cause: {root_cause} "
                f"Action: {action_taken} "
                f"Prevention: {prevention_steps or ''}"
            )
            metadata = {
                "title": title,
                "service": service_name,
                "root_cause": root_cause,
                "verified_fix": action_taken,
                "caution_notes": prevention_steps,
                "verified_by": verified_by
            }
            self.index.add_document(incident_id, combined_text, metadata)
            return True

    def count(self) -> int:
        with self._lock:
            return self.index.total_docs

    def clear(self) -> None:
        with self._lock:
            self.index.clear()
            self.is_ready = False
            self.last_error = None


# Global shared instance
memory_service = EpisodicMemoryService()
