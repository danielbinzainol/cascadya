<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import {
  deleteAdminUser,
  fetchAdminRbacCatalog,
  fetchAdminUsers,
  inviteAdminUser,
  updateAdminUserProfile,
  updateAdminUserRoles,
  updateAdminUserStatus,
} from "@/api/admin";
import { ApiError } from "@/api/client";
import MetricCard from "@/components/ui/MetricCard.vue";
import StatusBadge from "@/components/ui/StatusBadge.vue";
import RoleDropdownField from "@/modules/admin/components/RoleDropdownField.vue";
import { statusTone } from "@/mocks/controlPlane";
import { useAppStore } from "@/stores/app";
import { useSessionStore } from "@/stores/session";
import type {
  AdminUserRecord,
  ApiAdminUserPayload,
  DashboardMetric,
  ManagedUserSnapshot,
  RbacRoleCatalogEntry,
  RoleName,
} from "@/types/controlPlane";

interface InviteFormState {
  email: string;
  firstName: string;
  lastName: string;
  roleNames: RoleName[];
}

interface UserDraftState {
  email: string;
  firstName: string;
  lastName: string;
  roleNames: RoleName[];
}

const appStore = useAppStore();
const session = useSessionStore();
const route = useRoute();

const mockRoleCatalog: RbacRoleCatalogEntry[] = [
  {
    name: "viewer",
    description: "Lecture seule sur les sites et l'inventaire.",
    permissions: ["dashboard:read", "inventory:read", "site:read"],
  },
  {
    name: "operator",
    description: "Operateur standard du control panel.",
    permissions: ["dashboard:read", "inventory:read", "inventory:scan", "site:read"],
  },
  {
    name: "provisioning_manager",
    description: "Operateur habilite a preparer et lancer un provisionnement.",
    permissions: [
      "dashboard:read",
      "inventory:read",
      "inventory:scan",
      "provision:prepare",
      "provision:run",
      "provision:cancel",
      "site:read",
    ],
  },
  {
    name: "admin",
    description: "Administrateur applicatif avec toutes les permissions du catalogue.",
    permissions: [
      "audit:read",
      "dashboard:read",
      "inventory:read",
      "inventory:scan",
      "provision:prepare",
      "provision:run",
      "provision:cancel",
      "site:read",
      "site:write",
      "user:read",
      "user:write",
      "role:assign",
    ],
  },
];

const loading = ref(false);
const actionKey = ref<string | null>(null);
const backendUsers = ref<AdminUserRecord[]>([]);
const roleCatalog = ref<RbacRoleCatalogEntry[]>([]);
const noticeMessage = ref<string | null>(null);
const warningMessage = ref<string | null>(null);
const errorMessage = ref<string | null>(null);
const drafts = ref<Record<number, UserDraftState>>({});
const inviteForm = ref<InviteFormState>({
  email: "",
  firstName: "",
  lastName: "",
  roleNames: [],
});

const sessionEmail = computed(() => session.user?.email ?? "session@unknown");
const sessionLabel = computed(() =>
  session.demoModeEnabled ? "Session admin de demonstration" : "Session admin FastAPI / Keycloak",
);
const routeNoticeMessage = computed(() => {
  const value = route.query.message;
  return typeof value === "string" ? value : null;
});
const routeWarningMessage = computed(() => {
  const value = route.query.warning;
  return typeof value === "string" ? value : null;
});
const routeErrorMessage = computed(() => {
  const value = route.query.error;
  return typeof value === "string" ? value : null;
});
const canInviteUsers = computed(() => session.hasPermission("user:write"));
const canAssignRoles = computed(() => session.hasPermission("role:assign"));
const canToggleUsers = computed(() => session.hasPermission("user:write"));
const canManageIdentity = computed(() => session.isAdmin);
const canDeleteUsers = computed(() => session.isAdmin);

function toErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Une erreur inconnue est survenue.";
}

function splitDisplayName(displayName: string) {
  const parts = displayName.split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return { firstName: "", lastName: "" };
  }
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: "" };
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(" "),
  };
}

function formatLastLoginLabel(lastLoginAt: string | null) {
  if (!lastLoginAt) {
    return "jamais";
  }

  const parsed = new Date(lastLoginAt);
  if (Number.isNaN(parsed.getTime())) {
    return lastLoginAt;
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

function mapApiAdminUser(user: ApiAdminUserPayload): AdminUserRecord {
  const names = splitDisplayName(user.display_name);
  return {
    id: user.id,
    keycloakUuid: user.keycloak_uuid,
    username: user.username,
    email: user.email,
    displayName: user.display_name,
    firstName: names.firstName,
    lastName: names.lastName,
    roles: user.roles,
    permissions: user.permissions,
    isActive: user.is_active,
    lastLoginAt: user.last_login_at,
    lastLoginLabel: formatLastLoginLabel(user.last_login_at),
    authSource: user.auth_source,
  };
}

function mapMockAdminUser(user: ManagedUserSnapshot): AdminUserRecord {
  const names = splitDisplayName(user.displayName);
  return {
    id: user.id,
    keycloakUuid: null,
    username: user.email,
    email: user.email,
    displayName: user.displayName,
    firstName: names.firstName,
    lastName: names.lastName,
    roles: user.roles,
    permissions: [],
    isActive: user.isActive,
    lastLoginAt: null,
    lastLoginLabel: user.lastLoginLabel,
    authSource: user.authSource,
  };
}

function setDrafts(users: AdminUserRecord[]) {
  drafts.value = Object.fromEntries(
    users.map((user) => [
      user.id,
        {
          email: user.email,
          firstName: user.firstName,
          lastName: user.lastName,
          roleNames: [...user.roles],
        },
      ]),
  );
}

function getDraft(userId: number): UserDraftState {
  return (
    drafts.value[userId] ?? {
      email: "",
      firstName: "",
      lastName: "",
      roleNames: [],
    }
  );
}

function setDraftValue(userId: number, field: "email" | "firstName" | "lastName", value: string) {
  drafts.value = {
    ...drafts.value,
    [userId]: {
      ...getDraft(userId),
      [field]: value,
    },
  };
}

function setDraftRoles(userId: number, roleNames: RoleName[]) {
  drafts.value = {
    ...drafts.value,
    [userId]: {
      ...getDraft(userId),
      roleNames: [...roleNames],
    },
  };
}

const displayedUsers = computed(() =>
  session.demoModeEnabled ? appStore.adminUsers.map(mapMockAdminUser) : backendUsers.value,
);
const displayedRoleCatalog = computed(() => (session.demoModeEnabled ? mockRoleCatalog : roleCatalog.value));

const metrics = computed<DashboardMetric[]>(() => {
  const users = displayedUsers.value;
  return [
    {
      title: "Utilisateurs actifs",
      value: String(users.filter((user) => user.isActive).length),
      subtitle: `${users.length} comptes miroir`,
      tone: "healthy",
    },
    {
      title: "Admins",
      value: String(users.filter((user) => user.roles.includes("admin")).length),
      subtitle: "Gestion IAM",
      tone: "admin",
    },
    {
      title: "Operators",
      value: String(users.filter((user) => user.roles.includes("operator")).length),
      subtitle: "Runbooks et supervision",
      tone: "running",
    },
    {
      title: "Viewers",
      value: String(users.filter((user) => user.roles.includes("viewer")).length),
      subtitle: "Lecture seule",
      tone: "neutral",
    },
  ];
});

async function refreshUsers() {
  if (session.demoModeEnabled) {
    const mockUsers = appStore.adminUsers.map(mapMockAdminUser);
    setDrafts(mockUsers);
    return;
  }

  const response = await fetchAdminUsers();
  const users = response.users.map(mapApiAdminUser).sort((left, right) => left.email.localeCompare(right.email));
  backendUsers.value = users;
  setDrafts(users);
}

async function loadAdminData() {
  noticeMessage.value = null;
  warningMessage.value = null;
  errorMessage.value = null;

  if (session.demoModeEnabled) {
    await refreshUsers();
    return;
  }

  loading.value = true;
  try {
    const [usersResponse, catalogResponse] = await Promise.all([fetchAdminUsers(), fetchAdminRbacCatalog()]);
    const users = usersResponse.users.map(mapApiAdminUser).sort((left, right) => left.email.localeCompare(right.email));
    backendUsers.value = users;
    roleCatalog.value = catalogResponse.roles;
    setDrafts(users);
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

async function runAction(key: string, task: () => Promise<void>) {
  actionKey.value = key;
  noticeMessage.value = null;
  warningMessage.value = null;
  errorMessage.value = null;

  try {
    await task();
  } catch (error) {
    errorMessage.value = toErrorMessage(error);
  } finally {
    actionKey.value = null;
  }
}

async function handleInvite() {
  if (session.demoModeEnabled) {
    warningMessage.value = "Mode demo : l'invitation reelle est disponible uniquement quand la SPA est branchee au backend.";
    return;
  }

  await runAction("invite", async () => {
    const response = await inviteAdminUser({
      email: inviteForm.value.email,
      first_name: inviteForm.value.firstName,
      last_name: inviteForm.value.lastName,
      role_names: canAssignRoles.value ? inviteForm.value.roleNames : [],
    });
    inviteForm.value = {
      email: "",
      firstName: "",
      lastName: "",
      roleNames: [],
    };
    noticeMessage.value = `Le compte ${response.user.email} a bien ete cree dans Keycloak et dans le RBAC metier.`;
    await refreshUsers();
  });
}

async function handleProfileSave(user: AdminUserRecord) {
  const draft = getDraft(user.id);
  await runAction(`profile:${user.id}`, async () => {
    await updateAdminUserProfile(user.id, {
      email: draft.email,
      first_name: draft.firstName,
      last_name: draft.lastName,
    });
    noticeMessage.value = `Le profil de ${draft.email} a bien ete mis a jour.`;
    await refreshUsers();
  });
}

async function handleRolesSave(user: AdminUserRecord) {
  const draft = getDraft(user.id);
  await runAction(`roles:${user.id}`, async () => {
    await updateAdminUserRoles(user.id, {
      role_names: draft.roleNames,
    });
    noticeMessage.value = `Les roles de ${user.email} ont bien ete mis a jour.`;
    await refreshUsers();
  });
}

async function handleStatusToggle(user: AdminUserRecord) {
  await runAction(`status:${user.id}`, async () => {
    await updateAdminUserStatus(user.id, {
      is_active: !user.isActive,
    });
    noticeMessage.value = `${user.email} a ete ${user.isActive ? "desactive" : "reactive"} avec succes.`;
    await refreshUsers();
  });
}

async function handleDelete(user: AdminUserRecord) {
  if (typeof window !== "undefined") {
    const confirmed = window.confirm(`Supprimer definitivement ${user.email} de Keycloak et du RBAC local ?`);
    if (!confirmed) {
      return;
    }
  }

  await runAction(`delete:${user.id}`, async () => {
    const response = await deleteAdminUser(user.id);
    noticeMessage.value = `Utilisateur ${response.email} supprime de Keycloak et du RBAC local.`;
    warningMessage.value = response.warning ?? null;
    await refreshUsers();
  });
}

function isBusy(key: string) {
  return actionKey.value === key;
}

onMounted(() => {
  void loadAdminData();
});
</script>

<template>
  <section class="stack-card">
    <header class="page-heading">
      <div>
        <p class="muted-2 uppercase">Admin only zone</p>
        <h1>Gestion des acces</h1>
      </div>
      <div class="current-admin">
        <p class="muted">{{ sessionLabel }}</p>
        <p class="mono">{{ sessionEmail }}</p>
      </div>
    </header>

    <section class="metric-grid">
      <MetricCard
        v-for="metric in metrics"
        :key="metric.title"
        :title="metric.title"
        :value="metric.value"
        :subtitle="metric.subtitle"
        :tone="metric.tone"
      />
    </section>

    <section v-if="noticeMessage || routeNoticeMessage" class="notice-shell notice-ok">
      {{ noticeMessage || routeNoticeMessage }}
    </section>

    <section v-if="warningMessage || routeWarningMessage" class="notice-shell notice-warning">
      {{ warningMessage || routeWarningMessage }}
    </section>

    <section v-if="errorMessage || routeErrorMessage" class="notice-shell notice-error">
      {{ errorMessage || routeErrorMessage }}
    </section>

    <section v-if="loading" class="note-shell">
      <h2>Chargement IAM</h2>
      <p class="helper-text">Lecture des utilisateurs miroir et du catalogue RBAC...</p>
    </section>

    <div class="admin-grid">
      <section class="note-shell">
        <div class="card-heading">
          <div>
            <p class="muted-2 uppercase">Identite</p>
            <h2>Ton compte</h2>
          </div>
          <StatusBadge :label="session.user?.authSource ?? 'unknown'" :tone="session.user?.authSource === 'oidc' ? 'healthy' : 'warning'" compact />
        </div>
        <div class="identity-stack">
          <p class="identity-name">{{ session.user?.displayName ?? "Session inconnue" }}</p>
          <p class="helper-text">{{ session.user?.email ?? "Pas d'email disponible" }}</p>
          <div class="role-stack">
            <StatusBadge
              v-for="role in session.user?.roles ?? []"
              :key="role"
              :label="role"
              :tone="role"
              compact
            />
          </div>
          <p class="helper-text">
            Permissions actuelles :
            <span class="mono">{{ (session.user?.permissions ?? []).join(", ") || "aucune" }}</span>
          </p>
        </div>
      </section>

      <section class="note-shell">
        <div class="card-heading">
          <div>
            <p class="muted-2 uppercase">Catalogue</p>
            <h2>Roles metier</h2>
          </div>
          <button class="button-secondary" type="button" :disabled="loading || !!actionKey" @click="loadAdminData">
            Rafraichir
          </button>
        </div>
        <div class="catalog-list">
          <article v-for="role in displayedRoleCatalog" :key="role.name" class="catalog-item">
            <div class="catalog-title">
              <StatusBadge :label="role.name" :tone="statusTone(role.name)" compact />
              <span class="helper-text">{{ role.permissions.length }} permissions</span>
            </div>
            <p class="catalog-description">{{ role.description }}</p>
            <p class="helper-text">
              <span class="mono">{{ role.permissions.join(", ") }}</span>
            </p>
          </article>
        </div>
      </section>
    </div>

    <section v-if="canInviteUsers" class="note-shell">
        <div class="card-heading">
          <div>
            <p class="muted-2 uppercase">Invitation</p>
            <h2>Creer un utilisateur</h2>
          </div>
        <StatusBadge :label="session.demoModeEnabled ? 'demo' : 'backend'" :tone="session.demoModeEnabled ? 'neutral' : 'healthy'" compact />
      </div>
      <p class="helper-text invite-copy">
        Le compte est cree dans Keycloak, puis un utilisateur miroir est cree tout de suite dans le RBAC metier.
        Le mot de passe temporaire reste gere dans Keycloak.
      </p>
      <form class="invite-form" @submit.prevent="handleInvite">
        <label class="field">
          <span>Email</span>
          <input v-model="inviteForm.email" type="email" placeholder="luc.payen@cascadya.com" required />
        </label>

        <div class="field-row">
          <label class="field">
            <span>Prenom</span>
            <input v-model="inviteForm.firstName" placeholder="Luc" />
          </label>
          <label class="field">
            <span>Nom</span>
            <input v-model="inviteForm.lastName" placeholder="Payen" />
          </label>
        </div>

        <label class="field">
          <span>Roles initiaux</span>
          <RoleDropdownField
            v-model="inviteForm.roleNames"
            :options="displayedRoleCatalog"
            :disabled="!canAssignRoles"
          />
        </label>

        <div class="action-row">
          <button class="button-primary" type="submit" :disabled="isBusy('invite')">
            {{ isBusy("invite") ? "Creation..." : "Creer l'utilisateur" }}
          </button>
          <p v-if="!canAssignRoles" class="helper-text">
            Tu peux creer le compte, mais pas attribuer de roles initiaux sans <code>role:assign</code>.
          </p>
        </div>
      </form>
    </section>

    <section class="table-shell">
      <div class="table-header">
        <div>
          <p class="muted-2 uppercase">Utilisateurs</p>
          <h2>Comptes miroir Keycloak / RBAC</h2>
        </div>
        <StatusBadge :label="`${displayedUsers.length} comptes`" tone="neutral" compact />
      </div>

      <table class="user-table">
        <thead>
          <tr>
            <th>Utilisateur</th>
            <th>Roles</th>
            <th>Etat</th>
            <th>Connexion</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in displayedUsers" :key="user.id">
            <td>
              <strong>{{ user.displayName }}</strong>
              <span>{{ user.email }}</span>
              <span>username: {{ user.username }}</span>
              <span v-if="user.keycloakUuid" class="mono">{{ user.keycloakUuid }}</span>
            </td>
            <td>
              <div class="role-stack">
                <StatusBadge
                  v-for="role in user.roles"
                  :key="role"
                  :label="role"
                  :tone="statusTone(role)"
                  compact
                />
              </div>
            </td>
            <td>
              <StatusBadge :label="user.isActive ? 'active' : 'inactive'" :tone="user.isActive ? 'active' : 'waiting'" compact />
            </td>
            <td>
              <p class="mono">{{ user.lastLoginLabel }}</p>
              <p class="helper-text">{{ user.authSource }}</p>
            </td>
            <td>
              <div class="actions-stack">
                <form
                  v-if="canManageIdentity"
                  class="inline-form"
                  @submit.prevent="handleProfileSave(user)"
                >
                  <label class="field">
                    <span>Email</span>
                    <input
                      :value="getDraft(user.id).email"
                      type="email"
                      required
                      @input="setDraftValue(user.id, 'email', ($event.target as HTMLInputElement).value)"
                    />
                  </label>

                  <div class="field-row">
                    <label class="field">
                      <span>Prenom</span>
                      <input
                        :value="getDraft(user.id).firstName"
                        @input="setDraftValue(user.id, 'firstName', ($event.target as HTMLInputElement).value)"
                      />
                    </label>
                    <label class="field">
                      <span>Nom</span>
                      <input
                        :value="getDraft(user.id).lastName"
                        @input="setDraftValue(user.id, 'lastName', ($event.target as HTMLInputElement).value)"
                      />
                    </label>
                  </div>

                  <button class="button-secondary" type="submit" :disabled="isBusy(`profile:${user.id}`)">
                    {{ isBusy(`profile:${user.id}`) ? "Mise a jour..." : "Mettre a jour le profil" }}
                  </button>
                </form>

                <form
                  v-if="canAssignRoles"
                  class="inline-form"
                  @submit.prevent="handleRolesSave(user)"
                >
                  <label class="field">
                    <span>Roles</span>
                    <RoleDropdownField
                      :model-value="getDraft(user.id).roleNames"
                      :options="displayedRoleCatalog"
                      @update:model-value="setDraftRoles(user.id, $event)"
                    />
                  </label>

                  <button class="button-secondary" type="submit" :disabled="isBusy(`roles:${user.id}`)">
                    {{ isBusy(`roles:${user.id}`) ? "Application..." : "Appliquer les roles" }}
                  </button>
                </form>

                <button
                  v-if="canToggleUsers"
                  class="button-secondary"
                  type="button"
                  :disabled="isBusy(`status:${user.id}`)"
                  @click="handleStatusToggle(user)"
                >
                  {{ isBusy(`status:${user.id}`) ? "Mise a jour..." : user.isActive ? "Desactiver" : "Reactiver" }}
                </button>

                <button
                  v-if="canDeleteUsers && user.id !== session.user?.id"
                  class="button-danger"
                  type="button"
                  :disabled="isBusy(`delete:${user.id}`)"
                  @click="handleDelete(user)"
                >
                  {{ isBusy(`delete:${user.id}`) ? "Suppression..." : "Supprimer l'utilisateur" }}
                </button>

                <p v-else-if="canDeleteUsers && user.id === session.user?.id" class="helper-text">
                  Suppression du compte courant bloquee pour eviter un lock-out admin.
                </p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>

<style scoped>
.uppercase {
  margin-bottom: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.76rem;
}

.current-admin {
  text-align: right;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.3rem;
}

.admin-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr);
  gap: 1.25rem;
}

.note-shell,
.table-shell,
.notice-shell {
  overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(12, 14, 16, 0.96), rgba(8, 9, 10, 0.94));
}

.note-shell {
  padding: 1.5rem 1.7rem;
}

.notice-shell {
  padding: 1rem 1.2rem;
}

.notice-ok {
  border-color: rgba(132, 212, 79, 0.28);
  color: var(--green);
  background: rgba(66, 111, 21, 0.18);
}

.notice-warning {
  border-color: rgba(212, 166, 62, 0.28);
  color: var(--gold);
  background: rgba(95, 74, 20, 0.22);
}

.notice-error {
  border-color: rgba(255, 154, 139, 0.28);
  color: var(--red-soft);
  background: rgba(123, 38, 33, 0.22);
}

.card-heading,
.table-header,
.action-row,
.identity-stack,
.catalog-list,
.actions-stack,
.inline-form,
.invite-form {
  display: grid;
  gap: 0.9rem;
}

.card-heading,
.table-header {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.table-header {
  padding: 1.35rem 1.4rem 0;
}

.note-shell h2,
.table-header h2 {
  font-size: 1.5rem;
}

.identity-name {
  font-size: 1.1rem;
  font-weight: 600;
}

.helper-text {
  color: var(--muted);
  line-height: 1.55;
}

.catalog-item {
  padding: 1rem 1.05rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
}

.catalog-title {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
}

.catalog-description {
  margin-top: 0.7rem;
  color: var(--text);
}

.invite-copy {
  margin-top: 0.8rem;
  margin-bottom: 1rem;
}

.field {
  display: grid;
  gap: 0.45rem;
}

.field span {
  color: var(--muted);
  font-size: 0.92rem;
}

.field-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}

.field input,
.field select {
  width: 100%;
  min-height: 2.9rem;
  padding: 0.75rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}

.field select[multiple] {
  min-height: 8.5rem;
  padding-block: 0.5rem;
}

.field input:disabled,
.field select:disabled {
  opacity: 0.55;
}

.button-primary,
.button-secondary,
.button-danger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.85rem;
  padding: 0.75rem 1rem;
  border-radius: 999px;
  font-weight: 600;
  transition:
    transform 150ms ease,
    border-color 150ms ease,
    background 150ms ease;
}

.button-primary {
  border: 1px solid rgba(122, 168, 255, 0.32);
  background: rgba(82, 117, 176, 0.2);
  color: var(--text);
}

.button-secondary {
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
}

.button-danger {
  border: 1px solid rgba(255, 154, 139, 0.28);
  background: rgba(123, 38, 33, 0.2);
  color: var(--red-soft);
}

.button-primary:hover,
.button-secondary:hover,
.button-danger:hover {
  transform: translateY(-1px);
}

.button-primary:disabled,
.button-secondary:disabled,
.button-danger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

.user-table thead th {
  padding: 1rem 1.25rem;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
}

.user-table tbody td {
  padding: 1.15rem 1.25rem;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

.user-table tbody tr:last-child td {
  border-bottom: none;
}

.user-table tbody td:first-child strong {
  display: block;
  font-size: 1.05rem;
}

.user-table tbody td:first-child span {
  display: block;
  margin-top: 0.25rem;
  color: var(--muted);
}

.role-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

@media (max-width: 1320px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .field-row {
    grid-template-columns: 1fr;
  }

  .table-shell {
    overflow-x: auto;
  }

  .user-table {
    min-width: 1100px;
  }
}

@media (max-width: 720px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .card-heading,
  .table-header,
  .page-heading {
    grid-template-columns: 1fr;
  }

  .current-admin {
    text-align: left;
  }
}
</style>
