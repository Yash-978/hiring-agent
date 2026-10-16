import { API_URL, ApiError, apiRequest, clearToken, getToken } from "./client";
import type { ApplicationAnalysis } from "./types";

export interface ResumeFile {
  blob: Blob;
  mediaType: string;
  text: string | null;
}

export function getApplicationAnalysis(
  applicationId: number
): Promise<ApplicationAnalysis> {
  return apiRequest<ApplicationAnalysis>(`/applications/${applicationId}/analysis`);
}

export async function getApplicationResume(
  applicationId: number
): Promise<ResumeFile> {
  const token = getToken();
  const headers: HeadersInit = {};

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/applications/${applicationId}/resume`, {
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

  const blob = await response.blob();
  const mediaType = response.headers.get("content-type") ?? blob.type ?? "";
  const normalized = mediaType.toLowerCase();
  const text =
    normalized.startsWith("text/") || normalized.includes("json")
      ? await blob.text()
      : null;
  return { blob, mediaType, text };
}
