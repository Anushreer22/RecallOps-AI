# RecallOps-AI — Frontend Setup & Quick Start Guide

This guide details how to configure, run, test, and build the RecallOps-AI frontend application.

---

## 1. Prerequisites

- **Node.js**: v18.0.0 or higher (v20+ recommended)
- **pnpm**: v8.0.0 or higher
- **Backend API**: The FastAPI backend must be running on `http://127.0.0.1:8000` (see main README for backend startup instructions).

---

## 2. Installation

Navigate to the `frontend/` directory and install dependencies:

```bash
cd frontend
pnpm install
```

---

## 3. Environment Configuration

The frontend Vite development server is pre-configured with a proxy in `vite.config.ts`:

- Any API request to `/api/*` is automatically proxied to `http://127.0.0.1:8000/api/*`.

To customize the backend URL directly, you can create a `.env` file in `frontend/`:

```env
VITE_API_URL=http://127.0.0.1:8000/api/v1
```

---

## 4. Running the Development Server

Start the local Vite development server:

```bash
cd frontend
pnpm dev
```

The application will be accessible at:
```
http://localhost:3000
```

---

## 5. Running Automated Tests

Run the frontend Vitest test suite in single-run mode:

```bash
cd frontend
pnpm test
```

Or run Vitest in watch mode:

```bash
cd frontend
pnpm exec vitest
```

---

## 6. Type Checking

Validate TypeScript types without emitting code:

```bash
cd frontend
pnpm typecheck
```

---

## 7. Production Build

Compile TypeScript and bundle optimized static assets with Vite:

```bash
cd frontend
pnpm build
```

Production artifacts will be generated in `frontend/dist/`.

To preview the production build locally:

```bash
cd frontend
pnpm preview
```
