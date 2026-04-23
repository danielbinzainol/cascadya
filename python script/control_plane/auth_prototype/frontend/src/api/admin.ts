import { apiClient } from "@/api/client";
import type { ApiAdminUserPayload, RbacCatalogPayload, RoleName } from "@/types/controlPlane";

export interface AdminUsersResponse {
  users: ApiAdminUserPayload[];
}

export interface AdminInvitePayload {
  email: string;
  first_name?: string;
  last_name?: string;
  role_names: RoleName[];
}

export interface AdminProfilePayload {
  email: string;
  first_name?: string;
  last_name?: string;
}

export interface AdminRolesPayload {
  role_names: RoleName[];
}

export interface AdminStatusPayload {
  is_active: boolean;
}

export interface AdminInviteResponse {
  user: ApiAdminUserPayload;
}

export interface AdminDeleteResponse {
  status: string;
  user_id: number;
  email: string;
  keycloak_user_deleted: boolean;
  warning?: string;
}

export function fetchAdminUsers() {
  return apiClient<AdminUsersResponse>("/api/admin/users");
}

export function fetchAdminRbacCatalog() {
  return apiClient<RbacCatalogPayload>("/api/admin/rbac/catalog");
}

export function inviteAdminUser(payload: AdminInvitePayload) {
  return apiClient<AdminInviteResponse>("/api/admin/users/invite", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function updateAdminUserProfile(userId: number, payload: AdminProfilePayload) {
  return apiClient<ApiAdminUserPayload>(`/api/admin/users/${userId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function updateAdminUserRoles(userId: number, payload: AdminRolesPayload) {
  return apiClient<ApiAdminUserPayload>(`/api/admin/users/${userId}/roles`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function updateAdminUserStatus(userId: number, payload: AdminStatusPayload) {
  return apiClient<ApiAdminUserPayload>(`/api/admin/users/${userId}/status`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function deleteAdminUser(userId: number) {
  return apiClient<AdminDeleteResponse>(`/api/admin/users/${userId}`, {
    method: "DELETE",
  });
}
