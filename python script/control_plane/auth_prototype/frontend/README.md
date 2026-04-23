# Frontend Vue du control panel

Ce dossier contient le premier socle `Vue 3 + Vite + TypeScript` du control panel.

## Ce qui est deja pose

- shell applicatif avec navigation;
- mode de demonstration RBAC par roles;
- dashboard global;
- detail d'un site;
- page provisioning;
- page test E2E;
- zone admin branchee au backend IAM;
- donnees de demonstration coherentes avec les maquettes et le lot IAM.

## Routage frontend

- `/ui/app`
- `/ui/sites/:siteId`
- `/ui/sites/:siteId/provisioning`
- `/ui/sites/:siteId/e2e`
- `/ui/admin`

## Stack

- `Vue 3`
- `TypeScript`
- `Vite`
- `Vue Router`
- `Pinia`
- `@tanstack/vue-query`
- `zod`

## Demarrage local

Prerequis :

- `Node.js 20+`
- `npm`

Commandes :

```bash
cd auth_prototype/frontend
npm install
npm run dev
```

Ouvrir ensuite :

```text
http://127.0.0.1:5173/ui/app
```

## Note sur l'etat actuel

Le frontend supporte maintenant :

- la session backend via `FastAPI` + Keycloak ;
- un mode `mock` pour le developpement local ;
- le service du build sous `/ui`.

Le prochain chantier sera :

1. brancher les vrais endpoints `sites`, `inventory`, `jobs` ;
2. remplacer progressivement les donnees mock restantes ;
3. integrer le build frontend au playbook de deploiement.
