import { apiClient } from "@/api/client";
import type { ApiSessionUserPayload, ApiUiConfigPayload } from "@/types/controlPlane";

export function fetchCurrentUser() {
  return apiClient<ApiSessionUserPayload>("/api/me");
}

export function fetchUiConfig() {
  return apiClient<ApiUiConfigPayload>("/api/ui/config");
}
