<script setup lang="ts">
import { computed } from "vue";
import { RouterView } from "vue-router";

import { useSessionStore } from "@/stores/session";

const session = useSessionStore();

const isBooting = computed(() => !session.ready && !session.redirectingToLogin && !session.authError);
</script>

<template>
  <section v-if="isBooting" class="boot-shell">
    <div class="boot-card">
      <p class="boot-eyebrow">Session bootstrap</p>
      <h1>Connexion au control plane...</h1>
      <p class="boot-body">
        Verification de la session FastAPI / Keycloak et chargement du profil RBAC.
      </p>
    </div>
  </section>

  <section v-else-if="session.redirectingToLogin" class="boot-shell">
    <div class="boot-card">
      <p class="boot-eyebrow">Authentication required</p>
      <h1>Redirection vers la page de login</h1>
      <p class="boot-body">
        La session frontend n'est pas encore ouverte. Tu vas etre renvoye vers
        <code>/auth/login</code>.
      </p>
    </div>
  </section>

  <section v-else-if="session.authError" class="boot-shell">
    <div class="boot-card boot-card-error">
      <p class="boot-eyebrow">Session error</p>
      <h1>Impossible d'initialiser la session frontend</h1>
      <p class="boot-body">{{ session.authError }}</p>
      <div class="boot-actions">
        <a class="boot-button" href="/auth/login?next=/ui/app">Relancer la connexion</a>
      </div>
    </div>
  </section>

  <RouterView v-else />
</template>

<style scoped>
.boot-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem;
}

.boot-card {
  width: min(100%, 38rem);
  padding: 2rem 2.1rem;
  border-radius: 1.75rem;
  border: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(17, 21, 27, 0.96), rgba(12, 15, 19, 0.94)),
    radial-gradient(circle at top right, rgba(122, 168, 255, 0.14), transparent 44%);
  box-shadow: var(--shadow-panel);
}

.boot-card-error {
  background:
    linear-gradient(180deg, rgba(24, 18, 17, 0.96), rgba(16, 12, 11, 0.94)),
    radial-gradient(circle at top right, rgba(255, 154, 139, 0.16), transparent 44%);
}

.boot-eyebrow {
  margin: 0 0 0.8rem;
  color: var(--muted-2);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.76rem;
}

.boot-card h1 {
  margin: 0;
  font-size: clamp(2rem, 1.5vw + 1.4rem, 3rem);
}

.boot-body {
  margin: 1rem 0 0;
  color: var(--muted);
  line-height: 1.7;
}

.boot-actions {
  margin-top: 1.4rem;
}

.boot-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  padding: 0.8rem 1.15rem;
  border-radius: 999px;
  border: 1px solid rgba(122, 168, 255, 0.32);
  color: var(--text);
  text-decoration: none;
  background: rgba(82, 117, 176, 0.2);
}
</style>
