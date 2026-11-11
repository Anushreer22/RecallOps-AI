import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.ai.base import (
    LLMError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMResponseParsingError,
)
from backend.app.ai.registry import provider_registry
from backend.app.ai.schemas import (
    StructuredInvestigationReport,
    InvestigationResponse,
    InvestigationFeedbackCreate,
    InvestigationFeedbackResponse,
)
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.repositories.investigation_repository import InvestigationRepository
from backend.app.schemas.incident import ResolutionCreate
from backend.app.services.evidence_service import evidence_service
from backend.app.services.prompt_service import prompt_service
from backend.app.services.triage_service import triage_service
from backend.app.services.memory_service import memory_service


class InvestigationService:
    """
    Orchestrates the LLM incident investigation lifecycle:
    1. Evidence collection across incidents, logs, topology, and historical memory.
    2. Prompt construction with injection safeguards.
    3. LLM provider invocation.
    4. Evidence reference validation and anti-hallucination verification.
    5. Durable database persistence of investigation reports.
    6. Human engineer verification and feedback loop to episodic memory.
    """

    def investigate_incident(
        self,
        incident_id: str,
        db: Session,
        provider_name: Optional[str] = None
    ) -> InvestigationResponse:
        incident_repo = IncidentRepository(db)
        investigation_repo = InvestigationRepository(db)

        incident = incident_repo.get_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found."
            )

        # Transition status to INVESTIGATING if OPEN
        if incident.status == "OPEN":
            incident_repo.update_status(incident.id, "INVESTIGATING")

        # 1. Collect all available evidence
        evidence = evidence_service.collect_evidence(incident)

        # 2. Build injection-safe prompts
        system_prompt = prompt_service.system_prompt
        user_prompt = prompt_service.build_user_prompt(
            incident_id=incident.id,
            service_name=incident.service_name,
            title=incident.title,
            description=incident.description,
            severity=incident.severity,
            raw_logs=incident.raw_logs or "",
            evidence=evidence
        )

        # 3. Locate configured LLM provider
        try:
            provider = provider_registry.get(provider_name)
        except LLMConfigurationError as conf_err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(conf_err)
            )

        # 4. Create initial pending Investigation record
        investigation = investigation_repo.create(
            incident_id=incident.id,
            organization_id=incident.organization_id,
            provider=provider.provider_name,
            model_name=provider.model_name,
            status="PENDING",
            summary="Investigation underway..."
        )

        # 5. Invoke LLM Provider with error handling
        try:
            report: StructuredInvestigationReport = provider.generate_investigation(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                evidence=evidence
            )
        except LLMConfigurationError as exc:
            investigation_repo.update_status(
                investigation.id,
                status="FAILED",
                error_message=f"Configuration Error: {str(exc)}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM provider is not configured: {str(exc)}"
            )
        except LLMAuthenticationError as exc:
            investigation_repo.update_status(
                investigation.id,
                status="FAILED",
                error_message=f"Authentication Error: {str(exc)}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM authentication failed: {str(exc)}"
            )
        except LLMTimeoutError as exc:
            investigation_repo.update_status(
                investigation.id,
                status="FAILED",
                error_message=f"Timeout Error: {str(exc)}"
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"LLM provider timed out during investigation: {str(exc)}"
            )
        except LLMResponseParsingError as exc:
            investigation_repo.update_status(
                investigation.id,
                status="FAILED",
                error_message=f"Parsing Error: {str(exc)}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM returned invalid or malformed investigation response: {str(exc)}"
            )
        except LLMError as exc:
            investigation_repo.update_status(
                investigation.id,
                status="FAILED",
                error_message=f"Provider Error: {str(exc)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM provider encountered an error: {str(exc)}"
            )
        except Exception as exc:
            investigation_repo.update_status(
                investigation.id,
                status="FAILED",
                error_message=f"Unexpected Error: {str(exc)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected failure during AI investigation: {str(exc)}"
            )

        # 6. Evidence Grounding & Anti-Hallucination Validation
        valid_evidence_ids = evidence.all_ids()
        hallucinated_ids = []

        for cause in report.probable_root_causes:
            # Check supporting evidence IDs
            clean_supporting = []
            for eid in cause.supporting_evidence_ids:
                if eid in valid_evidence_ids:
                    clean_supporting.append(eid)
                else:
                    hallucinated_ids.append(eid)
            cause.supporting_evidence_ids = clean_supporting

            # Check contradicting evidence IDs
            clean_contradicting = []
            for eid in cause.contradicting_evidence_ids:
                if eid in valid_evidence_ids:
                    clean_contradicting.append(eid)
                else:
                    hallucinated_ids.append(eid)
            cause.contradicting_evidence_ids = clean_contradicting

        if hallucinated_ids:
            report.hallucinated_evidence_ids = list(set(hallucinated_ids))
            report.evidence_gaps.append(
                f"Grounding Alert: LLM referenced invalid/hallucinated evidence IDs: {report.hallucinated_evidence_ids}"
            )
            report.requires_human_review = True

        # 7. Persist completed report to database
        updated_inv = investigation_repo.update_status(
            investigation_id=investigation.id,
            status="COMPLETED",
            summary=report.summary,
            structured_result=report.model_dump_json()
        )

        return InvestigationResponse(
            id=updated_inv.id,
            incident_id=updated_inv.incident_id,
            provider=updated_inv.provider,
            model_name=updated_inv.model_name,
            status=updated_inv.status,
            summary=updated_inv.summary,
            report=report,
            created_at=updated_inv.created_at,
            completed_at=updated_inv.completed_at,
            error_message=updated_inv.error_message
        )

    def list_investigations(
        self,
        incident_id: str,
        db: Session,
        skip: int = 0,
        limit: int = 50
    ) -> List[InvestigationResponse]:
        incident_repo = IncidentRepository(db)
        incident = incident_repo.get_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found."
            )

        investigation_repo = InvestigationRepository(db)
        inv_list = investigation_repo.list_by_incident(incident_id, skip=skip, limit=limit)

        responses = []
        for inv in inv_list:
            report = None
            if inv.structured_result:
                try:
                    report = StructuredInvestigationReport.model_validate_json(inv.structured_result)
                except Exception:
                    report = None

            responses.append(
                InvestigationResponse(
                    id=inv.id,
                    incident_id=inv.incident_id,
                    provider=inv.provider,
                    model_name=inv.model_name,
                    status=inv.status,
                    summary=inv.summary,
                    report=report,
                    created_at=inv.created_at,
                    completed_at=inv.completed_at,
                    error_message=inv.error_message
                )
            )
        return responses

    def get_investigation(
        self,
        investigation_id: str,
        db: Session
    ) -> InvestigationResponse:
        investigation_repo = InvestigationRepository(db)
        inv = investigation_repo.get_by_id(investigation_id)
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation '{investigation_id}' not found."
            )

        report = None
        if inv.structured_result:
            try:
                report = StructuredInvestigationReport.model_validate_json(inv.structured_result)
            except Exception:
                report = None

        return InvestigationResponse(
            id=inv.id,
            incident_id=inv.incident_id,
            provider=inv.provider,
            model_name=inv.model_name,
            status=inv.status,
            summary=inv.summary,
            report=report,
            created_at=inv.created_at,
            completed_at=inv.completed_at,
            error_message=inv.error_message
        )

    def handle_feedback(
        self,
        investigation_id: str,
        feedback: InvestigationFeedbackCreate,
        db: Session
    ) -> InvestigationFeedbackResponse:
        investigation_repo = InvestigationRepository(db)
        incident_repo = IncidentRepository(db)

        inv = investigation_repo.get_by_id(investigation_id)
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation '{investigation_id}' not found."
            )

        incident = incident_repo.get_by_id(inv.incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{inv.incident_id}' not found."
            )

        if not feedback.verified_by or not feedback.verified_by.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Engineer verification identifier ('verified_by') is strictly required."
            )

        report: Optional[StructuredInvestigationReport] = None
        if inv.structured_result:
            try:
                report = StructuredInvestigationReport.model_validate_json(inv.structured_result)
            except Exception:
                report = None

        if feedback.approved:
            # SRE has approved the proposed or corrected resolution
            root_cause = feedback.root_cause
            if not root_cause:
                if report and report.probable_root_causes:
                    root_cause = report.probable_root_causes[0].hypothesis
                else:
                    root_cause = "Approved automated investigation resolution"

            action_taken = feedback.action_taken
            if not action_taken:
                if report and report.suggested_resolution:
                    action_taken = "\n".join(report.suggested_resolution)
                else:
                    action_taken = "Remediated based on AI investigation findings"

            prevention_steps = feedback.prevention_steps
            if not prevention_steps and report and report.suggested_investigation_steps:
                prevention_steps = report.suggested_investigation_steps[0]

            # 1. Resolve incident in database
            resolution_create = ResolutionCreate(
                root_cause=root_cause,
                action_taken=action_taken,
                prevention_steps=prevention_steps,
                verified_by=feedback.verified_by
            )
            db_res = incident_repo.resolve(incident.id, resolution_create)

            # 2. Dequeue from triage queue
            triage_service.remove(incident.id)

            # 3. Persist into Episodic Memory (ONLY human-approved resolutions enter memory)
            memory_service.record_resolution(
                incident_id=incident.id,
                title=incident.title,
                description=incident.description,
                service_name=incident.service_name,
                root_cause=root_cause,
                action_taken=action_taken,
                prevention_steps=prevention_steps,
                raw_logs=incident.raw_logs,
                verified_by=feedback.verified_by
            )

            return InvestigationFeedbackResponse(
                investigation_id=inv.id,
                incident_id=incident.id,
                approved=True,
                verified_by=feedback.verified_by,
                memory_indexed=True,
                resolution_id=db_res.id if db_res else None,
                incident_status="RESOLVED",
                message=f"Investigation {inv.id} approved by {feedback.verified_by}. Incident resolved and resolution indexed into episodic memory."
            )

        else:
            # SRE rejected the AI investigation recommendations
            # Do NOT resolve incident
            # Do NOT index into episodic memory
            rejection_note = feedback.notes or "Rejected by engineer during human review."
            investigation_repo.update_status(
                investigation_id=inv.id,
                status=inv.status,
                error_message=f"Engineer Review Note: {rejection_note}"
            )

            return InvestigationFeedbackResponse(
                investigation_id=inv.id,
                incident_id=incident.id,
                approved=False,
                verified_by=feedback.verified_by,
                memory_indexed=False,
                resolution_id=None,
                incident_status=incident.status,
                message=f"Investigation {inv.id} rejected by {feedback.verified_by}. No episodic memory created. Incident remains {incident.status}."
            )


investigation_service = InvestigationService()
