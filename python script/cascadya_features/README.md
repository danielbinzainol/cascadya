# Cascadya Features

Mini webapp interne pour challenger rapidement une spec de feature avant implementation.

Le repo livre trois briques:

- une mini app Flask
- une interface HTML/CSS/JS pour coller une spec et obtenir une note sur 5
- un outillage Ansible pour la poser derriere Traefik, limitee au reseau WireGuard

## Fonctionnement

La note repose sur une grille heuristique simple, sans appel a un LLM:

- contexte / probleme
- utilisateurs et impact
- perimetre et non-objectifs
- criteres d'acceptation
- risques, dependances et exploitation

L'application expose aussi `/keys.js`.
Par defaut, ce fichier est servi depuis une requete SQL configurable afin de coller a la demande "aller chercher `keys.js` dans la database".
Comme le schema exact n'etait pas present localement, la requete par defaut est volontairement generique et doit etre ajustee si besoin.

## Arborescence

- `app.py`: lance le serveur
- `cascadya_features/`: logique Python
- `web/`: frontend statique
- `tests/`: tests unitaires de la logique de scoring
- `ansible/`: deploiement sur VM existante

## Lancement local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Puis ouvrir:

```text
http://127.0.0.1:8766
```

## Variables utiles

- `APP_HOST`: bind du serveur Python
- `APP_PORT`: port du serveur Python
- `FEATURES_KEYS_DATABASE_URL`: DSN PostgreSQL pour charger `keys.js`
- `FEATURES_KEYS_SQL`: requete SQL retournant le contenu de `keys.js` dans la premiere colonne
- `FEATURES_KEYS_FILE_PATH`: fallback fichier si la DB n'est pas configuree
- `*_API_KEY`: toute variable finissant par `_API_KEY` peut vivre dans `.env`; l'app ne remonte jamais les valeurs, seulement les noms/configurations presentes

## API

- `GET /api/healthz`
- `GET /api/status`
- `POST /api/evaluate`
- `GET /keys.js`

`/api/status` remonte aussi le nombre et les noms des variables `*_API_KEY` configurees, sans exposer leurs contenus.

Exemple:

```json
{
  "spec": "Objectif: ...\nUtilisateurs: ...\nCritere d'acceptation: ..."
}
```

## Deploiement

Le dossier [ansible/README.md](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/cascadya_features/ansible/README.md) prepare:

- un service `systemd` qui tourne en local sur `127.0.0.1`
- une route Traefik `https://features.cascadya.internal`
- un filtrage `ipAllowList` cote Traefik pour restreindre l'acces a WireGuard
- un enregistrement `dnsmasq` sur la VM WireGuard

## Mise a jour rapide depuis Windows

Si tu veux mettre a jour l'app sans repasser par WSL/Ansible, tu peux lancer les scripts PowerShell du repo depuis un terminal ouvert a la racine du projet:

```powershell
cd "C:\Users\Daniel BIN ZAINOL\Desktop\GIT - Daniel\python script\cascadya_features"
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-live.ps1
```

Pour pousser uniquement le frontend statique:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-live.ps1 -FrontendOnly
```

Pour verifier rapidement le service et l'URL live:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-live.ps1
```

Ou, si tu preferes eviter totalement `ExecutionPolicy`, tu peux lancer les wrappers Windows:

```powershell
.\scripts\deploy-live.cmd
.\scripts\deploy-live.cmd -FrontendOnly
.\scripts\check-live.cmd
```

## Ou lancer quoi

- Depuis ton PC Windows, a la racine du repo: `.\scripts\deploy-live.ps1`
- Depuis la VM Control Panel: verifications `systemd`, `curl http://127.0.0.1:8766/...`
- Depuis un poste connecte au VPN WireGuard: test final sur `https://features.cascadya.internal`
