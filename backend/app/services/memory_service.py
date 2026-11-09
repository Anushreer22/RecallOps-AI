from typing import List, Dict, Any, Optional
from backend.app.core.algorithms import EpisodicMemoryIndex

class EpisodicMemoryService:
    """Manages indexing and recall of historical post-mortems and resolutions."""

    def __init__(self):
        self.index = EpisodicMemoryIndex()
        self._seed_historical_outages()

    def _seed_historical_outages(self):
        """Seed realistic SRE incidents into episodic memory for instant retrieval."""
        seed_data = [
            {
                "id": "HIST-001",
                "text": "PostgreSQL connection pool exhaustion under high traffic load in auth-service. Error: remaining connection slots are reserved. Callers received 500 internal server errors.",
                "metadata": {
                    "title": "Database connection pool saturated in auth-service",
                    "service": "auth-service",
                    "root_cause": "Unclosed SQLAlchemy db sessions in JWT verification middleware led to idle connection leak.",
                    "verified_fix": "Applied context manager 'with get_db() as db' and configured PgBouncer connection pooler with max_client_conn=500.",
                    "caution_notes": "Do not simply increase max_connections on Postgres without PgBouncer, as it will cause OOM on the database primary."
                }
            },
            {
                "id": "HIST-002",
                "text": "Redis OOM command not allowed when used memory > maxmemory. Session cache eviction storm caused high database CPU spike.",
                "metadata": {
                    "title": "Redis out-of-memory cache eviction collapse",
                    "service": "redis-session-cache",
                    "root_cause": "User sessions created without an explicit TTL, accumulating stale session keys indefinitely until memory saturated.",
                    "verified_fix": "Configured maxmemory-policy volatile-lru, applied default 24h TTL on all session keys, and flushed expired keys via cron.",
                    "caution_notes": "Do not use 'KEYS *' to debug Redis memory in production, use 'SCAN' with count limit."
                }
            },
            {
                "id": "HIST-003",
                "text": "Kubernetes CoreDNS resolution timeout 504 gateway error in payment-service. Upstream external payment provider DNS queries failing intermittently.",
                "metadata": {
                    "title": "CoreDNS timeout during external API resolution",
                    "service": "payment-service",
                    "root_cause": "Default k8s resolv.conf ndots:5 caused 5 internal domain lookups before querying public DNS, causing CoreDNS query spikes and timeouts.",
                    "verified_fix": "Appended trailing dot '.' to external API hostnames and set dnsConfig with ndots:2 and single-request-reopen.",
                    "caution_notes": "Restarting CoreDNS pods only provides temporary relief; dnsConfig is the permanent solution."
                }
            },
            {
                "id": "HIST-004",
                "text": "Checkout payment gateway HTTP 429 Too Many Requests rate limit breach. Payment provider blocked checkout transactions for 15 minutes.",
                "metadata": {
                    "title": "Third-party payment provider rate limit throttle",
                    "service": "payment-service",
                    "root_cause": "Payment provider lowered API rate limit from 500 req/sec to 150 req/sec without prior deprecation notice.",
                    "verified_fix": "Implemented client-side token bucket rate limiter with jittered exponential backoff and graceful request queueing.",
                    "caution_notes": "Do not retry failed 429 requests immediately; it exacerbates provider throttling."
                }
            },
            {
                "id": "HIST-005",
                "text": "Kafka consumer group partition rebalance storm causing extreme message processing lag in notification-service.",
                "metadata": {
                    "title": "Kafka partition rebalancing storm",
                    "service": "notification-service",
                    "root_cause": "Synchronous email delivery exceeded max.poll.interval.ms (300s), causing broker to consider consumer dead and trigger rebalances.",
                    "verified_fix": "Decoupled message consumption from processing via internal async worker threadpool and increased max.poll.interval.ms to 600s.",
                    "caution_notes": "Avoid long synchronous network calls directly inside the Kafka message poll loop."
                }
            }
        ]

        for item in seed_data:
            self.index.add_document(item["id"], item["text"], item["metadata"])

    def recall(self, query_text: str, top_k: int = 3, threshold: float = 0.05) -> List[Dict[str, Any]]:
        return self.index.search_similar(query_text, top_k=top_k, threshold=threshold)

    def record_resolution(self, incident_id: str, title: str, description: str,
                          root_cause: str, action_taken: str, prevention_steps: Optional[str] = None) -> None:
        """Stores a newly verified resolution into the vector episodic memory."""
        combined_text = f"{title} {description} Root cause: {root_cause} Action: {action_taken} Prevention: {prevention_steps or ''}"
        metadata = {
            "title": title,
            "service": "production",
            "root_cause": root_cause,
            "verified_fix": action_taken,
            "caution_notes": prevention_steps
        }
        self.index.add_document(incident_id, combined_text, metadata)

    def count(self) -> int:
        return self.index.total_docs


# Global shared instance
memory_service = EpisodicMemoryService()
