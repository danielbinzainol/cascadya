# Ansible - Etat fige de la page d'authentification

Ce dossier contient un playbook Ansible qui reproduit l'etat fonctionnel actuel du prototype d'authentification :

- `FastAPI` sur `control-panel-DEV1-S`
- `Traefik` en Docker sur la meme VM
- `PostgreSQL` metier pour le RBAC
- route retour vers le reseau `WireGuard`
- `dnsmasq` sur `wireguard-DEV1-S`
- resolution interne de `control-panel.cascadya.internal`
- resolution interne de `wazuh.cascadya.internal`

## Ce que le playbook couvre

- configuration de `dnsmasq` sur la gateway WireGuard
- configuration TLS interne du dashboard Wazuh
- activation de `ip_forward`
- ancrage des regles de forwarding WireGuard -> reseau prive
- configuration de l'environnement applicatif FastAPI
- deploiement de `Traefik` via Docker Compose
- deploiement de `postgres-fastapi` via Docker Compose
- generation d'un certificat autosigne local pour `Traefik`
- service `systemd` `control-panel-auth`
- service `systemd` de route retour vers `10.8.0.0/24`
- installation des dependances Python du lot 1
- migration Alembic
- seed RBAC
- verifications `healthz` et `healthz/db`

## Prerequis

- le code du repo est deja present sur la VM control panel dans `/opt/control-panel/control_plane`
- le virtualenv de l'application existe ou peut etre cree dans `/opt/control-panel/control_plane/.venv`
- Docker et le plugin `docker compose` sont deja installes sur `control-panel-DEV1-S`
- WireGuard est deja installe et `wg0` existe deja sur `wireguard-DEV1-S`
- les Security Groups Scaleway sont deja geres a part

## Collections Ansible

Depuis la machine de controle :

```bash
ansible-galaxy collection install -r auth_prototype/ansible/requirements.yml
```

## Preparation

1. Copier `inventory/hosts.example.yml` vers ton propre inventaire.
2. Copier `inventory/group_vars/all.example.yml` vers `inventory/group_vars/all.yml`.
3. Remplir les secrets et variables adaptees a ton environnement.
4. Synchroniser `auth_prototype` avec `rsync --delete` avant le playbook pour supprimer aussi les fichiers retires localement.

## Synchronisation du code

Le playbook ne pousse pas le code applicatif. Pour eviter les fichiers orphelins laisses par `scp`, utilise :

```bash
./auth_prototype/ansible/sync-auth-prototype.sh ubuntu@51.15.115.203
```

Ce script :

- synchronise `auth_prototype/` vers `/opt/control-panel/control_plane/auth_prototype` ;
- supprime du cote VM les fichiers source retires localement ;
- nettoie les `__pycache__` et les fichiers `*.pyc`.

## Execution

Depuis la racine du repo :

```bash
./auth_prototype/ansible/sync-auth-prototype.sh ubuntu@51.15.115.203
./auth_prototype/ansible/run-playbook.sh auth_prototype/ansible/inventory/hosts.yml
```

## Tags utiles

Tu peux aussi executer une partie du playbook :

```bash
./auth_prototype/ansible/run-playbook.sh auth_prototype/ansible/inventory/hosts.yml --tags wireguard
./auth_prototype/ansible/run-playbook.sh auth_prototype/ansible/inventory/hosts.yml --tags wazuh
./auth_prototype/ansible/run-playbook.sh auth_prototype/ansible/inventory/hosts.yml --tags control_panel
```

## Note WSL / disque Windows

Si tu executes Ansible depuis un chemin WSL mappe sur Windows, Ansible peut ignorer `ansible.cfg` a cause du `world writable directory`.
Le script `run-playbook.sh` contourne ce point en injectant explicitement `ANSIBLE_ROLES_PATH`.

## Resultat attendu

- `https://control-panel.cascadya.internal/auth/login` repond via `WireGuard`
- `https://wazuh.cascadya.internal` repond via `WireGuard`
- `FastAPI` tourne sur `127.0.0.1:8000`
- `Traefik` termine TLS sur `:443`
- `postgres-fastapi` expose `127.0.0.1:5433`
- `GET /healthz` et `GET /healthz/db` repondent
- le catalogue RBAC est seed en base
