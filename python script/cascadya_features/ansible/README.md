# Deploiement Ansible

Ce dossier prepare un deploiement simple de `cascadya_features` sur une VM deja existante.

Le setup vise le cas de figure decrit:

- app Flask locale servie par Waitress
- exposition via un reverse proxy deja present
- acces reserve au reseau WireGuard
- `keys.js` servi par l'application depuis une requete DB configurable

## Hypothese retenue

Le role cible par defaut la VM `control-panel-DEV1-S`, parce qu'elle dispose deja d'un Traefik interne et d'une resolution `.cascadya.internal` dans le workspace local.

Si vous choisissez une autre VM:

- adaptez `inventory/hosts.yml`
- adaptez `group_vars/all.yml`
- pointez `features_traefik_root` vers le Traefik existant sur cette VM

## Fichiers principaux

- `site.yml`: orchestration globale
- `inventory/hosts.example.yml`: inventaire exemple
- `group_vars/all.example.yml`: variables a personnaliser
- `sync-cascadya-features.sh`: rsync du repo sur la VM cible
- `run-playbook.sh`: wrapper d'execution

## Etapes

1. Copier `inventory/hosts.example.yml` vers `inventory/hosts.yml`.
2. Copier `group_vars/all.example.yml` vers `group_vars/all.yml`.
3. Adapter le hostname interne, la VM cible et la requete SQL pour `keys.js`.
4. Ajouter si besoin les cles d'API dans `features_extra_env`.
5. Synchroniser le repo sur la VM:

```bash
./ansible/sync-cascadya-features.sh ubuntu@51.15.115.203
```

6. Appliquer le playbook:

```bash
./ansible/run-playbook.sh ansible/inventory/hosts.yml
```

## Resultat attendu

- le service Python repond localement sur `127.0.0.1:8766`
- Traefik route `https://features.cascadya.internal`
- l'acces externe est borne par `traefik_allowed_cidrs`
- la gateway WireGuard resout `features.cascadya.internal`

## Point d'attention

Le schema DB reel de `keys.js` n'etait pas present dans le repo local.
La variable `features_keys_sql` doit donc etre validee contre la vraie base avant mise en prod.
