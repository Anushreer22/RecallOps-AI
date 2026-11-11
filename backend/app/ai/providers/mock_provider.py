from typing import Optional, List
from backend.app.ai.base import (
    BaseLLMProvider,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMResponseParsingError,
)
from backend.app.ai.schemas import (
    StructuredInvestigationReport,
    ProbableRootCause,
    EvidenceCollection,
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for automated unit and integration testing.
    Can be configured to simulate timeouts, authentication failures, malformed outputs,
    and grounded vs hallucinated evidence citations.
    """

    def __init__(
        self,
        model_name: str = "mock-gpt-4o",
        is_configured: bool = True,
        simulate_timeout: bool = False,
        simulate_auth_failure: bool = False,
        simulate_malformed_json: bool = False,
        simulate_schema_failure: bool = False,
        simulate_hallucinated_evidence: bool = False,
        simulate_contradicting_evidence: bool = False,
        custom_report: Optional[StructuredInvestigationReport] = None
    ):
        self._model_name = model_name
        self.is_configured = is_configured
        self.simulate_timeout = simulate_timeout
        self.simulate_auth_failure = simulate_auth_failure
        self.simulate_malformed_json = simulate_malformed_json
        self.simulate_schema_failure = simulate_schema_failure
        self.simulate_hallucinated_evidence = simulate_hallucinated_evidence
        self.simulate_contradicting_evidence = simulate_contradicting_evidence
        self.custom_report = custom_report

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return self.is_configured

    def validate_configuration(self) -> None:
        if not self.is_configured:
            raise LLMConfigurationError("Mock LLM provider is not configured.")

    def generate_investigation(
        self,
        system_prompt: str,
        user_prompt: str,
        evidence: EvidenceCollection,
        temperature: Optional[float] = None
    ) -> StructuredInvestigationReport:
        self.validate_configuration()

        if self.simulate_auth_failure:
            raise LLMAuthenticationError("Mock provider simulated 401 Unauthorized API key error.")

        if self.simulate_timeout:
            raise LLMTimeoutError("Mock provider simulated API request timeout after 30s.")

        if self.simulate_malformed_json:
            raise LLMResponseParsingError("Mock provider simulated malformed JSON: Expecting property name enclosed in double quotes.")

        if self.simulate_schema_failure:
            raise LLMResponseParsingError("Mock provider simulated schema failure: 'probable_root_causes' missing required field 'hypothesis'.")

        if self.custom_report:
            return self.custom_report

        # Extract real evidence IDs from collection
        available_ids = list(evidence.all_ids())

        # Determine supporting IDs
        if self.simulate_hallucinated_evidence:
            supporting_ids = ["EVID-HALLUCINATED-999", "EVID-FAKE-XYZ"]
            contradicting_ids = ["EVID-NONEXISTENT-404"]
        else:
            # Pick available IDs
            supporting_ids = [eid for eid in available_ids if "INC" in eid or "LOG" in eid or "HIST" in eid][:3]
            contradicting_ids = [eid for eid in available_ids if "TOPO" in eid][:1] if self.simulate_contradicting_evidence else []

        # Find historical references
        hist_incidents = []
        for item in evidence.items:
            if item.source_type == "historical_resolution":
                hist_incidents.append(item.metadata.get("incident_id", item.id))

        incident_id = "UNKNOWN-INC"
        for item in evidence.items:
            if item.source_type == "incident":
                incident_id = item.metadata.get("incident_id", "INC-001")
                break

        # If no meaningful evidence exists
        if not available_ids or all(item.source_type == "telemetry_status" for item in evidence.items):
            return StructuredInvestigationReport(
                incident_id=incident_id,
                summary="Insufficient evidence available to determine root cause with confidence.",
                probable_root_causes=[
                    ProbableRootCause(
                        hypothesis="Unspecified operational anomaly due to absence of telemetry and logs.",
                        confidence_score=0.1,
                        supporting_evidence_ids=[],
                        contradicting_evidence_ids=[],
                        reasoning="No application logs, error traces, or metric spikes were provided for analysis."
                    )
                ],
                observed_facts=["Incident alert registered without telemetry."],
                evidence_gaps=["Application logs unavailable", "Metrics unavailable", "Traces unavailable"],
                suggested_investigation_steps=[
                    "Check host agent health and metric collection daemons.",
                    "Review centralized logging pipeline for ingestion lag."
                ],
                suggested_resolution=[
                    "Verify service health via manual ping before taking disruptive actions."
                ],
                related_historical_incidents=[],
                requires_human_review=True
            )

        return StructuredInvestigationReport(
            incident_id=incident_id,
            summary="Automated investigation grounded in collected system logs and historical resolution memory.",
            probable_root_causes=[
                ProbableRootCause(
                    hypothesis="Database connection pool saturation triggered by unclosed client sessions under elevated load.",
                    confidence_score=0.85,
                    supporting_evidence_ids=supporting_ids,
                    contradicting_evidence_ids=contradicting_ids,
                    reasoning="Scanned error signatures match resource exhaustion patterns observed in previous verified outages."
                )
            ],
            observed_facts=[
                f"Observed in evidence: {evidence.items[0].title if evidence.items else 'Incident details'}"
            ],
            evidence_gaps=[
                "Database query execution latency metrics unavailable",
                "Distributed trace spans unavailable"
            ],
            suggested_investigation_steps=[
                "Execute 'SHOW max_connections' and inspect pg_stat_activity connection counts.",
                "Verify whether PgBouncer connection pooler is saturated."
            ],
            suggested_resolution=[
                "Deploy PgBouncer pooler or scale replicas with properly closed DB session context managers."
            ],
            related_historical_incidents=hist_incidents,
            requires_human_review=True
        )
