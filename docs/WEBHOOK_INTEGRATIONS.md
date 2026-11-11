# RecallOps-AI: Webhook Integrations & Ingestion Architecture

RecallOps-AI provides production-ready, vendor-specific webhook adapters for enterprise observability and alerting platforms:
1. **PagerDuty Webhooks** (v3 and v2 legacy)
2. **Datadog Webhooks** (Monitor & Event alerts)
3. **Prometheus Alertmanager** (v4 webhook receiver)

All incoming webhooks pass through cryptographic signature or bearer token authentication, payload size enforcement, schema validation, sensitive credential redaction, database-backed deduplication/idempotency tracking, and incident lifecycle state synchronization.

---

## 1. Architecture Overview

```
                                      ┌─────────────────────────────────────────────────────────┐
                                      │              RecallOps-AI Ingestion Gateway             │
                                      │                                                         │
[ PagerDuty v3/v2 ] ──(HMAC-SHA256)───► [ POST /api/v1/webhooks/pagerduty    ]                  │
                                      │                                      │                  │
[ Datadog Monitor ] ──(Token Auth)────► [ POST /api/v1/webhooks/datadog      │──► [ Payload ]   │
                                      │                                      │    [ Size    ]   │
[ Alertmanager v4 ] ──(Bearer Token)──► [ POST /api/v1/webhooks/alertmanager │    [ Check   ]   │
                                      └──────────────────────────────────────┼──────────────────┘
                                                                             │
                                                                             ▼
                                                              ┌─────────────────────────────┐
                                                              │ Security Verification       │
                                                              │ - HMAC / Constant-time auth │
                                                              └──────────────┬──────────────┘
                                                                             │
                                                                             ▼
                                                              ┌─────────────────────────────┐
                                                              │ Schema Validation (Pydantic)│
                                                              └──────────────┬──────────────┘
                                                                             │
                                                                             ▼
                                                              ┌─────────────────────────────┐
                                                              │ Normalization & Redaction   │
                                                              │ (NormalizedAlertEvent)      │
                                                              └──────────────┬──────────────┘
                                                                             │
                                                                             ▼
                                                              ┌─────────────────────────────┐
                                                              │ Database Deduplication      │
                                                              │ (Unique: provider + evt_id) │
                                                              └──────────────┬──────────────┘
                                                                Duplicate?   │  New Event?
                                                            ┌────────────────┴───────────────┐
                                                            ▼                                ▼
                                                  [ 200 OK: DUPLICATE ]         [ Incident Lifecycle ]
                                                  (Provider stops retry)         - Triggered -> Triage
                                                                                 - Acked -> Investigate
                                                                                 - Resolved -> Resolve
```

---

## 2. Provider Specifications & Security Analysis

### A. PagerDuty Webhooks (v3 & v2)

- **Official Specification:** PagerDuty sends HTTP POST requests containing an `event` object (v3) or an array of `messages` (v2).
- **Authentication & Signatures:**
  - PagerDuty Webhooks v3 supports HMAC-SHA256 payload signing via the `X-PagerDuty-Signature` header.
  - Header Format: `v1=<hmac-sha256-hex>`
  - Key Rotation: PagerDuty transmits multiple signatures separated by commas during secret rotation: `v1=<new_sig>,v1=<old_sig>`. RecallOps-AI validates against all comma-separated signatures.
  - V2 Legacy: Transmits unauthenticated messages or custom webhook tokens.
- **Correlation & Deduplication:**
  - Event ID: `event.id` (v3) or `messages[i].id` (v2).
  - Incident Correlation Key: `event.data.incident_key` or `event.data.id`.

### B. Datadog Webhooks

- **Official Specification:** Datadog Monitor and Event webhooks post JSON payloads when a monitor changes status (Triggered, Recovered, Warn, No Data).
- **Security Limitations & Authentication:**
  - **Important:** Datadog does **not** provide native cryptographic HMAC payload signing.
  - **Documented Mechanism:** Datadog Webhooks support user-configured Custom Headers in the Datadog integration UI.
  - RecallOps-AI verifies the configured secret using:
    - `X-Datadog-Webhook-Token: <token>`
    - or `Authorization: Bearer <token>`
  - All comparisons use `hmac.compare_digest` to prevent timing attacks.
- **Normalization & Service Extraction:**
  - Datadog tags (`tags: ["service:auth-service", "env:production"]`) are dynamically parsed to identify the impacted microservice and environment.
  - Lifecycle: `alert_transition: "Recovered"` transitions the incident to `RESOLVED`.

### C. Prometheus Alertmanager (v4)

- **Official Specification:** Prometheus Alertmanager posts grouped alerts formatted as JSON with version `4`.
- **Security Limitations & Authentication:**
  - **Important:** Alertmanager does **not** cryptographically sign payloads with HMAC.
  - **Documented Mechanism:** Alertmanager `http_config` supports HTTP Bearer token authentication:
    ```yaml
    receivers:
    - name: 'recallops-webhook'
      webhook_configs:
      - url: 'http://recallops.internal/api/v1/webhooks/alertmanager'
        http_config:
          bearer_token: 'your-configured-alertmanager-secret'
        send_resolved: true
    ```
  - RecallOps-AI validates `Authorization: Bearer <token>` or `X-Alertmanager-Token` using constant-time comparison.
- **Grouped Alert Unpacking:**
  - Alertmanager groups multiple alerts into a single webhook delivery batch (`alerts: [...]`).
  - RecallOps-AI unpacks the batch into individual `NormalizedAlertEvent` objects based on `fingerprint`, reconciling each firing or resolved alert independently.

---

## 3. Database Deduplication & Idempotency

When monitoring providers experience delivery timeouts or upstream network blips, they automatically retry webhook deliveries. Without idempotency guards, retries cause duplicate incident creation and alert fatigue.

RecallOps-AI implements robust database-backed deduplication:
- **Table:** `webhook_events`
- **Unique Constraint:** `(provider, provider_event_id)`
- **Behavior on Duplicate:**
  - RecallOps-AI detects the duplicate record via query and atomic unique constraint enforcement.
  - Returns HTTP `200 OK` with `already_processed: true` and `status: "DUPLICATE"`.
  - The external provider receives a successful acknowledgement and halts its retry loop.
  - No duplicate incidents, priority queue items, or resolutions are created.

---

## 4. Sensitive Data Sanitization

Observability alerts frequently contain authorization tokens, passwords, database URLs, and API keys embedded in stack traces or raw metrics.

RecallOps-AI executes recursive sensitive key scrubbing (`redact_sensitive_data`) before persisting any payload to disk or the database:
- Matching keys: `password`, `secret`, `token`, `api_key`, `auth`, `bearer`, `credentials`, `private_key`, `cert`.
- Value replacement: `[REDACTED]`.

---

## 5. Configuration Reference

Configure webhook behavior in `.env` or system environment variables:

| Variable | Default | Description |
|---|---|---|
| `PAGERDUTY_WEBHOOK_SECRET` | `None` | Shared HMAC secret for verifying `X-PagerDuty-Signature`. |
| `DATADOG_WEBHOOK_TOKEN` | `None` | Secret token expected in `X-Datadog-Webhook-Token` or `Authorization: Bearer`. |
| `ALERTMANAGER_WEBHOOK_TOKEN` | `None` | Secret token expected in Alertmanager `http_config` Bearer token. |
| `WEBHOOK_AUTH_REQUIRED` | `False` | When `True`, rejects unauthenticated webhook requests with HTTP 401. |
| `WEBHOOK_MAX_PAYLOAD_BYTES` | `1048576` (1MB) | Maximum allowed payload size; larger requests are rejected with HTTP 413. |
