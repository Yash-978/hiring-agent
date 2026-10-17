import type { TokenResponse, User, Candidate, Application, Approval, ApprovalCounts, Letter, AuditLog, Job, CandidateCreate, ApplicationCreate, ApprovalDecisionRequest, OfferDraftRequest, RegisterTenantRequest, JobCreate, JobUpdate, ApprovalRead, AuditLogRead, LetterRead, MetaInfo } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface ApiErrorData {
  status: number;
  message: string;
  data?: unknown;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly data?: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

function setToken(token: string): void {
  localStorage.setItem("access_token", token);
}

function clearToken(): void {
  localStorage.removeItem("access_token");
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }

  const contentType = response.headers.get("content-type");
  const isJson = contentType?.includes("application/json");

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    let data: unknown = undefined;

    if (isJson) {
      try {
        const errorData = await response.json();
        data = errorData;
        message = errorData.detail ?? errorData.message ?? message;
      } catch {
        message = await response.text();
      }
    } else {
      message = await response.text();
    }

    throw new ApiError(response.status, message, data);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (isJson) {
    return response.json();
  }

  return response.text() as T;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  return handleResponse<T>(response);
}

export async function apiUpload<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {};

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  return handleResponse<T>(response);
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString(),
  });

  return handleResponse<TokenResponse>(response);
}

// export async function registerTenant(data: RegisterTenantRequest): Promise<TokenResponse> {
//   return apiRequest<TokenResponse>("/auth/register-tenant", {
//     method: "POST",
//     body: JSON.stringify(data),
//   });
// }
export async function registerTenant(
  companyName: string,
  email: string,
  password: string,
): Promise<TokenResponse> {
  const baseUrl: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/auth/register-tenant`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name: companyName, email, password }),
  });
  if (!response.ok) {
    let message = "Registration failed";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg;
    } catch {
      // keep the default message
    }
    throw new Error(message);
  }
  return (await response.json()) as TokenResponse;
}
export async function approveApproval(id: number, note?: string): Promise<ApprovalRead> {
  return apiRequest<ApprovalRead>(`/approvals/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export async function getApprovalCounts(): Promise<ApprovalCounts> {
  return apiRequest<ApprovalCounts>("/approvals/counts");
}

export async function getJobs(): Promise<Job[]> {
  return apiRequest<Job[]>("/jobs");
}

export async function createJob(data: JobCreate): Promise<Job> {
  return apiRequest<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateJob(id: number, data: JobUpdate): Promise<Job> {
  return apiRequest<Job>(`/jobs/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getMeta(): Promise<MetaInfo> {
  return apiRequest<MetaInfo>("/meta");
}

export async function rejectApproval(id: number, note: string): Promise<ApprovalRead> {
  return apiRequest<ApprovalRead>(`/approvals/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export async function getApplicationAudit(id: number): Promise<AuditLogRead[]> {
  return apiRequest<AuditLogRead[]>(`/applications/${id}/audit`);
}

export async function createOfferDraft(
  applicationId: number,
  data: OfferDraftRequest
): Promise<Application> {
  return apiRequest<Application>(`/applications/${applicationId}/offer-draft`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function downloadLetter(letterId: number): Promise<Blob> {
  const token = getToken();
  const headers: HeadersInit = {};

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/letters/${letterId}/download`, {
    method: "GET",
    headers,
  });

  if (response.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      message = errorData.detail ?? errorData.message ?? message;
    } catch {
      message = await response.text();
    }
    throw new ApiError(response.status, message);
  }

  return response.blob();
}

export { getToken, setToken, clearToken, API_URL };
export type { User, Candidate, Application, Approval, ApprovalCounts, Letter, AuditLog, Job, CandidateCreate, ApplicationCreate, ApprovalDecisionRequest, OfferDraftRequest, RegisterTenantRequest, TokenResponse, JobCreate, JobUpdate, ApprovalRead, AuditLogRead, LetterRead, MetaInfo };