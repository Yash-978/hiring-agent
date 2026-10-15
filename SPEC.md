# SPEC: Hiring Agent MVP

## Product
Multi-tenant hiring-to-joining paperwork system for small companies (10-200
people). AI agents parse, draft and file; a human approves every decision that
matters. First use: our own internal hiring. Then micro-SaaS.

## MVP flow
1. Create a Job. Create a Candidate and an Application.
2. Upload a resume (.pdf or .txt). The resume agent parses it and scores it
   against the job. This creates a pending Approval (shortlist).
3. An admin/approver approves or rejects the shortlist.
4. After approval, create an offer draft (salary, currency, start date). The
   offer agent drafts the letter. This creates a pending Approval (offer_letter).
5. After approval, a .docx is generated and can be downloaded.
6. Every step writes an AuditLog entry, visible as a timeline.

## Entities
Tenant, User, Job, Candidate, Application, Approval, AuditLog, Letter.
All except Tenant have tenant_id.

## Approval
id, tenant_id, action_type (shortlist | offer_letter), target_type, target_id,
payload (JSON), status (pending | approved | rejected), requested_by,
decided_by_user_id, decided_at, decision_note, created_at.
Rules: only admin or approver may decide; only pending approvals can be
decided; decisions are tenant-scoped.

## AuditLog (append-only)
id, tenant_id, actor_type (agent | user | system), actor_name, action,
entity_type, entity_id, details (JSON), created_at.

## Roles
admin, approver, member. Members can create and upload but cannot approve.

## Application status lifecycle
new -> analyzed -> shortlist_approved | shortlist_rejected -> offer_drafted
-> offer_approved | offer_rejected.

## Backend layout (backend/app)
main.py, config.py, db.py, deps.py, models/, schemas/, routes/, services/,
agents/. Tests in backend/tests/.

## Environment variables (backend/.env)
SECRET_KEY, DATABASE_URL, LLM_PROVIDER (fake | gemini), GEMINI_API_KEY,
GEMINI_MODEL.

## Out of scope for the MVP
Real email sending, calendar sync, e-signatures, billing, document
collection, interview scheduling, revised and joining letters, Alembic
migrations.