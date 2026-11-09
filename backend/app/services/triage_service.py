import time
from typing import List, Dict, Any, Optional
from backend.app.core.algorithms import PriorityTriageQueue


class TriageService:
    """Manages real-time incident priority queue and triage scoring."""

    def __init__(self):
        self.queue = PriorityTriageQueue()

    def enqueue(self, incident_id: str, title: str, severity: str,
                service_tier: str, impacted_users: int, timestamp: Optional[float] = None) -> Dict[str, Any]:
        ts = timestamp or time.time()
        item = self.queue.push(
            incident_id=incident_id,
            title=title,
            severity=severity,
            service_tier=service_tier,
            impacted_users=impacted_users,
            timestamp=ts
        )
        return {
            "incident_id": item.incident_id,
            "title": item.title,
            "severity": item.severity,
            "service_tier": item.service_tier,
            "impacted_users": item.impacted_users,
            "score": item.score,
            "timestamp": item.timestamp
        }

    def dequeue(self) -> Optional[Dict[str, Any]]:
        item = self.queue.pop()
        if not item:
            return None
        return {
            "incident_id": item.incident_id,
            "title": item.title,
            "severity": item.severity,
            "service_tier": item.service_tier,
            "impacted_users": item.impacted_users,
            "score": item.score,
            "timestamp": item.timestamp
        }

    def remove(self, incident_id: str) -> bool:
        return self.queue.remove(incident_id)

    def list_queue(self) -> List[Dict[str, Any]]:
        return self.queue.list_all_sorted()

    def count(self) -> int:
        return self.queue.size()


# Global shared instance
triage_service = TriageService()
