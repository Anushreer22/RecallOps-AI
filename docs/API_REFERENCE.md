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

### `POST /incidents/webhook`
Ingests an alert payload from external monitoring systems (PagerDuty, Prometheus, Datadog).

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
