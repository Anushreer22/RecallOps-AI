from typing import Optional, Dict, Any, List
from backend.app.models.incident import Incident
from backend.app.services.memory_service import memory_service
from backend.app.services.topology_service import topology_service
from backend.app.core.algorithms import ErrorSignatureTrie
from backend.app.core.config import settings
from backend.app.ai.schemas import EvidenceItem, EvidenceCollection


class EvidenceCollectionService:
    """
    Gathers, validates, and tags all multi-modal observability and memory evidence
    associated with an ongoing incident into a structured EvidenceCollection.
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

    def scan_logs_for_signatures(self, raw_logs: str) -> List[Dict[str, str]]:
        if not raw_logs:
            return []
        matches = self.trie.scan_log_line(raw_logs)
        return [{"token": token, "category": cat, "severity": sev} for token, cat, sev in matches]

    def collect_evidence(self, incident: Incident) -> EvidenceCollection:
        evidence = EvidenceCollection()

        # -------------------------------------------------------------------
        # 1. Incident Core Evidence
        # -------------------------------------------------------------------
        evidence.add(
            EvidenceItem(
                id="EVID-INC-INFO",
                source_type="incident",
                title=f"Incident Metadata: {incident.title}",
                content=(
                    f"Incident ID: {incident.id}\n"
                    f"Target Service: {incident.service_name} (Tier: {incident.service_tier})\n"
                    f"Severity: {incident.severity} | Current Status: {incident.status}\n"
                    f"Impacted Users: {incident.impacted_users}\n"
                    f"Reported Source: {incident.source}\n"
                    f"Summary Description: {incident.description}"
                ),
                metadata={
                    "incident_id": incident.id,
                    "service_name": incident.service_name,
                    "severity": incident.severity,
                    "tier": incident.service_tier,
                    "impacted_users": incident.impacted_users,
                }
            )
        )

        # -------------------------------------------------------------------
        # 2. Application Logs Evidence
        # -------------------------------------------------------------------
        if incident.raw_logs and incident.raw_logs.strip():
            # Scanned Trie Signatures
            signatures = self.scan_logs_for_signatures(incident.raw_logs)
            if signatures:
                sig_summary = ", ".join([f"{s['token']} ({s['category']}: {s['severity']})" for s in signatures])
                evidence.add(
                    EvidenceItem(
                        id="EVID-LOGS-SIGS",
                        source_type="logs",
                        title="Scanned Error Code Signatures",
                        content=f"Detected error patterns: {sig_summary}",
                        metadata={"signatures": signatures}
                    )
                )

            # Raw Log Extract (bounded to first 2000 chars to prevent prompt bloat)
            bounded_logs = incident.raw_logs[:2000]
            if len(incident.raw_logs) > 2000:
                bounded_logs += "\n... [LOGS TRUNCATED AT 2000 CHARACTERS] ..."

            evidence.add(
                EvidenceItem(
                    id="EVID-LOGS-RAW",
                    source_type="logs",
                    title="Application Error Logs",
                    content=bounded_logs,
                    metadata={"character_length": len(incident.raw_logs)}
                )
            )
        else:
            evidence.add(
                EvidenceItem(
                    id="EVID-LOGS-UNAVAIL",
                    source_type="telemetry_status",
                    title="Application Logs Unavailable",
                    content="No raw logs or stack traces were provided with this incident alert.",
                    metadata={"available": False}
                )
            )

        # -------------------------------------------------------------------
        # 3. Topology & Microservice Blast-Radius Evidence
        # -------------------------------------------------------------------
        blast_data = topology_service.get_blast_radius(incident.service_name)
        impacted_svcs = blast_data.get("impacted_services", [])
        total_impacted = blast_data.get("total_impacted_services", 0)
        max_depth = blast_data.get("max_depth", 0)

        topo_content = (
            f"Service Dependency Analysis for '{incident.service_name}':\n"
            f"Total Downstream Services Impacted: {total_impacted}\n"
            f"Maximum Downstream Dependency Depth: {max_depth} hops\n"
        )
        if impacted_svcs:
            svc_list = ", ".join([
                f"{s.get('service')} (hops: {s.get('hop_distance', 1)}, weight: {s.get('impact_weight', 1.0)})"
                for s in impacted_svcs
            ])
            topo_content += f"Downstream Impacted Services: {svc_list}"
        else:
            topo_content += "No downstream services depend on this service (Leaf node in dependency DAG)."

        evidence.add(
            EvidenceItem(
                id="EVID-TOPO-BLAST",
                source_type="topology",
                title=f"Microservice Blast Radius ({total_impacted} services)",
                content=topo_content,
                metadata={
                    "total_impacted": total_impacted,
                    "max_depth": max_depth,
                    "impacted_services": impacted_svcs
                }
            )
        )

        # -------------------------------------------------------------------
        # 4. Episodic Memory (Historical Verified Resolutions)
        # -------------------------------------------------------------------
        query_text = f"{incident.title} {incident.description} {incident.raw_logs or ''}"
        similar_outages = memory_service.recall(
            query_text,
            top_k=settings.MAX_HISTORICAL_RECALL,
            threshold=settings.SIMILARITY_THRESHOLD
        )

        if similar_outages:
            for idx, match in enumerate(similar_outages, 1):
                meta = match.get("metadata", {})
                hist_id = match.get("incident_id")
                sim_score = match.get("similarity_score", 0.0)

                evidence.add(
                    EvidenceItem(
                        id=f"EVID-HIST-{idx}",
                        source_type="historical_resolution",
                        title=f"Historical Precedent: {meta.get('title', hist_id)} (Cosine Similarity: {sim_score:.4f})",
                        content=(
                            f"Historical Incident ID: {hist_id}\n"
                            f"Verified Root Cause: {meta.get('root_cause', 'Unknown')}\n"
                            f"Verified Action Taken: {meta.get('verified_fix', 'None recorded')}\n"
                            f"Prevention/Caution Notes: {meta.get('caution_notes', 'None recorded')}\n"
                            f"Verified By: {meta.get('verified_by', 'SRE')}"
                        ),
                        metadata={
                            "incident_id": hist_id,
                            "similarity_score": round(sim_score, 4),
                            "verified_by": meta.get("verified_by"),
                            "resolved_at": meta.get("resolved_at")
                        }
                    )
                )
        else:
            evidence.add(
                EvidenceItem(
                    id="EVID-HIST-EMPTY",
                    source_type="historical_resolution",
                    title="No Relevant Historical Incidents Found",
                    content=(
                        f"Episodic vector memory search returned 0 matching historical incidents "
                        f"above cosine similarity threshold {settings.SIMILARITY_THRESHOLD}."
                    ),
                    metadata={"matches_count": 0}
                )
            )

        # -------------------------------------------------------------------
        # 5. Unavailable Telemetry (Metrics & Distributed Traces)
        # -------------------------------------------------------------------
        evidence.add(
            EvidenceItem(
                id="EVID-TELEM-METRICS",
                source_type="telemetry_status",
                title="Telemetry Status: Time-Series Metrics Unavailable",
                content="Fine-grained system metrics (CPU, Memory, Disk I/O, Network p99 latency) are not instrumented or unavailable.",
                metadata={"status": "UNAVAILABLE"}
            )
        )
        evidence.add(
            EvidenceItem(
                id="EVID-TELEM-TRACES",
                source_type="telemetry_status",
                title="Telemetry Status: Distributed Traces Unavailable",
                content="OpenTelemetry/Jaeger distributed trace spans and waterfall flamegraphs are not connected or unavailable.",
                metadata={"status": "UNAVAILABLE"}
            )
        )

        return evidence


evidence_service = EvidenceCollectionService()
