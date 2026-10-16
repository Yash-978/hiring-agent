export interface User {
  id: number;
  tenant_id: number;
  email: string;
  role: string;
  created_at: string;
}

export interface Job {
  id: number;
  title: string;
  description: string;
  status: string;
  created_at: string;
}

export interface JobCreate {
  title: string;
  description: string;
  status?: string;
}

export interface Candidate {
  id: number;
  full_name: string;
  email: string;
  resume_text: string | null;
  parsed_data: Record<string, unknown> | null;
  created_at: string;
}

export interface CandidateCreate {
  full_name: string;
  email: string;
  resume_text?: string;
  parsed_data?: Record<string, unknown>;
}

export interface Application {
  id: number;
  candidate_id: number;
  job_id: number;
  candidate_name: string;
  job_title: string;
  status: string;
  score: number | null;
  score_reasoning: string | null;
  created_at: string;
  payload?: Record<string, unknown> | null;
}

export interface ApplicationCreate {
  candidate_id: number;
  job_id: number;
}

export interface Approval {
  id: number;
  tenant_id: number;
  action_type: string;
  target_type: string;
  target_id: number;
  payload: Record<string, unknown> | null;
  status: string;
  requested_by: number;
  decided_by_user_id: number | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string;
}

export interface ApprovalRead {
  id: number;
  tenant_id: number;
  action_type: string;
  target_type: string;
  target_id: number;
  payload: Record<string, unknown> | null;
  status: string;
  requested_by: number;
  decided_by_user_id: number | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string;
}

export interface AuditLogRead {
  id: number;
  actor_type: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: number;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface ApprovalDecisionRequest {
  note?: string;
}

export interface Letter {
  id: number;
  tenant_id: number;
  application_id: number;
  approval_id: number | null;
  content: string | null;
  file_path: string | null;
  created_at: string;
}

export interface LetterRead {
  id: number;
  tenant_id: number;
  application_id: number;
  approval_id: number | null;
  content: string | null;
  file_path: string | null;
  created_at: string;
}

export interface OfferDraftRequest {
  salary: number;
  currency: string;
  start_date: string;
}

export interface AuditLog {
  id: number;
  tenant_id: number;
  actor_type: "agent" | "user" | "system";
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: number;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterTenantRequest {
  company_name: string;
  email: string;
  password: string;
}