# Project: Hiring Agent

Multi-tenant hiring-to-joining paperwork system. AI agents prepare; humans decide.

## Core principle (never violate)
No offer letter, salary, shortlist/hiring decision or any outgoing document may
be finalized or released without an Approval row with status "approved",
checked through require_approved(). Every agent action and every human
decision writes an append-only AuditLog entry.

## Stack
- Backend: Python 3.11, FastAPI, SQLModel, PostgreSQL (dev), pytest.
  Tests use in-memory SQLite, so all models must work on both.
- Auth: PyJWT and the bcrypt library directly. NEVER use passlib or python-jose.
- AI: google-genai (Gemini) behind an LLMClient protocol. LLM_PROVIDER=fake in tests.
- Frontend: Vite + React + TypeScript + Tailwind v4 + shadcn/ui (Radix).
  Use the components already in frontend/src/components/ui. Do not add other
  UI libraries. Import with the "@/" alias.

## Backend rules
- Layout: backend/app/{models,schemas,routes,services,agents}/. Routes stay
  thin and only call services. Business logic lives in services.
- Type hints everywhere. Use absolute imports (from app.x import y).
- Every table except Tenant has an indexed tenant_id. Every query filters by
  current_user.tenant_id. Foreign ids from request bodies must be verified to
  belong to the same tenant, returning 404 otherwise.
- Portable types only: JSON via sa_column=Column(JSON); enums stored as
  strings; datetimes via datetime.now(timezone.utc), never utcnow.
- LLM output must be validated with Pydantic models. Retry once, then fail
  safely. Never trust raw text.
- Never log resume text, salaries, passwords, tokens or API keys.
- AuditLog has NO update and NO delete code anywhere.
- Secrets only in backend/.env. Never hardcode keys.
- Every new endpoint gets pytest tests, including a cross-tenant test.

## Frontend rules
- API calls only inside src/api/. No `any` types.
- Every data view needs loading, empty and error states.
- Send the auth token via the shared API client, never ad hoc.

## Working rules
- Make the smallest change that satisfies the task. Do not rewrite files you
  were not asked to touch. Do not add features that were not requested.
- Ask before adding any new dependency.
- Run `pytest -q` (backend) and `npm run build` (frontend) before saying done.
- If something is ambiguous, state your assumption in one line and continue.