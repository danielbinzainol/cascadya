import { apiClient } from "@/api/client";
import type { ApiLiveAlertsPayload } from "@/types/controlPlane";

export function fetchLiveAlerts() {
  return apiClient<ApiLiveAlertsPayload>("/api/alerts/live");
}
