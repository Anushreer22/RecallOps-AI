# RecallOps-AI 🚨🧠

> **Persistent Incident Memory & Autonomous Production Intelligence for SRE Teams**

RecallOps-AI bridges the gap between stateless AI triage and long-term production resilience. Instead of analyzing outages in isolation, RecallOps-AI maintains an **episodic vector memory** of historical failures, applies **graph-based blast radius traversal**, and dynamically prioritizes incoming telemetry via a **multi-factor max-heap triage queue**.

---

## 🏛️ The 5 Core Concepts Implemented

| Core Concept | Implementation in RecallOps-AI |
| :--- | :--- |
| **1. Data Structures & Algorithms** | • **Vector Index & Cosine Similarity ($k$-NN):** Sub-linear similarity search across historical incidents.<br>• **Priority Queue (Max-Heap):** Multivariate urgency scoring based on Severity, Service Tier, and User Impact.<br>• **Directed Acyclic Graph (DAG):** Downstream BFS blast-radius propagation and DFS cycle detection.<br>• **Prefix Trie:** $\mathcal{O}(L)$ log tokenization and error signature categorization. |
| **2. API Integration** | • **FastAPI REST Endpoints:** Modular `/api/v1/` routes with dependency injection.<br>• **Webhook Ingestion:** Normalizes alerts from PagerDuty, Datadog, Prometheus, Grafana.<br>• **Database Layer:** SQLAlchemy ORM models with SQLite/PostgreSQL persistence. |
| **3. Prototyping** | • **Working End-to-End MVP:** Ingestion $\rightarrow$ Triage $\rightarrow$ Memory Recall $\rightarrow$ Diagnosis $\rightarrow$ Resolution Feedback.<br>• **Pre-seeded Incident History:** Out-of-the-box knowledge base of common production failure modes. |
| **4. Testing & Validation** | • **20 Automated Tests:** Unit tests for DSA, schema validations, and full API lifecycle tests with `pytest`.<br>• **Pydantic V2:** Runtime boundary validation and type safety. |
| **5. Technical Documentation** | • **System Design:** Detailed architectural documentation and mathematical formulas in `docs/SYSTEM_DESIGN.md`.<br>• **API Reference:** Complete endpoint documentation in `docs/API_REFERENCE.md`.<br>• **Interactive Swagger Docs:** Accessible at `/docs`. |

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

Run the full automated test suite (20 tests covering algorithms, API endpoints, and schemas):

```powershell
pytest -v
```

**Test Breakdown:**
* `backend/tests/test_algorithms.py`: 8 tests (Vector similarity, Priority queue, Graph blast radius, Cycle detection, Error Trie).
* `backend/tests/test_health.py`: 2 tests (System health and metadata).
* `backend/tests/test_incidents_api.py`: 6 tests (Ingestion, Webhooks, Triage, AI Diagnosis, Resolution feedback loop).
* `backend/tests/test_schemas.py`: 4 tests (Schema boundaries and validation constraints).

---

## 📁 Repository Layout

```
RecallOps-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── health.py        # Healthcheck endpoint
│   │   │   │   └── incidents.py     # Ingestion, Triage, Diagnosis, Resolution
│   │   │   └── router.py            # API V1 router aggregation
│   │   ├── core/
│   │   │   ├── algorithms.py        # DSA: VectorIndex, Max-Heap, DAG, Trie
│   │   │   └── config.py            # Application settings (Pydantic Settings)
│   │   ├── db/
│   │   │   ├── base.py              # DeclarativeBase
│   │   │   └── session.py           # SQLAlchemy session engine
│   │   ├── models/
│   │   │   └── incident.py          # Incident & Resolution ORM models
│   │   ├── repositories/
│   │   │   └── incident_repository.py # Data access layer
│   │   ├── schemas/
│   │   │   └── incident.py          # Pydantic V2 schemas
│   │   ├── services/
│   │   │   ├── ai_agent_service.py  # Diagnostic & Runbook reasoning agent
│   │   │   ├── memory_service.py    # Episodic memory management
│   │   │   ├── topology_service.py  # Microservice dependency graph
│   │   │   └── triage_service.py    # Dynamic priority triage queue
│   │   └── main.py                  # FastAPI application entrypoint
│   ├── tests/
│   │   ├── test_algorithms.py       # DSA unit tests
│   │   ├── test_health.py           # Health endpoint tests
│   │   ├── test_incidents_api.py    # Lifecycle integration tests
│   │   └── test_schemas.py          # Pydantic boundary validation tests
│   └── requirements.txt             # Project dependencies
├── docs/
│   ├── SYSTEM_DESIGN.md             # In-depth architectural blueprint
│   └── API_REFERENCE.md             # API specifications & curl examples
├── pytest.ini                       # Test runner configuration
└── README.md                        # Project documentation
```

---

## 💡 Real-World Workflow Example

1. **Alert Ingestion:** Datadog fires a webhook indicating `[payment-service] HighErrorRate`.
2. **Dynamic Triage:** System calculates priority score based on severity (CRITICAL) and tier (TIER_0), placing it at the front of the queue.
3. **AI Diagnosis & Memory Recall:**
   * Trie matches `[ERR_504]` and `dns_timeout`.
   * Graph traces blast radius: `checkout-web` and `api-gateway` are impacted.
   * Vector Index recalls incident `HIST-003` (CoreDNS `ndots:5` timeout) with 81% confidence.
4. **Actionable Runbook:** Agent recommends applying `dnsConfig ndots:2` and warns against pod restarting anti-patterns.
5. **Continuous Learning:** When SRE resolves the incident, the verified solution is indexed into memory, permanently preventing future guesswork.
