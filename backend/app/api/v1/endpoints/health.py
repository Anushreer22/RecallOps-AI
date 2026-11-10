from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.schemas.incident import HealthResponse
from backend.app.services.memory_service import memory_service
from backend.app.services.triage_service import triage_service
from backend.app.services.topology_service import topology_service

router = APIRouter(tags=["Health & Status"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Returns application health, indexed memory count, active triage count, and topology nodes."""
    system_status = "healthy" if (memory_service.is_ready and not memory_service.last_error) else "degraded"
    return HealthResponse(
        status=system_status,
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        indexed_memories=memory_service.count(),
        active_triage_count=triage_service.count(),
        services_in_graph=topology_service.service_count()
    )
