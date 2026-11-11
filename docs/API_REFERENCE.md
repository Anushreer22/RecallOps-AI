# RecallOps-AI: API Specification & Reference

Base URL: `http://localhost:8000/api/v1`

---

## 1. System Health

### `GET /health`
Returns health status, active memory document count, active triage queue count, and service nodes.

**Response `200 OK`:**
```json
{
  "status": "healthy",
  "project": "RecallOps-AI",
  "version": "1.0.0",
  "indexed_memories": 6,
  "active_triage_count": 2,
  "services_in_graph": 11
}
```

---

## 2. Incident Ingestion & Webhooks

### `POST /webhooks/pagerduty`
Ingests PagerDuty Webhooks v3 (with HMAC-SHA256 signature verification) or v2 legacy messages.

**Headers:**
- `X-PagerDuty-Signature: v1=<hmac-sha256-hex>`

**Response `200 OK`:**
```json
{
  "provider": "pagerduty",
  "events_count": 1,
  "processed_count": 1,
  "duplicate_count": 0,
  "results": [
    {
      "event_id": "01DP1A7K9M2",
      "incident_key": "srv-auth-pool",
      "event_type": "triggered",
      "internal_incident_id": "INC-7F3A2B",
      "already_processed": false,
      "status": "PROCESSED"
    }
  ]
}
```

### `POST /webhooks/datadog`
Ingests Datadog Monitor and Event webhook alerts with custom token authentication.

**Headers:**
- `X-Datadog-Webhook-Token: <token>` or `Authorization: Bearer <token>`

**Response `200 OK`:**
```json
{
  "provider": "datadog",
  "events_count": 1,
  "processed_count": 1,
  "duplicate_count": 0,
  "results": [
    {
      "event_id": "184920481",
      "incident_key": "982741",
      "event_type": "triggered",
      "internal_incident_id": "INC-8A91C2",
      "already_processed": false,
      "status": "PROCESSED"
    }
  ]
}
```

### `POST /webhooks/alertmanager`
Ingests Prometheus Alertmanager v4 webhook payloads with Bearer token authentication and unpacks grouped alerts.

**Headers:**
- `Authorization: Bearer <token>`

**Response `200 OK`:**
```json
{
  "provider": "alertmanager",
  "events_count": 2,
  "processed_count": 2,
  "duplicate_count": 0,
  "results": [
    {
      "event_id": "4a18b9c201...",
      "incident_key": "alertmanager-fp01",
      "event_type": "triggered",
      "internal_incident_id": "INC-3F1829",
      "already_processed": false,
      "status": "PROCESSED"
    }
  ]
}
```

### `GET /webhooks/events`
Lists recorded webhook ingestion events for auditing, observability, and deduplication verification.

**Query Parameters:**
- `skip`: Integer (default 0)
- `limit`: Integer (default 50, max 100)
- `provider`: Optional filter (`pagerduty`, `datadog`, `alertmanager`)
- `status`: Optional filter (`PROCESSED`, `DUPLICATE`, `FAILED`)

### `POST /incidents/webhook` (Legacy Ingestion)
Ingests an alert payload from external monitoring systems (PagerDuty, Prometheus, Datadog) using a simplified payload.

**Request Body:**
```json
{
  "event_type": "alert.triggered",
  "alert_name": "HighLatency_PaymentGateway",
  "service": "payment-service",
  "severity": "CRITICAL",
  "tier": "TIER_0",
  "details": "Upstream payment gateway returning HTTP 504 timeouts.",
  "impacted_users": 4500,
  "logs": "dns_timeout resolving api.stripe.com in CoreDNS pod [ERR_504]"
}
```

**Response `201 Created`:**
```json
{
  "id": "INC-4A2BC9E1",
  "title": "[payment-service] HighLatency_PaymentGateway",
  "description": "Upstream payment gateway returning HTTP 504 timeouts.",
  "service_name": "payment-service",
  "severity": "CRITICAL",
  "service_tier": "TIER_0",
  "status": "OPEN",
  "impacted_users": 4500,
  "raw_logs": "dns_timeout resolving api.stripe.com in CoreDNS pod [ERR_504]",
  "source": "Webhook:alert.triggered",
  "created_at": "2026-11-09T14:40:00Z",
  "updated_at": "2026-11-09T14:40:00Z",
  "resolution": null
}
```

---

## 3. Dynamic Triage Queue

### `GET /incidents/triage/queue`
Retrieves all active unmitigated incidents ordered by highest priority score (Max-Heap).

**Response `200 OK`:**
```json
[
  {
    "incident_id": "INC-4A2BC9E1",
    "title": "[payment-service] HighLatency_PaymentGateway",
    "severity": "CRITICAL",
    "service_tier": "TIER_0",
    "impacted_users": 4500,
    "score": 93.31,
    "timestamp": 1794235200.0
  }
]
```

---

## 4. AI Diagnosis with Episodic Memory Recall

### `POST /incidents/{incident_id}/diagnose`
Synthesizes historical incident memory, log Trie signatures, and topology blast radius to generate root cause hypothesis and remediation runbook.

**Response `200 OK`:**
```json
{
  "incident_id": "INC-4A2BC9E1",
  "detected_signatures": [
    {
      "token": "dns_timeout",
      "category": "NAME_RESOLUTION_FAILURE",
      "severity": "HIGH"
    },
    {
      "token": "err_504",
      "category": "GATEWAY_TIMEOUT",
      "severity": "CRITICAL"
    }
  ],
  "blast_radius": {
    "origin_service": "payment-service",
    "total_impacted_services": 2,
    "impacted_services": [
      {
        "service": "api-gateway",
        "hop_distance": 1,
        "tier": "TIER_1",
        "owner": "Core-Routing",
        "impact_weight": 1.0
      },
      {
        "service": "checkout-web",
        "hop_distance": 1,
        "tier": "TIER_2",
        "owner": "Frontend-Team",
        "impact_weight": 1.0
      }
    ],
    "max_depth": 1
  },
  "historical_matches": [
    {
      "incident_id": "HIST-003",
      "similarity_score": 0.542,
      "title": "CoreDNS timeout during external API resolution",
      "root_cause": "Default k8s resolv.conf ndots:5 caused 5 internal domain lookups before querying public DNS.",
      "verified_fix": "Appended trailing dot '.' to external API hostnames and set dnsConfig with ndots:2.",
      "caution_notes": "Restarting CoreDNS pods only provides temporary relief; dnsConfig is the permanent solution."
    }
  ],
  "hypothesized_root_cause": "High-confidence correlation with historical incident 'CoreDNS timeout during external API resolution'. Probable root cause: Default k8s resolv.conf ndots:5 caused 5 internal domain lookups before querying public DNS.",
  "recommended_runbook_steps": [
    "1. Immediate Containment: Appended trailing dot '.' to external API hostnames and set dnsConfig with ndots:2.",
    "2. Inspect impacted downstream dependencies: api-gateway, checkout-web",
    "3. Verify error signature resolution against active log stream.",
    "4. If symptoms persist after 5 minutes, initiate failover to standby replica."
  ],
  "cautions_and_anti_patterns": [
    "Restarting CoreDNS pods only provides temporary relief; dnsConfig is the permanent solution.",
    "Ensure circuit breaker metrics are monitored during rollout."
  ],
  "confidence_score": 0.81,
  "ai_generated_at": "2026-11-09T14:40:05Z"
}
```

---

## 4.1 LLM Investigation Engine Endpoints

### `POST /incidents/{incident_id}/investigate`
Triggers an automated structured incident investigation using the configured LLM provider (OpenAI / Mock).

**Query Parameters:**
- `provider`: Optional provider override (e.g. `openai`, `mock`)

**Response `200 OK`:**
```json
{
  "id": "INV-7F2A190B",
  "incident_id": "INC-4A2BC9E1",
  "provider": "openai",
  "model_name": "gpt-4o-mini",
  "status": "COMPLETED",
  "summary": "Automated investigation grounded in collected system logs and historical resolution memory.",
  "report": {
    "incident_id": "INC-4A2BC9E1",
    "summary": "Database connection pool saturation triggered by unclosed sessions in payment-service.",
    "probable_root_causes": [
      {
        "hypothesis": "PostgreSQL connection pool saturation.",
        "confidence_score": 0.88,
        "supporting_evidence_ids": ["EVID-INC-INFO", "EVID-LOGS-SIGS", "EVID-HIST-1"],
        "contradicting_evidence_ids": [],
        "reasoning": "Scanned log signatures match historical outage HIST-001 with 0.82 similarity."
      }
    ],
    "observed_facts": ["Payment gateway throwing 500 errors", "FATAL: remaining connection slots reserved"],
    "evidence_gaps": ["Database CPU metrics unavailable"],
    "suggested_investigation_steps": ["Inspect pg_stat_activity", "Check PgBouncer client pool"],
    "suggested_resolution": ["Deploy PgBouncer connection pooler", "Recycle leaking worker pods"],
    "related_historical_incidents": ["HIST-001"],
    "requires_human_review": true,
    "hallucinated_evidence_ids": []
  },
  "created_at": "2026-11-11T12:00:00Z",
  "completed_at": "2026-11-11T12:00:03Z",
  "error_message": null
}
```

### `GET /incidents/{incident_id}/investigations`
Lists historical investigation reports for a given incident.

**Query Parameters:**
- `skip`: Integer (default 0)
- `limit`: Integer (default 50)

### `GET /investigations/{investigation_id}`
Retrieves a specific investigation report by ID.

### `POST /investigations/{investigation_id}/feedback`
Allows an on-call engineer to verify, approve, or reject an investigation report.

**Request Body:**
```json
{
  "approved": true,
  "verified_by": "Senior-SRE",
  "root_cause": "Unclosed connections in JWT validation middleware.",
  "action_taken": "Applied PgBouncer pooler and fixed session context manager.",
  "prevention_steps": "Added pool healthcheck alert at 80% saturation."
}
```

**Response `200 OK`:**
```json
{
  "investigation_id": "INV-7F2A190B",
  "incident_id": "INC-4A2BC9E1",
  "approved": true,
  "verified_by": "Senior-SRE",
  "memory_indexed": true,
  "resolution_id": "RES-8A1902C1",
  "incident_status": "RESOLVED",
  "message": "Investigation INV-7F2A190B approved by Senior-SRE. Incident resolved and resolution indexed into episodic memory."
}
```

---

## 5. Incident Resolution & Feedback Loop

### `POST /incidents/{incident_id}/resolve`
Records the verified post-mortem, marks the incident as `RESOLVED`, pops it from triage, and updates the vector memory space.

**Request Body:**
```json
{
  "root_cause": "Default k8s resolv.conf ndots:5 saturated CoreDNS replicas.",
  "action_taken": "Updated Helm values with dnsConfig ndots:2 and single-request-reopen.",
  "prevention_steps": "Added static CoreDNS query rate alert and enforced trailing dot on external hostnames.",
  "verified_by": "OnCall-SRE"
}
```

**Response `200 OK`:**
```json
{
  "id": "RES-8A731B29",
  "incident_id": "INC-4A2BC9E1",
  "root_cause": "Default k8s resolv.conf ndots:5 saturated CoreDNS replicas.",
  "action_taken": "Updated Helm values with dnsConfig ndots:2 and single-request-reopen.",
  "prevention_steps": "Added static CoreDNS query rate alert and enforced trailing dot on external hostnames.",
  "verified_by": "OnCall-SRE",
  "resolved_at": "2026-11-09T14:42:00Z"
}
```

---

## 6. Service Blast Radius Analysis

### `GET /incidents/topology/blast-radius?service=user-db`
Computes the downstream blast radius using Breadth-First Search (BFS) on the service dependency graph.

**Response `200 OK`:**
```json
{
  "origin_service": "user-db",
  "total_impacted_services": 4,
  "impacted_services": [
    {
      "service": "auth-service",
      "hop_distance": 1,
      "tier": "TIER_1",
      "owner": "Security-Team",
      "impact_weight": 1.0
    },
    {
      "service": "payment-service",
      "hop_distance": 1,
      "tier": "TIER_1",
      "owner": "Payments-Team",
      "impact_weight": 1.0
    },
    {
      "service": "inventory-service",
      "hop_distance": 1,
      "tier": "TIER_1",
      "owner": "Logistics-Team",
      "impact_weight": 1.0
    },
    {
      "service": "api-gateway",
      "hop_distance": 2,
      "tier": "TIER_1",
      "owner": "Core-Routing",
      "impact_weight": 0.5
    }
  ],
  "max_depth": 2
}
```

---

## 7. Authentication & User Profile

### `POST /auth/register`
Registers a new user account, creates their primary organization, and returns a signed JWT access token.

**Request Body:**
```json
{
  "email": "engineer@company.com",
  "password": "StrongPassword123!",
  "full_name": "Senior SRE",
  "organization_name": "Acme Platform Team"
}
```

**Response `201 Created`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "USR-a8b2c4d6",
    "email": "engineer@company.com",
    "full_name": "Senior SRE",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2026-11-11T20:00:00Z",
    "memberships": [
      {
        "id": "MEM-12345678",
        "organization_id": "ORG-98765432",
        "organization_name": "Acme Platform Team",
        "organization_slug": "acme-platform-team-1a2b",
        "role": "ADMIN",
        "created_at": "2026-11-11T20:00:00Z"
      }
    ]
  }
}
```

### `POST /auth/login`
Authenticates a user via email and password, returning an access token.

**Request Body:**
```json
{
  "email": "engineer@company.com",
  "password": "StrongPassword123!"
}
```

**Response `200 OK`:** Same token payload as registration.

### `GET /auth/me`
Retrieves current authenticated user profile and memberships. Requires `Authorization: Bearer <token>`.

---

## 8. Organization & Membership Management

### `POST /organizations`
Creates a new organization. Requires authenticated user.

### `GET /organizations`
Lists organizations the authenticated user belongs to.

### `GET /organizations/{org_id}/members`
Lists all members in the organization. Requires membership.

### `POST /organizations/{org_id}/members`
Adds a new member by email with specified role (`ADMIN`, `ENGINEER`, `VIEWER`). Requires `ADMIN` role.

### `PUT /organizations/{org_id}/members/{user_id}`
Updates a member's role. Requires `ADMIN` role.

---

## 9. Projects & Services Management

### `POST /projects`
Creates a project scoped to the active organization. Requires `ENGINEER` role.

### `GET /projects`
Lists projects in the active organization. Requires `VIEWER` role.

### `POST /services`
Registers a microservice within the active organization. Requires `ENGINEER` role.

### `GET /services`
Lists services in the organization. Requires `VIEWER` role.

---

## 10. Persistent Topology & Cycle Detection

### `POST /topology/dependencies`
Registers a persistent dependency edge (`source_service` -> `target_service`). Requires `ENGINEER` role.

### `DELETE /topology/dependencies/{id}`
Deletes a dependency edge and updates the in-memory graph. Requires `ENGINEER` role.

### `GET /topology/dependencies`
Lists all persistent dependency edges for the active organization.

### `GET /topology/blast-radius?service=auth-service`
Computes downstream blast radius for a service in the active organization.

### `GET /topology/cycles`
Runs 3-color DFS to detect circular architecture dependencies.

---

## 11. Security Audit Logs

### `GET /audit-logs?action=AUTH_LOGIN&limit=50&offset=0`
Retrieves sanitized security audit records for the active organization. Requires `VIEWER` role. Sensitive metadata (passwords, tokens) is scrubbed to `[REDACTED]`.
