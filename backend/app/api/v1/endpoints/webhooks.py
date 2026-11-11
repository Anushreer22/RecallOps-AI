from typing import List, Optional
from fastapi import APIRouter, Request, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.webhook_service import webhook_service
from backend.app.services.deduplication_service import deduplication_service
from backend.app.schemas.webhook import WebhookIngestResponse, WebhookEventResponse

router = APIRouter(prefix="/webhooks", tags=["Webhooks & Ingestion"])


@router.post("/pagerduty", response_model=WebhookIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_pagerduty_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Ingests and normalizes PagerDuty webhook payloads (supporting v3 signatures & v2 legacy).
    Validates HMAC-SHA256 signature when configured and deduplicates via provider event ID.
    """
    raw_body = await request.body()
    headers = dict(request.headers)
    return webhook_service.process_webhook("pagerduty", raw_body, headers, db)


@router.post("/datadog", response_model=WebhookIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_datadog_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Ingests and normalizes Datadog webhook notifications.
    Validates custom security token and deduplicates via provider event ID.
    """
    raw_body = await request.body()
    headers = dict(request.headers)
    return webhook_service.process_webhook("datadog", raw_body, headers, db)


@router.post("/alertmanager", response_model=WebhookIngestResponse, status_code=status.HTTP_200_OK)
async def ingest_alertmanager_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Ingests and normalizes Prometheus Alertmanager v4 webhook payloads.
    Validates Bearer token authentication and unpacks grouped firing/resolved alerts.
    """
    raw_body = await request.body()
    headers = dict(request.headers)
    return webhook_service.process_webhook("alertmanager", raw_body, headers, db)


@router.get("/events", response_model=List[WebhookEventResponse])
def list_webhook_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    provider: Optional[str] = Query(None, description="Filter by provider: pagerduty, datadog, alertmanager"),
    status: Optional[str] = Query(None, description="Filter by status: PROCESSED, DUPLICATE, FAILED"),
    db: Session = Depends(get_db)
):
    """
    Lists received webhook audit events for observability and deduplication tracking.
    """
    return deduplication_service.list_events(db, skip=skip, limit=limit, provider=provider, status=status)
