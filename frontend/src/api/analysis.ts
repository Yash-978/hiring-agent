import { apiRequest } from "./client";
import type { ApplicationAnalysis } from "./types";

export function getApplicationAnalysis(
  applicationId: number
): Promise<ApplicationAnalysis> {
  return apiRequest<ApplicationAnalysis>(`/applications/${applicationId}/analysis`);
}
