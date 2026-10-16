# Hiring Agent

Multi-tenant hiring-to-joining paperwork system. **AI agents prepare; humans decide.**

## What it is

A small-company (10–200 people) platform that automates the document-heavy parts of hiring while keeping every meaningful decision behind a human approval gate. Built first for internal use, then as a micro-SaaS.

**MVP flow:**
1. Create a Job → Create Candidate & Application
2. Upload resume (PDF/TXT) → AI parses & scores → creates **pending shortlist approval**
3. Admin/approver **approves or rejects** the shortlist
4. After approval → create offer draft (salary, currency, start date) → AI drafts letter → creates **pending offer-letter approval**
5. After approval → generate & download .docx
6. Every step writes an **append-only AuditLog** visible as a timeline

---

## Core Principle (never violate)

> No offer letter, salary, shortlist/hiring decision, or any outgoing document may be finalized or released without an `Approval` row with `status = "approved"`, checked through `require_approved()`. Every agent action and every human decision writes an append-only `AuditLog` entry.

---

## Architecture (text diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vite + React)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Login     │  │ Candidates  │  │  Approvals  │             │
│  │   Page      │──│   Table     │──│  (Tabs)     │             │
│  └─────────────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────────────────────────────────────┐               │
│  │          api/client.ts (fetch wrapper)      │               │
│  │  • Bearer token from localStorage           │               │
│  │  • 401 → clear token + redirect /login      │               │
│  │  • apiUpload() for multipart resume upload  │               │
│  └─────────────────────────────────────────────┘               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS (VITE_API_URL)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ /auth      │ │ /jobs      │ │ /candidates│ │/applications│   │
│  │  login     │ │  CRUD      │ │  CRUD      │ │  CRUD       │   │
│  │  /me       │ │            │ │            │ │  /analyze   │   │
│  └────────────┘ └────────────┘ └────────────┘ │  /offer-dft │   │
│                                               │  /{id}/audit│   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ └────────────┘   │
│  │ /approvals │ │ /letters   │ │ agents/    │                  │
│  │  list      │ │  /{id}/gen │ │  resume    │                  │
│  │  /approve  │ │  /download │ │  offer     │                  │
│  │  /reject   │ └────────────┘ └────────────┘                  │
│  └────────────┘                                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │ SQLModel
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATABASE (PostgreSQL / SQLite)              │
│  Tables: tenant, user, job, candidate, application, approval,  │
│          auditlog, letter                                      │
│  All except tenant have tenant_id (indexed)                    │
└─────────────────────────────────────────────────────────────────┘
```

**Key backend layout** (`backend/app/`):
```
main.py              # FastAPI app, CORS, router includes
config.py            # Settings from .env (pydantic-settings)
db.py                # SQLModel engine, create_db_and_tables, get_session
deps.py              # get_current_user, require_role
models/              # SQLModel table definitions
schemas/             # Pydantic request/response models
routes/              # Thin routers → call services only
services/            # Business logic, audit logging, approvals
agents/              # LLMClient protocol, resume_agent, offer_agent
```

---

## Setup (Windows)

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL (or use SQLite for local dev)

### 1. Backend

```powershell
cd backend

# Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your values:
# SECRET_KEY=your-secret
# DATABASE_URL=sqlite:///./demo.db  (or postgresql+psycopg://...)
# LLM_PROVIDER=fake   (use "gemini" for real LLM)

# Create tables & seed demo data
python scripts\seed.py
# → Creates tenant "Demo Co", admin@demo.test / demo123, a job, 2 candidates, 2 applications

# Run server
uvicorn app.main:app --reload --port 8000
# API at http://localhost:8000
# Swagger at http://localhost:8000/docs
```

### 2. Frontend

```powershell
cd frontend

# Configure API URL
# .env already exists with: VITE_API_URL=http://localhost:8000

# Install deps
npm install

# Run dev server
npm run dev
# App at http://localhost:5173
```

---

## Running Tests

### Backend (pytest, in-memory SQLite)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
# 40 tests, including cross-tenant isolation checks
```

### Frontend
```powershell
cd frontend
npm run lint      # ESLint
npm run build     # TypeScript + Vite build
```

---

## Demo Script (the 8 clicks of the full flow)

> **Login:** `admin@demo.test` / `demo123`

| # | Action | Expected |
|---|--------|----------|
| 1 | Open http://localhost:5173 → **Login** | Redirected to `/candidates` |
| 2 | Click **"New job"** → Title: "Backend Engineer", Description: "Python, FastAPI, Postgres" → **Create** | Job appears in select dropdown |
| 3 | Click **"New candidate"** → Name: "Alice Smith", Email: "alice@example.com", Job: "Backend Engineer", Resume: upload `resume.txt` (or PDF) → **Add candidate** | Toast "Candidate added and analysis complete" |
| 4 | Table row appears with **score** (e.g. 8.5) and status **"shortlist pending"** | AI analysis + audit entry created |
| 5 | Click **"Approvals"** tab → **Pending** tab shows shortlist approval → Click **Approve** → optional note → **Approve** | Status → **approved**, decided-by & time shown |
| 6 | Back to **Candidates** → row status now **"shortlisted"** | Application status updated |
| 7 | Click row → **Candidate Detail** → Click **"Create Offer"** → Salary: 120000, Currency: USD, Start Date: tomorrow → **Create Offer** | Offer draft created, approval appears in Approvals |
| 8 | **Approvals** → Pending → Approve offer → Back to Candidate Detail → **"Download Letter (.docx)"** button visible → Click → `.docx` downloads | Full flow complete |

---

## Known Limitations / Next Steps

| Area | Limitation | Next Step |
|------|------------|-----------|
| **Migrations** | No Alembic; `create_db_and_tables()` only | Add Alembic for schema evolution |
| **Auth** | JWT in localStorage; no refresh token rotation | Add httpOnly cookie + refresh endpoint |
| **LLM** | `LLM_PROVIDER=fake` returns canned responses | Wire real Gemini (`google-genai`) with retries/validation |
| **Email** | No notifications on approval/events | Add SMTP / SendGrid / Resend integration |
| **Documents** | Only offer letter .docx; no revised/joining letters | Add revised-offer, joining-letter templates |
| **Calendar** | No interview scheduling | Add `/interviews` endpoints + calendar sync |
| **E-sign** | No digital signature | Integrate DocuSign / Dropbox Sign |
| **Billing** | No subscription/metering | Add Stripe + usage-based pricing |
| **File storage** | Local `backend/storage/` only | S3 / R2 / Azure Blob for multi-instance |
| **RBAC** | Admin/approver/member only | Add granular permissions (e.g., `can_create_job`) |
| **Audit** | No tamper-evidence (hash chain) | Add hash-chain or Merkle tree to AuditLog |
| **Tests** | No frontend E2E (Playwright) | Add critical path E2E tests |
| **Observability** | No metrics/tracing | Add OpenTelemetry + Prometheus/Grafana |

---

## License

Internal / proprietary. Not for public distribution.