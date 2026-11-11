from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    health,
    incidents,
    webhooks,
    investigations,
    auth,
    organizations,
    projects,
    services,
    topology,
    audit
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(projects.router)
api_router.include_router(services.router)
api_router.include_router(topology.router)
api_router.include_router(incidents.router)
api_router.include_router(webhooks.router)
api_router.include_router(investigations.router)
api_router.include_router(audit.router)
