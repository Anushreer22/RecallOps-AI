# RecallOps-AI — Frontend Architecture & Component Design

## 1. Architectural Overview

RecallOps-AI's frontend is a high-performance, single-page application built with **React 18**, **TypeScript**, **Vite**, **Tailwind CSS**, **TanStack Query (React Query v5)**, and **@xyflow/react (React Flow 12)**.

The interface adheres to an operations-first, dark-mode-first aesthetic inspired by Linear, Datadog, Grafana, and Vercel. It is architected for high information density, low operational latency, and real-time incident intelligence.

```
+-----------------------------------------------------------------------------------+
|                                 React 18 SPA Shell                                |
|  +-----------------------------------------------------------------------------+  |
|  |                  QueryClientProvider (TanStack Query v5)                    |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  |                         ThemeProvider (Dark/Light)                    |  |  |
|  |  |  +-----------------------------------------------------------------+  |  |  |
|  |  |  |         AuthProvider (JWT, PyJWT payload, Tenant Context)       |  |  |  |
|  |  |  |  +-----------------------------------------------------------+  |  |  |  |
|  |  |  |  |                   BrowserRouter / React Router            |  |  |  |  |
|  |  |  |  |   +---------------------------------------------------+   |  |  |  |  |
|  |  |  |  |   | AppLayout: Collapsible Sidebar + Tenant/TopBar   |   |  |  |  |  |
|  |  |  |  |   |   +-------------------------------------------+   |   |  |  |  |  |
|  |  |  |  |   |   | Dashboard | Incidents | Investigations    |   |   |  |  |  |  |
|  |  |  |  |   |   | Topology  | Services  | Webhooks | Audit  |   |   |  |  |  |  |
|  |  |  |  |   |   +-------------------------------------------+   |   |  |  |  |  |
|  |  |  |  |   +---------------------------------------------------+   |  |  |  |  |
|  |  |  |  +-----------------------------------------------------------+  |  |  |  |
|  |  |  +-----------------------------------------------------------------+  |  |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Directory Structure

```
frontend/
├── index.html                    # HTML entry point with dark background bootstrap
├── package.json                  # React 18, Vite 5, Tailwind 3, Vitest, @xyflow/react
├── tsconfig.json                 # Strict TypeScript configuration
├── vite.config.ts                # Dev server (port 3000), /api proxy to FastAPI
├── tailwind.config.js            # Design tokens (brand, surface 50-950, danger, warning)
├── postcss.config.js             # PostCSS with tailwindcss and autoprefixer
└── src/
    ├── api/                      # Strongly typed REST API client modules
    │   ├── client.ts             # Axios instance with Bearer JWT & X-Organization-Id interceptor
    │   ├── auth.ts               # Login, register, current user profile
    │   ├── incidents.ts          # Incident CRUD, triage queue, resolution, memory search
    │   ├── investigations.ts     # AI investigations, grounded feedback review
    │   ├── topology.ts           # Service dependencies, cycles, blast radius
    │   ├── services.ts           # Service catalog management
    │   ├── projects.ts           # Project workspaces
    │   ├── webhooks.ts           # Audited provider deliveries
    │   ├── audit.ts              # SOC 2 immutable audit logs
    │   └── health.ts             # Engine and memory index health
    ├── components/
    │   ├── layout/               # Shell layout, Collapsible Sidebar, TopBar with org selector
    │   └── ui/                   # Badge, Button, Card, Modal, Input, Select, LoadingSpinner, EmptyState
    ├── context/
    │   ├── AuthContext.tsx       # Auth lifecycle, tenant switching, RBAC helpers
    │   └── ThemeContext.tsx      # Dark / light theme manager with localStorage sync
    ├── pages/
    │   ├── auth/                 # LoginPage, RegisterPage
    │   ├── dashboard/            # DashboardPage (KPI cards, charts, active criticals)
    │   ├── incidents/            # IncidentsPage (heap triage queue), IncidentDetailPage
    │   ├── investigations/       # InvestigationPage (AI SRE copilot, evidence grounding, review loop)
    │   ├── topology/             # TopologyPage (React Flow graph, blast radius, cycle banner)
    │   ├── services/             # ServicesPage (service catalog & blast radius modal)
    │   ├── projects/             # ProjectsPage (workspace initiatives)
    │   ├── webhooks/             # WebhooksPage (PagerDuty, Datadog, Alertmanager adapters)
    │   ├── audit/                # AuditLogsPage (compliance forensic trail)
    │   └── settings/             # SettingsPage (organization profile, RBAC membership)
    ├── test/                     # Vitest + React Testing Library test suites
    │   ├── setup.ts              # Jest DOM matchers, ResizeObserver & matchMedia mocks
    │   ├── auth.test.tsx         # Authentication and session management tests
    │   ├── rbac.test.tsx         # Role visibility and permission restriction tests
    │   ├── incidents.test.tsx    # Incident listing, heap triage queue, declaration tests
    │   ├── investigation.test.tsx# AI investigation findings and human review tests
    │   └── topology.test.tsx     # Graph topology, blast radius, cycle detection tests
    ├── types/                    # Comprehensive domain TypeScript interfaces & enums
    ├── App.tsx                   # Client-side router & ProtectedRoute wrappers
    ├── main.tsx                  # React DOM mount point
    └── index.css                 # Tailwind directives, custom scrollbars
```

---

## 3. Key Subsystems & Design Choices

### 3.1 Multi-Tenant Context & Authorization
- **Tenant Context (`X-Organization-Id`)**: The Axios client in `src/api/client.ts` automatically attaches `Authorization: Bearer <token>` and `X-Organization-Id: <org_id>` to all outgoing API calls.
- **Tenant Switching**: Users belonging to multiple organizations can instantly switch active organizations using the tenant dropdown in the TopBar. This updates `localStorage.getItem('recallops_org_id')` and invalidates TanStack Query caches to rehydrate data for the selected tenant.
- **Role-Based Access Control (RBAC)**: Enforces `ADMIN > ENGINEER > VIEWER` roles.
  - `isViewer`: Read-only access to metrics, telemetry, and audit logs.
  - `isEngineer`: Ability to trigger AI investigations, declare incidents, approve resolutions, and add services.
  - `isAdmin`: Full administrative rights including adding organization members and promoting/demoting user roles.
  - *Note: Frontend RBAC restrictions provide immediate user feedback; the FastAPI backend remains the authoritative boundary enforcing HTTP 403 Forbidden on all mutating endpoints.*

### 3.2 Dynamic Priority Triage Queue (Max-Heap)
- The Incidents page features a one-click toggle between standard table view and dynamic priority triage queue view.
- Triage queue displays priority scores computed by the backend's max-heap triage engine using the formula:
  $$\text{Score} = 0.40 \times \text{Severity} + 0.30 \times \text{Tier} + 0.20 \times \log(\text{Impacted Users} + 1)$$
- Critical high-impact outages automatically rise to the top of the queue.

### 3.3 Interactive Service Topology & Cascading Blast Radius
- Powered by `@xyflow/react` (React Flow 12).
- Visualizes directed dependency edges between services (`source_service -> target_service`).
- **DFS Cycle Detection**: If circular dependencies exist in the architecture graph, a red warning banner alerts engineers and lists the cyclic paths.
- **BFS Blast Radius Simulator**: Selecting an origin service queries `GET /api/v1/topology/blast-radius` and dynamically highlights downstream impacted services with hop distance badges and weight indicators.

### 3.4 Grounded AI Investigation & Human-in-the-Loop Oversight
- Seamlessly integrates with Phase 3's provider-independent LLM investigation engine.
- Renders:
  - Executive Diagnostic Summary
  - Probable Root Causes with confidence score progress bars
  - Grounded Evidence IDs (`EVID-INC-1`, `EVID-LOG-1`)
  - Verified Observed Facts
  - Recommended Remediation Runbooks with risk levels
  - Persistent Episodic Memory matches rehydrated from the relational database
- **Human Review Actions**:
  - **Approve & Commit to Memory**: Prompts the on-call engineer for their name/notes, resolves the incident in the database, and permanently indexes the verified resolution into persistent TF-IDF vector memory.
  - **Reject AI Hypothesis**: Prompts rejection feedback notes, rejects ungrounded suggestions from entering memory, and leaves the incident open for manual triage.

---

## 4. Verification & Testing

- **Type Safety**: Enforced via `tsc --noEmit`.
- **Production Build**: Bundled with Vite (`pnpm build`), producing minified and gzip-compressed production assets.
- **Component & Unit Testing**: 15 tests across 5 Vitest suites validating auth, RBAC enforcement, incidents lifecycle, AI investigations review, and service topology graphs.
