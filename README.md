# RecallOps-AI 🚨🧠

> **Persistent Incident Memory & Autonomous Production Intelligence for SRE Teams**

RecallOps-AI bridges the gap between stateless AI triage and long-term production resilience. Instead of analyzing outages in isolation, RecallOps-AI maintains **persistent episodic memory** backed by a durable relational database, applies **graph-based blast radius traversal**, and dynamically prioritizes incoming telemetry via a **multi-factor max-heap triage queue**.

---

## 🏛️ The 5 Core Concepts Implemented

| Core Concept | Implementation in RecallOps-AI |
| :--- | :--- |
| **1. Data Structures & Algorithms** | • **Vector Index & Cosine Similarity ($k$-NN):** In-memory TF-IDF sparse vector retrieval with thread-safe `RLock` synchronization.<br>• **Priority Queue (Max-Heap):** Dynamic triage prioritizing alerts by Severity, Service Tier, and User Impact.<br>• **Directed Acyclic Graph (DAG):** Downstream BFS blast-radius propagation and DFS cycle detection.<br>• **Prefix Trie:** $\mathcal{O}(L)$ log tokenization and error signature categorization. |
| **2. API Integration** | • **FastAPI REST Endpoints:** Modular `/api/v1/` routes with dependency injection.<br>• **Production Webhook Adapters:** Native adapters for PagerDuty (v3 HMAC-SHA256 & v2), Datadog (token auth & tag parsing), and Prometheus Alertmanager (v4 grouped alerts).<br>• **Database Deduplication:** Idempotency tracking in `webhook_events` via unique constraint on `(provider, provider_event_id)`.<br>• **Durable Persistence:** SQLAlchemy ORM models with SQLite/PostgreSQL persistence and transactional rollback guarantees. |
| **3. Prototyping** | • **Persistent Episodic Memory Lifecycle:** Ingestion $\rightarrow$ Triage $\rightarrow$ Memory Recall $\rightarrow$ Diagnosis $\rightarrow$ Verified Resolution $\rightarrow$ Database Persistence $\rightarrow$ Startup Rehydration.<br>• **Database-Driven Memory Seeding:** Grounded historical outages persisted in relational storage, not volatile RAM. |
| **4. Testing & Validation** | • **49 Automated Tests:** Full test suite covering webhook authentication, idempotency, lifecycle transitions, persistence across server restarts, service recreation, duplicate handling, database failure handling, DSA, schemas, and lifecycle APIs.<br>• **Pydantic V2:** Runtime boundary validation and type safety. |
| **5. Technical Documentation** | • **Webhook Architecture:** Complete provider security and normalization specifications in `docs/WEBHOOK_INTEGRATIONS.md`.<br>• **System Design:** Detailed architectural documentation, database persistence vs in-memory index design in `docs/SYSTEM_DESIGN.md`.<br>• **Implementation Audit:** Comprehensive gap analysis and vulnerability review in `docs/IMPLEMENTATION_AUDIT.md`.<br>• **API Reference:** Complete endpoint documentation in `docs/API_REFERENCE.md`.<br>• **Interactive Swagger Docs:** Accessible at `/docs`. |

---

## 🧠 Persistent Episodic Memory Architecture

RecallOps-AI cleanly separates **durable relational persistence** from the **in-memory vector search index**:

```
+--------------------------------------------------------------------------+
|                        DURABLE PERSISTENCE LAYER                         |
|                    (SQLAlchemy ORM + SQLite/PostgreSQL)                  |
|                                                                          |
|  - Table: `incidents` (title, description, service_name, raw_logs)       |
|  - Table: `incident_resolutions` (root_cause, action_taken, verified_by) |
|  - ACID Guarantees: Transactional rollbacks on failure                   |
|  - Source of Truth: Survives process restarts, crashes, deployments      |
+--------------------------------------------------------------------------+
                                     |
               Startup Rehydration   |   Verified Resolution
             (rehydrate_from_db)     |   (record_resolution)
                                     v
+--------------------------------------------------------------------------+
|                       EPISODIC IN-MEMORY SEARCH INDEX                    |
|                        (EpisodicMemoryIndex in RAM)                      |
|                                                                          |
|  - Structure: Sparse TF-IDF token dictionary + precomputed vector norms  |
|  - Retrieval: Cosine Similarity k-NN ranking via min-heap               |
|  - Synchronization: Thread-safe via threading.RLock                     |
|  - Lifecycle: Ephemeral; rebuilt from verified database records on start |
+--------------------------------------------------------------------------+
```

1. **Transactional Durability:** When an incident is resolved with verified notes (`verified_by`), it is atomically written to the relational database.
2. **Startup Rehydration:** On application start (`lifespan`), `EpisodicMemoryService.rehydrate_from_db()` queries all verified resolutions and re-indexes them into RAM.
3. **Verified Knowledge Only:** Speculative or unverified triage notes are rejected by the memory index, preventing hallucinated fixes from polluting historical memory.
4. **Duplicate Protection:** Re-resolving an incident updates the existing database record in place and updates the memory index cleanly without inflating document counts.

---

## 🔌 Production-Ready Webhook Adapters

RecallOps-AI provides dedicated, secure ingestion endpoints for industry-standard observability tools:

- **PagerDuty (`/api/v1/webhooks/pagerduty`):** V3 HMAC-SHA256 signature verification via `X-PagerDuty-Signature` with secret rotation support, plus V2 legacy support.
- **Datadog (`/api/v1/webhooks/datadog`):** Authenticated monitor ingestion via `X-Datadog-Webhook-Token` or `Authorization: Bearer`, dynamic tag parsing (`service:<name>`).
- **Prometheus Alertmanager (`/api/v1/webhooks/alertmanager`):** V4 webhook receiver format with Bearer token authentication, unpacking grouped firing and resolved alerts.
- **Deduplication & Idempotency:** Managed via `webhook_events` table with unique constraint `(provider, provider_event_id)` and fallback deterministic hashing.
- **Full Guide:** See [`docs/WEBHOOK_INTEGRATIONS.md`](file:///c:/Users/ANUSHREE%20R/RecallOps-AI/docs/WEBHOOK_INTEGRATIONS.md).

---

## 🚀 Quickstart Guide

### 1. Prerequisites
* Python 3.10+ (Python 3.12 verified)

### 2. Environment Setup
```powershell
# Navigate to backend
cd backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies (if not already installed)
pip install -r requirements.txt
```

### 3. Run the Backend Server
```powershell
uvicorn backend.app.main:app --reload --port 8000
```
Open **[http://localhost:8000/docs](http://localhost:8000/docs)** to view the interactive Swagger API documentation.

---

## 🧪 Running the Test Suite

Run the full automated test suite (49 tests):

```powershell
pytest -v
```

**Test Breakdown:**
* `backend/tests/test_webhooks.py`: 21 tests (PagerDuty v3 HMAC-SHA256 & v2 legacy, Datadog token & bearer auth, Prometheus Alertmanager grouped alerts, auth failures, idempotency & deduplication, payload size rejection, credential scrubbing, audit events, and critical concurrency / lifecycle reliability scenarios).
* `backend/tests/test_persistent_memory.py`: 8 tests (Verified additions, service recreation, restart persistence across temporary database, unverified rejection, duplicate resolution protection, multiple record rehydration, empty memory retrieval, database failure handling).
* `backend/tests/test_algorithms.py`: 8 tests (Vector similarity, Priority queue, Graph blast radius, Cycle detection, Error Trie).
* `backend/tests/test_health.py`: 2 tests (System health, degraded state detection, and metadata).
* `backend/tests/test_incidents_api.py`: 6 tests (Ingestion, Webhooks, Triage, AI Diagnosis, Resolution feedback loop, Topology).
* `backend/tests/test_schemas.py`: 4 tests (Schema boundaries and validation constraints).

---

## 📁 Repository Layout

```
RecallOps-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── health.py              # Healthcheck & degraded status reporting
│   │   │   │   ├── incidents.py           # Ingestion, Triage, Diagnosis, Resolution
│   │   │   │   └── webhooks.py            # PagerDuty, Datadog, Alertmanager endpoints
│   │   │   └── router.py                  # API V1 router aggregation
│   │   ├── core/
│   │   │   ├── algorithms.py              # DSA: VectorIndex, Max-Heap, DAG, Trie (Thread-safe)
│   │   │   └── config.py                  # Application settings (Pydantic Settings)
│   │   ├── db/
│   │   │   ├── base.py                    # DeclarativeBase
│   │   │   └── session.py                 # SQLAlchemy session engine
│   │   ├── integrations/                  # Modular webhook adapters
│   │   │   ├── base.py                    # BaseWebhookAdapter & NormalizedAlertEvent
│   │   │   ├── registry.py                # WebhookAdapterRegistry
│   │   │   ├── pagerduty/                 # PagerDuty adapter, schemas & HMAC verification
│   │   │   ├── datadog/                   # Datadog adapter, schemas & token security
│   │   │   └── alertmanager/              # Alertmanager adapter, schemas & auth
│   │   ├── models/
│   │   │   ├── incident.py                # Incident & Resolution ORM models
│   │   │   └── webhook_event.py           # Webhook event deduplication model
│   │   ├── repositories/
│   │   │   └── incident_repository.py     # Transactional data access layer
│   │   ├── schemas/
│   │   │   └── incident.py                # Pydantic V2 schemas
│   │   ├── services/
│   │   │   ├── ai_agent_service.py        # Diagnostic & Runbook reasoning agent
│   │   │   ├── memory_service.py          # Persistent episodic memory manager
│   │   │   ├── topology_service.py        # Microservice dependency graph
│   │   │   └── triage_service.py          # Dynamic priority triage queue
│   │   └── main.py                        # FastAPI app & database startup rehydration
│   ├── tests/
│   │   ├── test_persistent_memory.py      # Persistence & rehydration test suite
│   │   ├── test_algorithms.py             # DSA unit tests
│   │   ├── test_health.py                 # Health endpoint tests
│   │   ├── test_incidents_api.py          # Lifecycle integration tests
│   │   └── test_schemas.py                # Pydantic boundary validation tests
│   └── requirements.txt                   # Project dependencies
├── docs/
│   ├── SYSTEM_DESIGN.md                   # In-depth architectural blueprint
│   ├── IMPLEMENTATION_AUDIT.md            # Comprehensive audit & risk review
│   └── API_REFERENCE.md                   # API specifications & curl examples
├── pytest.ini                             # Test runner configuration
└── README.md                              # Project documentation
```
