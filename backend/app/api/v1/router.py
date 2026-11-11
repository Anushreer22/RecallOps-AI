from fastapi import APIRouter
from backend.app.api.v1.endpoints import incidents, health, webhooks, investigations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(incidents.router)
api_router.include_router(webhooks.router)
api_router.include_router(investigations.router)
