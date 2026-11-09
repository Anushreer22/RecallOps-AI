import pytest
from pydantic import ValidationError
from backend.app.schemas.incident import IncidentCreate, ResolutionCreate, WebhookAlertPayload


def test_incident_create_valid():
    inc = IncidentCreate(
        title="Test Incident",
        description="Testing system",
        service_name="auth-service",
        severity="HIGH",
        service_tier="TIER_1",
        impacted_users=50
    )
    assert inc.title == "Test Incident"
    assert inc.impacted_users == 50


def test_incident_create_negative_users_fails():
    with pytest.raises(ValidationError):
        IncidentCreate(
            title="Invalid Users",
            description="Testing negative users",
            service_name="auth-service",
            impacted_users=-10
        )


def test_resolution_create_required_fields():
    with pytest.raises(ValidationError):
        # Missing root_cause and action_taken
        ResolutionCreate(verified_by="Tester")


def test_webhook_alert_payload_defaults():
    payload = WebhookAlertPayload(
        alert_name="HighLatency",
        service="api-gateway",
        details="Latency exceeded 2000ms"
    )
    assert payload.event_type == "alert.triggered"
    assert payload.severity == "HIGH"
    assert payload.tier == "TIER_0"
    assert payload.impacted_users == 500
