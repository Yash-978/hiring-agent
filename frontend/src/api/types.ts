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
  candidate_count: number;
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
  candidate_name: string | null;
  job_title: string | null;
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
  candidate_name: string | null;
  job_title: string | null;
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

export interface AnalysisJobRef {
  id: number;
  title: string;
}

export interface AnalysisCandidate {
  full_name: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  current_title: string | null;
  total_years_experience: number | null;
  education: string[];
  skills: string[];
}

export interface AnalysisCriterion {
  criterion: string;
  kind: string;
  verdict: string;
  evidence: string;
  evidence_verified: boolean;
  note: string;
}

export interface AnalysisBreakdownEntry {
  ratio: number;
  weight: number;
  count: number;
}

export interface ApplicationAnalysis {
  application_id: number;
  job: AnalysisJobRef;
  candidate: AnalysisCandidate;
  criteria: AnalysisCriterion[];
  score: number;
  breakdown: Record<string, AnalysisBreakdownEntry>;
  strengths: string[];
  concerns: string[];
  questions_for_candidate: string[];
  recommendation: string;
  confidence: string;
  flags: string[];
  model: string;
  prompt_version: string;
  resume_available: boolean;
}

export interface CompareJob {
  id: number;
  title: string;
  must_have_skills: string[];
  nice_to_have_skills: string[];
}

export interface CompareCriterion {
  criterion: string;
  kind: string;
  verdict: string;
}

export interface CompareCandidate {
  application_id: number;
  name: string;
  score: number | null;
  recommendation: string;
  confidence: string;
  years: number | null;
  breakdown: Record<string, number>;
  criteria: CompareCriterion[];
  flags: string[];
}

export interface JobComparisonCounts {
  total: number;
  scored: number;
}

export interface JobComparison {
  job: CompareJob;
  candidates: CompareCandidate[];
  counts: JobComparisonCounts;
}