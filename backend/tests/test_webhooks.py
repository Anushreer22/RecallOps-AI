import concurrent.futures
import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.db.base import Base
import backend.app.models
from backend.app.models.incident import Incident
from backend.app.models.webhook_event import WebhookEvent
from backend.app.services.webhook_service import webhook_service
from backend.app.services.deduplication_service import deduplication_service
from backend.app.services.triage_service import triage_service
from backend.app.services.memory_service import memory_service
from backend.app.integrations.base import redact_sensitive_data
from backend.app.integrations.registry import adapter_registry
from backend.app.integrations.pagerduty.security import verify_pagerduty_signature
from backend.app.integrations.datadog.security import verify_datadog_token
from backend.app.integrations.alertmanager.security import verify_alertmanager_auth
from backend.app.api.v1.endpoints.webhooks import list_webhook_events


# Isolated SQLite test engine for webhook tests (StaticPool ensures threads share database)
webhook_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
WebhookTestSession = sessionmaker(autocommit=False, autoflush=False, bind=webhook_test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_webhook_test_db():
    Base.metadata.create_all(bind=webhook_test_engine)
    yield
    Base.metadata.drop_all(bind=webhook_test_engine)


@pytest.fixture
def db():
    session = WebhookTestSession()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 1. PagerDuty Tests
# ---------------------------------------------------------------------------

def test_pagerduty_v3_triggered_flow(db, monkeypatch):
    secret = "pd_secret_key_123"
    monkeypatch.setattr(settings, "PAGERDUTY_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    payload = {
        "event": {
            "id": "PD_EVT_001",
            "event_type": "incident.triggered",
            "resource_type": "incident",
            "occurred_at": "2026-11-10T12:00:00Z",
            "data": {
                "id": "PD_INC_1001",
                "incident_key": "srv-auth-db-pool",
                "title": "Auth DB Pool Saturated",
                "urgency": "high",
                "service": {"name": "auth-service"},
                "body": {"details": "Max connections reached on primary database"}
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    headers = {"X-PagerDuty-Signature": f"v1={sig}", "Content-Type": "application/json"}

    resp = webhook_service.process_webhook("pagerduty", raw_body, headers, db)

    assert resp.provider == "pagerduty"
    assert resp.events_count == 1
    assert resp.processed_count == 1
    assert resp.duplicate_count == 0
    assert resp.results[0].already_processed is False
    assert resp.results[0].status == "PROCESSED"
    created_id = resp.results[0].internal_incident_id
    assert created_id is not None

    # Verify incident in DB
    inc = db.query(Incident).filter(Incident.id == created_id).first()
    assert inc is not None
    assert inc.service_name == "auth-service"
    assert inc.status == "OPEN"
    assert inc.severity == "CRITICAL"


def test_pagerduty_v3_lifecycle_ack_and_resolve(db, monkeypatch):
    secret = "pd_secret_key_123"
    monkeypatch.setattr(settings, "PAGERDUTY_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    # 1. Triggered
    trig_payload = {
        "event": {
            "id": "PD_EVT_LIFECYCLE_1",
            "event_type": "incident.triggered",
            "data": {
                "id": "PD_INC_2002",
                "incident_key": "srv-payment-timeout",
                "title": "Payment API Gateway 504",
                "urgency": "high",
                "service": {"name": "payment-service"}
            }
        }
    }
    raw_trig = json.dumps(trig_payload).encode("utf-8")
    sig_trig = hmac.new(secret.encode("utf-8"), raw_trig, hashlib.sha256).hexdigest()
    resp1 = webhook_service.process_webhook(
        "pagerduty", raw_trig, {"X-PagerDuty-Signature": f"v1={sig_trig}"}, db
    )
    internal_id = resp1.results[0].internal_incident_id

    # 2. Acknowledged
    ack_payload = {
        "event": {
            "id": "PD_EVT_LIFECYCLE_2",
            "event_type": "incident.acknowledged",
            "data": {
                "id": "PD_INC_2002",
                "incident_key": "srv-payment-timeout",
                "title": "Payment API Gateway 504",
                "service": {"name": "payment-service"}
            }
        }
    }
    raw_ack = json.dumps(ack_payload).encode("utf-8")
    sig_ack = hmac.new(secret.encode("utf-8"), raw_ack, hashlib.sha256).hexdigest()
    resp2 = webhook_service.process_webhook(
        "pagerduty", raw_ack, {"X-PagerDuty-Signature": f"v1={sig_ack}"}, db
    )
    assert resp2.results[0].internal_incident_id == internal_id

    inc_ack = db.query(Incident).filter(Incident.id == internal_id).first()
    assert inc_ack.status == "INVESTIGATING"

    # 3. Resolved
    res_payload = {
        "event": {
            "id": "PD_EVT_LIFECYCLE_3",
            "event_type": "incident.resolved",
            "data": {
                "id": "PD_INC_2002",
                "incident_key": "srv-payment-timeout",
                "title": "Payment API Gateway 504",
                "service": {"name": "payment-service"}
            }
        }
    }
    raw_res = json.dumps(res_payload).encode("utf-8")
    sig_res = hmac.new(secret.encode("utf-8"), raw_res, hashlib.sha256).hexdigest()
    resp3 = webhook_service.process_webhook(
        "pagerduty", raw_res, {"X-PagerDuty-Signature": f"v1={sig_res}"}, db
    )
    assert resp3.results[0].internal_incident_id == internal_id

    inc_res = db.query(Incident).filter(Incident.id == internal_id).first()
    assert inc_res.status == "RESOLVED"
    # Scenario 1 verification: resolved webhook must NOT create a human-verified IncidentResolution
    assert inc_res.resolution is None


def test_pagerduty_v2_legacy_payload(db, monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)
    monkeypatch.setattr(settings, "PAGERDUTY_WEBHOOK_SECRET", None)

    v2_payload = {
        "messages": [
            {
                "id": "PD_MSG_V2_100",
                "event": "incident.trigger",
                "created_on": "2026-11-10T12:30:00Z",
                "incident": {
                    "id": "PD_INC_V2_1",
                    "incident_number": 99,
                    "title": "CoreDNS service degraded",
                    "urgency": "low",
                    "status": "triggered",
                    "service": {"name": "coredns"}
                }
            }
        ]
    }
    raw_body = json.dumps(v2_payload).encode("utf-8")
    resp = webhook_service.process_webhook("pagerduty", raw_body, {}, db)
    assert resp.events_count == 1
    assert resp.results[0].event_id == "PD_MSG_V2_100"
    assert resp.results[0].status == "PROCESSED"


def test_pagerduty_signature_verification_failure(db, monkeypatch):
    monkeypatch.setattr(settings, "PAGERDUTY_WEBHOOK_SECRET", "super_secret")
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    raw_body = json.dumps({"event": {"id": "bad_sig", "event_type": "incident.triggered", "data": {"title": "X"}}}).encode("utf-8")
    headers = {"X-PagerDuty-Signature": "v1=bad_hash_hex"}

    with pytest.raises(HTTPException) as exc_info:
        webhook_service.process_webhook("pagerduty", raw_body, headers, db)
    assert exc_info.value.status_code == 401


def test_pagerduty_key_rotation_support():
    secret = "key_active_v2"
    body = b'{"hello": "world"}'
    valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    # Comma-separated signatures indicating key rotation
    sig_header = f"v1=stale_sig_12345,v1={valid_sig}"
    assert verify_pagerduty_signature(body, {"X-PagerDuty-Signature": sig_header}, secret) is True


# ---------------------------------------------------------------------------
# 2. Datadog Tests
# ---------------------------------------------------------------------------

def test_datadog_webhook_ingestion(db, monkeypatch):
    token = "datadog_secret_token_abc"
    monkeypatch.setattr(settings, "DATADOG_WEBHOOK_TOKEN", token)
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    payload = {
        "id": "DD_EVT_1001",
        "alert_id": 888999,
        "title": "[Triggered] High CPU on auth-service",
        "body": "CPU reached 94% across 8 replicas",
        "date": 1762776000,
        "tags": ["service:auth-service", "env:production", "team:core"],
        "alert_type": "error",
        "alert_transition": "Triggered"
    }
    raw_body = json.dumps(payload).encode("utf-8")
    headers = {
        "X-Datadog-Webhook-Token": token,
        "Content-Type": "application/json"
    }

    resp = webhook_service.process_webhook("datadog", raw_body, headers, db)

    assert resp.provider == "datadog"
    assert resp.events_count == 1
    assert resp.processed_count == 1
    assert resp.results[0].already_processed is False

    inc = db.query(Incident).filter(Incident.id == resp.results[0].internal_incident_id).first()
    assert inc is not None
    assert inc.service_name == "auth-service"
    assert inc.severity == "CRITICAL"


def test_datadog_auth_bearer_token(db, monkeypatch):
    token = "dd_bearer_token_xyz"
    monkeypatch.setattr(settings, "DATADOG_WEBHOOK_TOKEN", token)
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    payload = {
        "id": "DD_EVT_1002",
        "alert_id": 888111,
        "title": "Memory leak detected",
        "tags": ["service:order-service"],
        "alert_type": "warning",
        "alert_transition": "Warn"
    }
    raw_body = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}"}

    resp = webhook_service.process_webhook("datadog", raw_body, headers, db)
    assert resp.processed_count == 1


def test_datadog_unauthorized(db, monkeypatch):
    monkeypatch.setattr(settings, "DATADOG_WEBHOOK_TOKEN", "expected_token")
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    raw_body = json.dumps({"title": "Test"}).encode("utf-8")
    headers = {"X-Datadog-Webhook-Token": "wrong_token"}

    with pytest.raises(HTTPException) as exc_info:
        webhook_service.process_webhook("datadog", raw_body, headers, db)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# 3. Prometheus Alertmanager Tests
# ---------------------------------------------------------------------------

def test_alertmanager_ingestion_with_grouped_alerts(db, monkeypatch):
    token = "am_secret_token_789"
    monkeypatch.setattr(settings, "ALERTMANAGER_WEBHOOK_TOKEN", token)
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    payload = {
        "version": "4",
        "groupKey": "{}:{alertname=\"HighErrorRate\"}",
        "status": "firing",
        "receiver": "recallops-webhook",
        "commonLabels": {
            "alertname": "HighErrorRate",
            "service": "payment-service",
            "severity": "critical"
        },
        "commonAnnotations": {
            "summary": "5xx rate exceeding 5% threshold"
        },
        "alerts": [
            {
                "status": "firing",
                "labels": {"instance": "pod-1", "severity": "critical"},
                "annotations": {"description": "pod-1 error rate 8.2%"},
                "fingerprint": "fp_pod_1",
                "startsAt": "2026-11-10T14:00:00Z"
            },
            {
                "status": "firing",
                "labels": {"instance": "pod-2", "severity": "critical"},
                "annotations": {"description": "pod-2 error rate 6.5%"},
                "fingerprint": "fp_pod_2",
                "startsAt": "2026-11-10T14:01:00Z"
            }
        ]
    }

    raw_body = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    resp = webhook_service.process_webhook("alertmanager", raw_body, headers, db)

    assert resp.provider == "alertmanager"
    assert resp.events_count == 2
    assert resp.processed_count == 2
    assert resp.duplicate_count == 0


def test_alertmanager_version_variations(db, monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)
    payload_int = {
        "version": 4,
        "status": "firing",
        "commonLabels": {"service": "test-svc", "alertname": "TestAlert"},
        "alerts": []
    }
    raw_body = json.dumps(payload_int).encode("utf-8")
    resp = webhook_service.process_webhook("alertmanager", raw_body, {}, db)
    assert resp.events_count == 1
    assert resp.processed_count == 1


def test_alertmanager_unauthorized(db, monkeypatch):
    monkeypatch.setattr(settings, "ALERTMANAGER_WEBHOOK_TOKEN", "valid_am_token")
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", True)

    raw_body = json.dumps({"alerts": []}).encode("utf-8")
    headers = {"Authorization": "Bearer invalid_token"}

    with pytest.raises(HTTPException) as exc_info:
        webhook_service.process_webhook("alertmanager", raw_body, headers, db)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# 4. Critical Reliability Scenarios
# ---------------------------------------------------------------------------

def test_scenario_1_resolved_webhook_never_creates_verified_resolution_or_memory(db, monkeypatch):
    """
    Scenario 1: A resolved webhook must never automatically create a
    human-verified resolution or trusted episodic memory.
    """
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)
    monkeypatch.setattr(settings, "PAGERDUTY_WEBHOOK_SECRET", None)

    # Triggered
    trig = {
        "event": {
            "id": "PD_SCENARIO_1_TRIG",
            "event_type": "incident.triggered",
            "data": {
                "id": "PD_SCENARIO_1_INC",
                "incident_key": "scenario-1-key",
                "title": "Auth API Outage",
                "service": {"name": "auth-service"}
            }
        }
    }
    webhook_service.process_webhook("pagerduty", json.dumps(trig).encode("utf-8"), {}, db)

    # Resolved via webhook
    res = {
        "event": {
            "id": "PD_SCENARIO_1_RES",
            "event_type": "incident.resolved",
            "data": {
                "id": "PD_SCENARIO_1_INC",
                "incident_key": "scenario-1-key",
                "title": "Auth API Outage",
                "service": {"name": "auth-service"}
            }
        }
    }
    webhook_service.process_webhook("pagerduty", json.dumps(res).encode("utf-8"), {}, db)

    inc = db.query(Incident).filter(Incident.incident_key == "scenario-1-key").first()
    assert inc is not None
    assert inc.status == "RESOLVED"
    # MUST NOT create IncidentResolution
    assert inc.resolution is None

    # Memory service rehydration from DB must NOT index this resolved alert as trusted memory
    memory_service.clear()
    count = memory_service.rehydrate_from_db(db)
    assert count == 0
    matches = memory_service.recall("Auth API Outage")
    assert len(matches) == 0


def test_scenario_2_concurrent_deliveries_same_event_id(db, monkeypatch):
    """
    Scenario 2: Concurrent deliveries with the same provider_event_id must
    produce exactly one processed event.
    """
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)
    payload = {
        "event": {
            "id": "CONCURRENT_EVT_SAME_ID_999",
            "event_type": "incident.triggered",
            "data": {
                "id": "PD_INC_CONCURRENT_1",
                "incident_key": "concurrent-same-id-key",
                "title": "Concurrent Delivery Test",
                "service": {"name": "cart-service"}
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")

    def run_delivery():
        session = WebhookTestSession()
        try:
            return webhook_service.process_webhook("pagerduty", raw_body, {}, session)
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_delivery) for _ in range(5)]
        responses = [f.result() for f in futures]

    processed_sum = sum(r.processed_count for r in responses)
    duplicate_sum = sum(r.duplicate_count for r in responses)

    assert processed_sum == 1
    assert duplicate_sum == 4

    # Verify database has exactly 1 incident and 1 WebhookEvent record
    inc_count = db.query(Incident).filter(Incident.incident_key == "concurrent-same-id-key").count()
    assert inc_count == 1
    event_count = db.query(WebhookEvent).filter(WebhookEvent.provider_event_id == "CONCURRENT_EVT_SAME_ID_999").count()
    assert event_count == 1


def test_scenario_3_lifecycle_events_same_incident_key(db, monkeypatch):
    """
    Scenario 3: Different lifecycle events sharing the same incident_key
    must update the same incident.
    """
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)

    for evt_id, evt_type, expected_status in [
        ("EVT_CYCLE_1", "incident.triggered", "OPEN"),
        ("EVT_CYCLE_2", "incident.acknowledged", "INVESTIGATING"),
        ("EVT_CYCLE_3", "incident.resolved", "RESOLVED"),
    ]:
        body = json.dumps({
            "event": {
                "id": evt_id,
                "event_type": evt_type,
                "data": {
                    "id": "INC_LIFECYCLE_SHARE",
                    "incident_key": "shared-lifecycle-key",
                    "title": "Shared Lifecycle Outage",
                    "service": {"name": "billing-service"}
                }
            }
        }).encode("utf-8")
        resp = webhook_service.process_webhook("pagerduty", body, {}, db)
        assert resp.processed_count == 1

        inc = db.query(Incident).filter(Incident.incident_key == "shared-lifecycle-key").first()
        assert inc.status == expected_status

    # Ensure total incidents for this key is exactly 1
    total_incs = db.query(Incident).filter(Incident.incident_key == "shared-lifecycle-key").count()
    assert total_incs == 1


def test_scenario_4_concurrent_first_time_events_same_incident_key(db, monkeypatch):
    """
    Scenario 4: Concurrent first-time events sharing an incident_key
    must not create duplicate incidents.
    """
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)

    def run_concurrent_event(i: int):
        session = WebhookTestSession()
        try:
            body = json.dumps({
                "event": {
                    "id": f"CONCURRENT_FIRST_TIME_EVT_{i}",
                    "event_type": "incident.triggered",
                    "data": {
                        "id": f"PD_INC_C_{i}",
                        "incident_key": "concurrent-first-time-key",
                        "title": f"Concurrent Alert {i}",
                        "service": {"name": "search-service"}
                    }
                }
            }).encode("utf-8")
            return webhook_service.process_webhook("pagerduty", body, {}, session)
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_concurrent_event, i) for i in range(4)]
        responses = [f.result() for f in futures]

    assert all(r.events_count == 1 for r in responses)

    # Exactly 1 incident created with this incident_key
    inc_count = db.query(Incident).filter(Incident.incident_key == "concurrent-first-time-key").count()
    assert inc_count == 1


def test_scenario_5_and_6_database_failure_and_retry_recovery(db, monkeypatch):
    """
    Scenario 5: Database failure must not permanently mark an unprocessed webhook as successfully processed.
    Scenario 6: A retry after a failed transaction must be safely processable.
    """
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)
    body = json.dumps({
        "event": {
            "id": "EVT_FAIL_RETRY_123",
            "event_type": "incident.triggered",
            "data": {
                "id": "PD_FAIL_INC",
                "incident_key": "fail-retry-key",
                "title": "Failure and Retry Incident",
                "service": {"name": "test-service"}
            }
        }
    }).encode("utf-8")

    # Simulate database failure during incident creation
    from backend.app.repositories.incident_repository import IncidentRepository
    orig_create = IncidentRepository.create

    def broken_create(self, *args, **kwargs):
        raise RuntimeError("Simulated Database I/O Failure")

    monkeypatch.setattr(IncidentRepository, "create", broken_create)

    # 1. First attempt fails due to database failure
    with pytest.raises(HTTPException) as exc_info:
        webhook_service.process_webhook("pagerduty", body, {}, db)
    assert exc_info.value.status_code == 500

    # Verify event was NOT recorded as PROCESSED in database
    failed_event = deduplication_service.check_duplicate(db, "pagerduty", "EVT_FAIL_RETRY_123")
    assert failed_event is None or failed_event.status != "PROCESSED"

    # 2. Restore normal database behavior: retry must be safely processable
    monkeypatch.setattr(IncidentRepository, "create", orig_create)
    retry_resp = webhook_service.process_webhook("pagerduty", body, {}, db)
    assert retry_resp.processed_count == 1
    assert retry_resp.results[0].status == "PROCESSED"
    assert retry_resp.results[0].already_processed is False

    inc = db.query(Incident).filter(Incident.incident_key == "fail-retry-key").first()
    assert inc is not None
    assert inc.title == "Failure and Retry Incident"


def test_scenario_7_identical_retry_no_duplicate_triage_or_memory(db, monkeypatch):
    """
    Scenario 7: An identical webhook retry must not create another triage item or memory record.
    """
    monkeypatch.setattr(settings, "WEBHOOK_AUTH_REQUIRED", False)
    body = json.dumps({
        "event": {
            "id": "EVT_RETRY_TRIAGE_CHECK",
            "event_type": "incident.triggered",
            "data": {
                "id": "PD_TRIAGE_INC",
                "incident_key": "triage-dedup-key",
                "title": "Triage Dedup Check",
                "service": {"name": "triage-service"}
            }
        }
    }).encode("utf-8")

    # Initial delivery
    r1 = webhook_service.process_webhook("pagerduty", body, {}, db)
    assert r1.processed_count == 1
    triage_count_before = len(triage_service.list_queue())
    memory_count_before = memory_service.count()

    # Retry delivery
    r2 = webhook_service.process_webhook("pagerduty", body, {}, db)
    assert r2.duplicate_count == 1
    assert r2.processed_count == 0

    triage_count_after = len(triage_service.list_queue())
    memory_count_after = memory_service.count()

    # Must NOT have created additional triage items or memory records
    assert triage_count_after == triage_count_before
    assert memory_count_after == memory_count_before


def test_scenario_8_fallback_event_id_stability():
    """
    Scenario 8: Fallback event IDs must remain stable across legitimate provider retries.
    """
    datadog_adapter = adapter_registry.get("datadog")
    alertmanager_adapter = adapter_registry.get("alertmanager")

    # Datadog payload without 'id' and without 'date'
    dd_payload = {
        "alert_id": 999111,
        "title": "High latency alert",
        "body": "p99 latency > 500ms",
        "tags": ["service:api-gateway"]
    }
    dd_events_1 = datadog_adapter.normalize(dd_payload, {})
    dd_events_2 = datadog_adapter.normalize(dd_payload, {})
    # Both invocations must produce the identical fallback event ID
    assert dd_events_1[0].provider_event_id == dd_events_2[0].provider_event_id

    # Alertmanager payload without startsAt/endsAt
    am_payload = {
        "version": "4",
        "groupKey": "test_grp",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "PodCrashLoop", "service": "indexer"},
                "annotations": {"summary": "CrashLoopBackOff"},
                "fingerprint": "fp_test_123"
            }
        ]
    }
    am_events_1 = alertmanager_adapter.normalize(am_payload, {})
    am_events_2 = alertmanager_adapter.normalize(am_payload, {})
    assert am_events_1[0].provider_event_id == am_events_2[0].provider_event_id


def test_payload_size_limit_rejection(db, monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_MAX_PAYLOAD_BYTES", 1024)  # 1 KB limit
    large_body = b"A" * 2048

    with pytest.raises(HTTPException) as exc_info:
        webhook_service.process_webhook("pagerduty", large_body, {}, db)
    assert exc_info.value.status_code == 413


def test_sensitive_data_redaction():
    raw_data = {
        "service": "auth-service",
        "api_key": "secret_key_12345",
        "nested": {
            "password": "super_secret_db_password",
            "bearer_token": "token_abc_xyz",
            "safe_metric": 42
        }
    }
    redacted = redact_sensitive_data(raw_data)
    assert redacted["service"] == "auth-service"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["bearer_token"] == "[REDACTED]"
    assert redacted["nested"]["safe_metric"] == 42


def test_list_webhook_events(db):
    events = list_webhook_events(skip=0, limit=10, provider=None, status=None, db=db)
    assert isinstance(events, list)
    assert len(events) > 0
