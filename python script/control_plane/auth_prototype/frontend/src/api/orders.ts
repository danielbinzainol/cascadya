import { apiClient } from "@/api/client";
import type { ApiOrdersDispatchPayload, ApiOrdersFeedPayload } from "@/types/controlPlane";

export interface FetchOrdersOptions {
  limit?: number;
}

export interface DispatchOrderPayload {
  subject?: string;
  timeout_seconds?: number;
  command_payload: Record<string, unknown>;
}

export function fetchLiveOrders(options: FetchOrdersOptions = {}) {
  const params = new URLSearchParams();
  if (typeof options.limit === "number" && Number.isFinite(options.limit)) {
    params.set("limit", String(options.limit));
  }

  const query = params.toString();
  return apiClient<ApiOrdersFeedPayload>(`/api/orders/live${query ? `?${query}` : ""}`);
}

export function dispatchOrderCommand(payload: DispatchOrderPayload) {
  return apiClient<ApiOrdersDispatchPayload>("/api/orders/dispatch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}
