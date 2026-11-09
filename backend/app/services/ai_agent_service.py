from datetime import datetime, timezone
from typing import Dict, Any, List
from backend.app.core.algorithms import ErrorSignatureTrie
from backend.app.services.memory_service import memory_service
from backend.app.services.topology_service import topology_service
from backend.app.schemas.incident import DiagnosisResponse, HistoricalRecallMatch, BlastRadiusSummary


class IncidentAIAgent:
    """
    Autonomous Incident Diagnostic Agent that synthesizes:
    1. Error signature tokenization via Trie
    2. Topological blast-radius graph traversal
    3. Episodic historical incident memory recall
    4. Structured hypothesis and runbook generation
    """

    def __init__(self):
        self.trie = ErrorSignatureTrie()
        self._seed_trie_patterns()

    def _seed_trie_patterns(self):
        patterns = [
            ("err_500", "SERVER_ERROR", "HIGH"),
            ("err_503", "SERVICE_UNAVAILABLE", "CRITICAL"),
            ("err_504", "GATEWAY_TIMEOUT", "CRITICAL"),
            ("oom_killed", "MEMORY_EXHAUSTION", "CRITICAL"),
            ("connection_timeout", "NETWORK_PARTITION", "HIGH"),
            ("pool_exhausted", "RESOURCE_STARVATION", "CRITICAL"),
            ("deadlock", "CONCURRENCY_CONFLICT", "HIGH"),
            ("rate_limit", "THROTTLING", "MEDIUM"),
            ("dns_timeout", "NAME_RESOLUTION_FAILURE", "HIGH"),
            ("circuit_breaker_open", "CASCADE_PROTECTION", "HIGH")
        ]
        for pattern, category, severity in patterns:
            self.trie.insert(pattern, category, severity)

    def scan_logs(self, raw_logs: str) -> List[Dict[str, str]]:
        if not raw_logs:
            return []
        matches = self.trie.scan_log_line(raw_logs)
        return [
            {"token": token, "category": cat, "severity": sev}
            for token, cat, sev in matches
        ]

    def diagnose(self, incident_id: str, title: str, description: str,
                 service_name: str, raw_logs: str = "") -> DiagnosisResponse:
        # Step 1: Scan logs for known error signatures
        detected_signatures = self.scan_logs(raw_logs or f"{title} {description}")

        # Step 2: Traverse dependency graph for blast radius
        blast_data = topology_service.get_blast_radius(service_name)
        blast_summary = BlastRadiusSummary(
            origin_service=blast_data["origin_service"],
            total_impacted_services=blast_data["total_impacted_services"],
            impacted_services=blast_data["impacted_services"],
            max_depth=blast_data["max_depth"]
        )

        # Step 3: Recall historical incidents from episodic memory
        query_text = f"{title} {description} {raw_logs or ''}"
        similar_incidents = memory_service.recall(query_text, top_k=3, threshold=0.04)

        historical_matches: List[HistoricalRecallMatch] = []
        for match in similar_incidents:
            meta = match["metadata"]
            historical_matches.append(
                HistoricalRecallMatch(
                    incident_id=match["incident_id"],
                    similarity_score=match["similarity_score"],
                    title=meta.get("title", match["incident_id"]),
                    root_cause=meta.get("root_cause"),
                    verified_fix=meta.get("verified_fix"),
                    caution_notes=meta.get("caution_notes")
                )
            )

        # Step 4: Synthesize root cause hypothesis and remediation plan
        if historical_matches:
            top_match = historical_matches[0]
            confidence = min(0.95, max(0.65, top_match.similarity_score * 1.5))
            hypothesized_cause = (
                f"High-confidence correlation with historical incident '{top_match.title}'. "
                f"Probable root cause: {top_match.root_cause}"
            )
            runbook_steps = [
                f"1. Immediate Containment: {top_match.verified_fix}",
                f"2. Inspect impacted downstream dependencies: {', '.join([s['service'] for s in blast_summary.impacted_services]) if blast_summary.impacted_services else 'No downstream dependencies detected.'}",
                f"3. Verify error signature resolution against active log stream.",
                f"4. If symptoms persist after 5 minutes, initiate failover to standby replica."
            ]
            cautions = [
                top_match.caution_notes or "Avoid ad-hoc manual database alterations without peer sign-off.",
                "Ensure circuit breaker metrics are monitored during rollout."
            ]
        else:
            confidence = 0.55
            hypothesized_cause = (
                f"Novel anomaly in {service_name}. Detected signature categories: "
                f"{[s['category'] for s in detected_signatures] if detected_signatures else 'Uncategorized anomaly'}. "
                f"No close historical matches found in episodic memory."
            )
            runbook_steps = [
                f"1. Isolate {service_name} traffic by draining 50% of ingress requests.",
                f"2. Capture thread dump and heap profiler snapshot before pod recycling.",
                f"3. Check upstream dependencies and downstream blast radius ({blast_summary.total_impacted_services} services impacted).",
                f"4. Once resolved, submit resolution to RecallOps to train episodic memory for future recall."
            ]
            cautions = [
                "Proceed with caution: Unverified remediation steps may cause cascading restarts in downstream tiers."
            ]

        return DiagnosisResponse(
            incident_id=incident_id,
            detected_signatures=detected_signatures,
            blast_radius=blast_summary,
            historical_matches=historical_matches,
            hypothesized_root_cause=hypothesized_cause,
            recommended_runbook_steps=runbook_steps,
            cautions_and_anti_patterns=cautions,
            confidence_score=round(confidence, 2),
            ai_generated_at=datetime.now(timezone.utc)
        )


# Global shared instance
ai_agent = IncidentAIAgent()
