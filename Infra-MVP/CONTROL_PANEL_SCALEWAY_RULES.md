# Doc - Regles Scaleway a figer pour le Control Panel via Traefik + WireGuard

Version: 1.0
Date: 2026-03-26
Statut: cible reseau immediate
Auteur: Codex

## 1. Objet

Ce document decrit uniquement les regles reseau a appliquer cote Scaleway pour figer le setup actuel du Control Panel.

Le but est simple :

- exposer l'interface web uniquement via `Traefik` sur `443`
- restreindre l'acces aux clients `WireGuard`
- conserver un acces d'administration de secours
- interdire le contournement direct de `FastAPI` sur le port `8000`

## 2. Contexte technique retenu

Etat cible retenu :

- VM : `control-panel-DEV1-S`
- IP publique : `51.15.115.203`
- reverse proxy : `Traefik` en Docker sur la meme VM
- backend applicatif : `FastAPI` via `systemd`
- bind applicatif : `127.0.0.1:8000`
- nommage interne : `control-panel.cascadya.internal`
- acces web autorise uniquement depuis :
  - `10.8.0.0/24` (VPN WireGuard)
  - `195.68.106.70/32` (IP d'administration)

## 3. Principe de securite

Le port web expose publiquement par la VM ne doit plus etre `8000`.

Le seul point d'entree HTTP(S) doit etre :

- `TCP 443` -> `Traefik`

Le backend FastAPI continue d'exister sur `127.0.0.1:8000`, mais il ne doit jamais etre joignable directement depuis Internet.

## 4. Regles a appliquer dans le Security Group Scaleway

## 4.1 Regles inbound a conserver / creer

Autoriser `TCP 22` depuis :

- `10.8.0.0/24`
- `195.68.106.70/32`

Autoriser `TCP 443` depuis :

- `10.8.0.0/24`
- `195.68.106.70/32`

Optionnel selon vos usages :

- `ICMP` depuis `10.8.0.0/24` et `195.68.106.70/32` si vous voulez garder le ping pour debug

## 4.2 Regles inbound a supprimer / ne pas creer

Ne pas exposer `TCP 8000`.

Donc :

- supprimer toute regle `TCP 8000` existante
- ne laisser aucune ouverture de `8000` vers `0.0.0.0/0`
- ne laisser aucune ouverture de `8000` vers `10.8.0.0/24`
- ne laisser aucune ouverture de `8000` vers `195.68.106.70/32`

Raison :

- `8000` est reserve au trafic local entre `Traefik` et `FastAPI`
- avec le bind actuel sur `127.0.0.1`, ouvrir `8000` ne sert plus a l'exploitation normale

Ne pas ouvrir `TCP 80` pour ce setup.

Raison :

- vous utilisez un nommage interne et un certificat interne / auto-signe
- vous ne faites pas de challenge ACME public sur cette VM

## 4.3 Politique inbound par defaut

La politique inbound doit etre :

- `drop`

Puis seules les regles explicites ci-dessus doivent permettre le trafic entrant.

## 4.4 Politique outbound

Recommendation :

- conserver une politique outbound permissive / par defaut

Raison :

- la VM doit pouvoir sortir pour les mises a jour systeme
- Docker doit pouvoir telecharger les images
- l'application peut avoir besoin d'acces sortants ulterieurs

Si votre security group est `stateful`, le trafic de retour sera automatiquement autorise.

## 5. Regles cibles finales

En pratique, la cible minimale a atteindre est :

- `22/tcp` ouvert a `10.8.0.0/24`
- `22/tcp` ouvert a `195.68.106.70/32`
- `443/tcp` ouvert a `10.8.0.0/24`
- `443/tcp` ouvert a `195.68.106.70/32`
- `8000/tcp` ferme
- `80/tcp` ferme
- politique inbound par defaut = `drop`

## 6. Ce qu'il faut modifier dans Terraform

Dans votre Terraform actuel, il faut traduire ce document en trois types de changements :

### 6.1 Security group du control panel

Le security group dedie au Control Panel doit :

- rester attache uniquement a la VM `control-panel-DEV1-S`
- avoir une politique inbound restrictive
- contenir des regles explicites pour `22` et `443`
- ne contenir aucune regle pour `8000`
- ne contenir aucune regle pour `80`

### 6.2 Variables / locals reseau

Il est recommande de centraliser les CIDR autorises dans Terraform :

- `10.8.0.0/24`
- `195.68.106.70/32`

Par exemple via :

- un `local.allowed_control_panel_cidrs`
- ou des variables dediees `wireguard_cidr` et `admin_cidrs`

### 6.3 Nettoyage de l'ancien setup

Si l'ancien test HTTP direct existe encore dans Terraform, il faut retirer :

- la regle `TCP 8000`
- toute mention d'un acces direct au prototype Auth sur IP brute

## 7. Point important sur Scaleway

Les security groups Scaleway filtrent le trafic public de l'instance.

Cela veut dire :

- le control panel sera bien protege sur son interface publique
- mais le filtrage du trafic sur un eventuel `Private Network` ne repose pas sur ce security group

Si vous avez plus tard besoin de filtrer aussi le trafic prive intra-VPC, il faudra le faire au niveau de la VM elle-meme avec un firewall local (`ufw`, `iptables`, `nftables`) ou une autre brique reseau.

## 8. Tests d'acceptation apres `terraform apply`

Une fois les regles appliquees, les verifications attendues sont :

### 8.1 Depuis un poste autorise

Depuis :

- un client WireGuard `10.8.0.x`
- ou le poste admin `195.68.106.70`

Les tests suivants doivent reussir :

- acces a `https://control-panel.cascadya.internal/auth/login`
- affichage de la page de login
- login avec `operator / operator123!`

### 8.2 Depuis un poste non autorise

Depuis une IP non incluse dans les CIDR autorises :

- l'acces a `443` doit etre refuse ou timeout

### 8.3 Verification du backend direct

Depuis l'exterieur :

- `http://51.15.115.203:8000` doit echouer

Depuis la VM elle-meme :

- `curl http://127.0.0.1:8000/healthz` doit continuer a renvoyer `{"status":"ok"}`

## 9. Decision operationnelle

Le setup reseau a figer dans Terraform est donc :

- `Traefik` expose en `443`
- acces restreint a `WireGuard + IP admin`
- `FastAPI` non expose publiquement
- aucune ouverture de `80`
- aucune ouverture de `8000`

## 10. Checklist Terraform

- supprimer la regle ingress `8000/tcp` existante
- ajouter ou conserver `22/tcp` pour `10.8.0.0/24`
- ajouter ou conserver `22/tcp` pour `195.68.106.70/32`
- ajouter `443/tcp` pour `10.8.0.0/24`
- ajouter `443/tcp` pour `195.68.106.70/32`
- verifier que la politique inbound par defaut est `drop`
- reappliquer le security group sur `control-panel-DEV1-S`

## 11. Sources

- Scaleway - Security groups filter public traffic only: https://www.scaleway.com/en/docs/instances/how-to/use-security-groups/
- Scaleway - Security groups concepts: https://www.scaleway.com/en/docs/instances/concepts
- Traefik `ipAllowList`: https://doc.traefik.io/traefik/v3.3/middlewares/http/ipallowlist/
- FastAPI behind a proxy: https://fastapi.tiangolo.com/advanced/behind-a-proxy/
- Uvicorn proxy and forwarded headers: https://www.uvicorn.org/settings/
