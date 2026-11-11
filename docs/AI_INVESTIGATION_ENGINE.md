# RecallOps-AI: Real LLM-Powered Incident Investigation Engine

## 1. Executive Summary

RecallOps-AI Phase 3 replaces static, deterministic template diagnosis with an enterprise-grade **LLM Incident Investigation Engine**.

Unlike simplistic LLM wrappers that merely pass an alert title to a prompt and generate speculative diagnoses, RecallOps-AI synthesizes multi-modal observability evidence, verifies root-cause hypotheses against actual evidence identifiers, and enforces a strict human-in-the-loop approval workflow before allowing operational fixes into persistent episodic memory.

---

## 2. Architecture & Pipeline

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │            Evidence Collection Engine                  │
                                  │                                                        │
[ Incident Core Metadata ] ──────►│ - EVID-INC-INFO: Title, service, severity, tier       │
                                  │                                                        │
[ Scanned Application Logs ] ────►│ - EVID-LOGS-SIGS: Prefix trie error code signatures    │
                                  │ - EVID-LOGS-RAW: Sanitized log extracts                │
                                  │                                                        │
[ Topology DAG ] ────────────────►│ - EVID-TOPO-BLAST: Downstream blast radius & hops      │
                                  │                                                        │
[ Episodic Vector Memory ] ──────►│ - EVID-HIST-*: Verified historical resolutions ($k$-NN)│
                                  │                                                        │
[ Missing Telemetry Guard ] ─────►│ - EVID-TELEM-*: Unavailable metrics and traces         │
                                  └──────────────────────────┬─────────────────────────────┘
                                                             │
                                                             ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │ Prompt Engineering & Injection Defense                 │
                                  │ - SRE System Role & Anti-Hallucination Directives      │
                                  │ - Delimited <untrusted_*> Blocks & Tag Stripping       │
                                  └──────────────────────────┬─────────────────────────────┘
                                                             │
                                                             ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │ LLM Provider Architecture (OpenAI / Mock)              │
                                  │ - JSON Structured Object Enforcement                   │
                                  │ - Bounded Retries & HTTP Timeout Handling              │
                                  └──────────────────────────┬─────────────────────────────┘
                                                             │
                                                             ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │ Grounding & Anti-Hallucination Verification            │
                                  │ - Validates supporting_evidence_ids against collection │
                                  │ - Strips and quarantines hallucinated citations        │
                                  └──────────────────────────┬─────────────────────────────┘
                                                             │
                                                             ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │ Durable Persistence (`investigations` Table)           │
                                  │ - Status: COMPLETED / FAILED                           │
                                  │ - Preserves full investigation history per incident    │
                                  └──────────────────────────┬─────────────────────────────┘
                                                             │
                                                             ▼
                                  ┌────────────────────────────────────────────────────────┐
                                  │ Human-in-the-Loop Feedback Loop                        │
                                  │ - Engineer Reviews & Approves/Rejects via API          │
                                  │ - ONLY Approved Resolutions Enter Episodic Memory      │
                                  └────────────────────────────────────────────────────────┘
```

---

## 3. Provider-Independent Architecture

The AI subsystem is structured under `backend/app/ai/`:

- **`base.py` (`BaseLLMProvider`)**: Abstract provider interface defining `generate_investigation`, `is_available`, and `validate_configuration`.
- **`registry.py` (`LLMProviderRegistry`)**: Central registry mapping provider identifiers (`openai`, `mock`) to active instances.
- **`providers/openai_provider.py` (`OpenAIProvider`)**: Production provider utilizing OpenAI's Chat Completions REST API with `response_format={"type": "json_object"}`, bounded exponential backoff retries, and strict timeout enforcement.
- **`providers/mock_provider.py` (`MockLLMProvider`)**: Deterministic provider for offline development and CI/CD test automation, capable of simulating timeouts, auth failures, malformed JSON, and hallucinated evidence IDs.

### Configuration (`.env`)

```ini
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-api-key-here
LLM_TEMPERATURE=0.2
LLM_TIMEOUT_SECONDS=30.0
LLM_MAX_RETRIES=2
```

---

## 4. Evidence Grounding & Anti-Hallucination

To prevent LLM hallucination and ensure auditability:
1. **Stable Identifiers:** Every piece of telemetry passed to the model receives a unique ID (`EVID-INC-INFO`, `EVID-LOGS-SIGS`, `EVID-HIST-1`, `EVID-TOPO-BLAST`).
2. **Explicit Citation Requirement:** The model must reference valid evidence IDs in `supporting_evidence_ids` and `contradicting_evidence_ids`.
3. **Automated Citation Validation:** The `InvestigationService` extracts all cited evidence IDs and verifies them against the actual collection. Any hallucinated IDs are stripped from hypotheses, placed into `hallucinated_evidence_ids`, and flagged in `evidence_gaps`.
4. **Honest Ignorance:** If telemetry is missing (e.g., no raw logs or uninstrumented traces), the system explicitly registers `EVID-LOGS-UNAVAIL` and `EVID-TELEM-METRICS`, compelling the LLM to acknowledge missing data rather than fabricating metrics.

---

## 5. Confidence Score Interpretation

Confidence scores in `probable_root_causes[*].confidence_score` are **calibrated heuristic assessments** [0.0 - 1.0], not pure statistical probabilities.

- **0.80 - 1.00 (High Confidence):** Hypothesis supported by direct error log signatures, upstream/downstream topological failure patterns, and verified historical resolutions with high cosine similarity.
- **0.50 - 0.79 (Moderate Confidence):** Hypothesis supported by partial symptoms or topological proximity, with unverified telemetry gaps.
- **0.00 - 0.49 (Low / Speculative):** Absence of conclusive logs or conflicting evidence. SRE must execute suggested investigation steps before applying remediations.

---

## 6. Prompt Injection Defense

Observability telemetry frequently contains untrusted payloads from external users, HTTP headers, or network attacks.

RecallOps-AI protects the prompt boundary via:
1. **Tag Neutralization:** Closing and opening delimiter tags (e.g. `</untrusted_incident_logs>`) are aggressively stripped (`[STRIPPED_TAG]`).
2. **Structural Sandboxing:** Untrusted data is enclosed in dedicated XML blocks:
   ```xml
   <untrusted_incident_title>...</untrusted_incident_title>
   <untrusted_incident_description>...</untrusted_incident_description>
   <untrusted_incident_logs>...</untrusted_incident_logs>
   ```
3. **Role Instruction Pinning:** The system prompt explicitly commands the model to treat all content inside `<untrusted_*>` tags as passive data to analyze, never as instructions to execute.

---

## 7. API Reference

### `POST /api/v1/incidents/{incident_id}/investigate`
Triggers an automated investigation for the specified incident.

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

### `POST /api/v1/investigations/{investigation_id}/feedback`
Allows an on-call engineer to verify and approve or reject the AI findings.

**Request Body:**
```json
{
  "approved": true,
  "verified_by": "Senior-SRE",
  "root_cause": "Unclosed connections in JWT validation middleware.",
  "action_taken": "Applied connection pooler and fixed session context manager.",
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
