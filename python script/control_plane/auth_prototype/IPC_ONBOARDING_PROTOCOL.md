# IPC Onboarding Protocol

Ce protocole fixe une convention unique pour le control panel et les playbooks Ansible de `cascadya-edge-os-images`.

## Objectif

Chaque IPC doit avoir :

- un identifiant site stable
- un nom lisible metier
- un hostname OS stable
- un `inventory_hostname` unique pour Ansible et les certificats
- des variables edge-agent coherentes d'un site a l'autre

## Regles de nommage

### `code site`

Utilisation :

- identifiant court, stable, visible partout
- cle de rattachement d'un IPC a un site

Convention :

- format recommande : `SITE-44`
- uniquement majuscules, chiffres et `-`
- ne pas reutiliser un code deja attribue
- ne pas renommer un code site sans migration globale

Exemples :

- `SITE-44`
- `SITE-105`
- `SITE-LAB`

### `nom site`

Utilisation :

- libelle metier et UI
- peut rester plus humain que le code

Convention :

- nom lisible par les equipes terrain et exploitation
- garder la meme graphie partout

Exemples :

- `Ouest Consigne`
- `Lab Integration`
- `Bordeaux Nord`

### `hostname`

Utilisation :

- hostname Linux de l'IPC
- visible en SSH et dans les logs systeme

Convention :

- minuscules uniquement
- chiffres et `-` seulement
- format recommande : `ipc-site44-01`
- suffixe final pour distinguer plusieurs IPC sur un meme site

Exemples :

- `ipc-site44-01`
- `ipc-site44-02`
- `ipc-lab-01`

### `inventory_hostname`

Utilisation :

- identifiant Ansible
- nom des artefacts de certificats par device
- identifiant de reference dans les inventories generes

Convention :

- doit etre unique globalement
- garder un prefixe `cascadya-`
- format recommande : `cascadya-ipc-site44-01`

Exemples :

- `cascadya-ipc-site44-01`
- `cascadya-ipc-site44-02`
- `cascadya-ipc-lab-01`

## Regles de configuration reseau

### `management_ip`

- IP de management reachable depuis le control panel
- exemple : `192.168.10.109`

### `teltonika_router_ip`

- gateway management locale du site
- exemple : `192.168.10.1`

### `edge_agent_modbus_host`

- IP du simulateur Modbus ou de l'equipement terrain vu depuis l'IPC
- valeur courante recommandee dans les playbooks : `192.168.50.2`
- si le site utilise un autre endpoint, mettre l'IP reellement joignable depuis l'IPC

### `edge_agent_nats_url`

- URL du broker NATS central utilisee par l'edge-agent
- valeur par defaut actuellement alignee avec `cascadya-edge-os-images` :

```text
tls://10.30.0.1:4222
```

Regle :

- utiliser la meme URL pour tous les IPC d'un meme environnement
- ne pas mettre une URL fictive ou temporaire en production
- ne changer cette valeur que si le broker central change ou si un DNS stable le remplace

Si un DNS NATS officiel est mis en place plus tard, la nouvelle forme cible sera par exemple :

```text
tls://nats.cascadya.internal:4222
```

## Procedure recommande

1. Scanner l'IPC via son IP de management.
2. Verifier la MAC, les interfaces et la reachability SSH.
3. Choisir ou creer le site avec un `code site` stable.
4. Fixer `hostname` selon `ipc-<site>-<index>`.
5. Fixer `inventory_hostname` selon `cascadya-ipc-<site>-<index>`.
6. Verifier `edge_agent_modbus_host` selon le device terrain reel.
7. Verifier `edge_agent_nats_url` selon l'environnement central.
8. Enregistrer l'IPC puis preparer le job Ansible.

## Exemple complet

- `code site` : `SITE-44`
- `nom site` : `Ouest Consigne`
- `hostname` : `ipc-site44-01`
- `inventory_hostname` : `cascadya-ipc-site44-01`
- `management_ip` : `192.168.10.109`
- `teltonika_router_ip` : `192.168.10.1`
- `edge_agent_modbus_host` : `192.168.50.2`
- `edge_agent_nats_url` : `tls://10.30.0.1:4222`
