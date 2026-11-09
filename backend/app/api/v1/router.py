from fastapi import APIRouter
from backend.app.api.v1.endpoints import incidents, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(incidents.router)
