# PRD ajuste - Migration de Keycloak vers la VM Vault pour une identite partagee

Date de reference des constats terrain : 2026-04-16

## 1. Objet

Ce document ajuste le PRD initial a la realite observee sur `vault-DEV1-S`.

Il conserve l'objectif fonctionnel :

- heberger `Keycloak` sur la VM Vault ;
- garder `auth.cascadya.internal` comme hostname de l'IdP ;
- partager l'authentification entre `control-panel-web`, `cascadya-features-web`, `grafana-monitoring` et `cascadya-portal-web` ;
- conserver le RBAC metier du Control Panel dans `postgres-fastapi`.

Il modifie en revanche plusieurs hypotheses d'implementation, car la VM Vault n'est pas vide et expose deja des services en production.

## 2. Resume executif ajuste

La realite observee sur `vault-DEV1-S` au 2026-04-16 est la suivante :

- `Vault` tourne deja en natif via `systemd` sur `0.0.0.0:8200` et `*:8201` ;
- `nginx` tourne deja en natif sur `0.0.0.0:80` et `0.0.0.0:443` ;
- le vhost actuellement configure sur `nginx` est `secrets.cascadya.com` et reverse-proxy vers `http://127.0.0.1:8200` ;
- le certificat expose par ce vhost est un certificat `Let's Encrypt` pour `secrets.cascadya.com` ;
- `Docker` heberge maintenant :
  - `postgres-keycloak`
  - `keycloak`
  - `cadvisor` ;
- la VM Vault a bien l'IP privee `10.42.2.4` sur `ens5` ;
- la reachability privee vers `10.42.1.2:443` et `10.42.1.4:3000` est deja fonctionnelle ;
- `nginx` publie maintenant un vhost `auth.cascadya.internal` vers `Keycloak` ;
- `https://auth.cascadya.internal/realms/cascadya-corp/.well-known/openid-configuration`
  repond `200` depuis le poste admin ;
- `auth.cascadya.internal` et `control-panel.cascadya.internal` ne sont pas resolus localement sur la VM Vault ;
- le resolver local de Vault reste oriente vers des DNS publics (`1.1.1.1`, `8.8.8.8`), pas vers un DNS interne SI.

Conclusion immediate :

- l'option `Traefik dedie sur la VM Vault` n'est pas retenue ;
- la migration reelle s'appuie bien sur le `nginx` existant sur Vault ;
- le nouveau role Ansible Vault doit rester additif et ne doit pas casser le couple existant `nginx + Vault`.

## 2.1 Statut terrain confirme apres migration

Etat confirme apres la migration reussie de `Keycloak` vers `vault-DEV1-S` :

- la migration `Keycloak` est consideree comme reussie ;
- les endpoints historiques d'authentification ont ete maintenus ;
- le Control Panel continue de joindre l'IdP migre ;
- `auth.cascadya.internal` sert bien la discovery OIDC depuis Vault ;
- `portal.cascadya.internal` est a nouveau publie et repond `303 /auth/login?next=%2F` ;
- la regression fonctionnelle observee apres migration ne venait pas du runtime
  `Keycloak` lui-meme, mais du drift d'infrastructure autour de lui.

Constat complementaire etabli le 2026-04-16 :

- le DNS interne `dnsmasq` sert maintenant :
  - `auth.cascadya.internal -> 10.42.2.4`
  - `portal.cascadya.internal -> 10.42.1.2`
- `features.cascadya.internal` reste publie sur `10.42.1.2` ;
- `control-panel.cascadya.internal` reste publie sur `10.42.1.2` ;
- `wazuh.cascadya.internal` reste publie sur `10.42.1.7`.

Etat fonctionnel vu depuis le poste admin apres corrections reseau et DNS :

- `control-panel.cascadya.internal` repond a nouveau ;
- `features.cascadya.internal` repond ;
- `wazuh.cascadya.internal` repond a nouveau avec le `302` attendu ;
- `portal.cascadya.internal` repond a nouveau avec le `303` attendu vers le login ;
- `auth.cascadya.internal` repond a nouveau avec la discovery OIDC complete.

Drift residuel encore present au 2026-04-16 :

- la base `Keycloak` migree sur Vault contient bien :
  - `control-panel-web`
  - `cascadya-features-web`
  - `grafana-monitoring`
- mais ne contient pas encore `cascadya-portal-web` ;
- resultat : le portail atteint bien le bon `Keycloak`, mais affiche encore
  `Client not found` lors du flux OIDC ;
- la route Traefik legacy `auth.cascadya.internal` existe encore sur
  `control-panel-DEV1-S` et doit etre retiree pour eliminer le drift.

Diagnostic terrain etabli le 2026-04-15 :

- `https://10.42.1.7/` repond bien depuis `control-panel-DEV1-S` et renvoie le `302` attendu du dashboard Wazuh ;
- `10.42.1.7:443` est reachable depuis `control-panel-DEV1-S` ;
- `dnsmasq` sur `wireguard-DEV1-S` sert toujours correctement :
  - `wazuh.cascadya.internal -> 10.42.1.7`
- mais le resolver systeme de `control-panel-DEV1-S` renvoie `NXDOMAIN` pour `wazuh.cascadya.internal`.

Conclusion :

- l'indisponibilite de `https://wazuh.cascadya.internal/` n'est pas due au service Wazuh lui-meme ;
- le bouton Wazuh du Control Panel n'est pas la cause ;
- la cause immediate est une regression de resolution DNS sur `control-panel-DEV1-S`, qui n'interroge plus le DNS WireGuard `10.8.0.1` pour les hostnames `.cascadya.internal`.

Constat complete apres correction DNS sur `control-panel-DEV1-S` :

- la resolution locale de `wazuh.cascadya.internal` sur `control-panel-DEV1-S` a ete retablie ;
- `curl -k -I https://wazuh.cascadya.internal/` repond a nouveau depuis `control-panel-DEV1-S` ;
- mais le poste admin WireGuard ne pouvait toujours plus joindre :
  - `control-panel.cascadya.internal`
  - `wazuh.cascadya.internal`
  - plus largement les cibles privees `10.42.1.x`.

Diagnostic reseau finalement confirme :

- le DNS du poste admin reste bon et resolvait correctement :
  - `control-panel.cascadya.internal -> 10.42.1.2`
  - `wazuh.cascadya.internal -> 10.42.1.7`
- la gateway `wireguard-DEV1-S` joignait bien `10.42.1.2` et `10.42.1.7` ;
- les services applicatifs n'etaient donc pas tombes ;
- la chaine `WIREGUARD-FORWARD` autorisait deja bien le transit `wg0 -> ens5` ;
- mais la chaine `WIREGUARD-POSTROUTING` ne faisait le `MASQUERADE` que vers `ens2` ;
- il manquait une translation source pour le trafic `10.8.0.0/16 -> 10.42.0.0/16` en sortie `ens5`.

Preuve complementaire :

- sur `control-panel-DEV1-S`, `ip route get 10.8.0.2` partait vers la gateway publique `62.210.0.1` et non vers `10.42.1.5` ;
- les VMs du LAN `10.42.1.x` n'avaient donc pas de route retour vers le reseau clients WireGuard `10.8.0.0/16`.

Conclusion finale du probleme de reachability :

- il y a eu deux regressions distinctes a traiter :
  - une regression de resolution DNS interne sur `control-panel-DEV1-S` ;
  - une absence de NAT retour `wg0 -> ens5` sur `wireguard-DEV1-S` pour les clients admin WireGuard.
- la migration `Keycloak` vers Vault n'est pas la cause directe du probleme transport ;
- elle a en revanche revele que le chemin prive `.cascadya.internal` depend encore de mecanismes reseau non suffisamment industrialises.

Impact architectural :

- la migration `Keycloak` doit maintenant inclure une verification de non-regression des hostnames internes ;
- il ne suffit pas de valider `auth.cascadya.internal` ;
- il faut aussi revalider :
  - `wazuh.cascadya.internal`
  - `control-panel.cascadya.internal`

## 3. Constat terrain sur la VM Vault

### 3.1 Systeme et reseau

- VM : `vault-DEV1-S`
- OS : `Ubuntu 22.04.5 LTS`
- IP publique : `51.15.36.65`
- IP privee : `10.42.2.4`
- interface privee : `ens5`

Le routage prive vers les VMs applicatives existe deja :

- `10.42.1.2` joignable via `ens5`
- `10.42.1.4` joignable via `ens5`

La connectivite applicative minimale est deja validee :

- `nc -vz 10.42.1.2 443` : succes
- `nc -vz 10.42.1.4 3000` : succes

### 3.2 Services deja presents

Services natifs :

- `vault.service` actif
- `nginx.service` actif

Ports observes :

- `80/tcp` : `nginx`
- `443/tcp` : `nginx`
- `8200/tcp` : `vault`
- `8201/tcp` : `vault`
- `8080/tcp` : `cadvisor` via Docker
- `127.0.0.1:8081/tcp` : `keycloak` via Docker

Conteneurs confirmes sur Vault :

- `postgres-keycloak`
- `keycloak`
- `cadvisor`

Artefacts de deploiement confirms :

- compose dedie dans `/opt/keycloak-vault/docker-compose.yml`
- stockage applicatif sous `/opt/keycloak-vault`

### 3.3 Nginx existant

Le `nginx` actuel expose :

- `secrets.cascadya.com` -> `http://127.0.0.1:8200`
- `auth.cascadya.internal` -> `http://127.0.0.1:8081`

Le vhost TLS courant utilise un certificat `Let's Encrypt` pour `secrets.cascadya.com`.

Validation terrain :

- `curl -k --resolve auth.cascadya.internal:443:127.0.0.1 https://auth.cascadya.internal/realms/cascadya-corp/.well-known/openid-configuration`
  repond `200` localement sur Vault ;
- le `502` observe depuis le poste admin ne venait donc pas de `nginx` ou
  `Keycloak` sur Vault ;
- il venait du fait que `auth.cascadya.internal` pointait encore en DNS
  interne vers `10.42.1.2`.

### 3.4 DNS sur la VM Vault

Observation :

- `auth.cascadya.internal` n'est pas resolu localement sur Vault
- `control-panel.cascadya.internal` n'est pas resolu localement sur Vault
- `/etc/resolv.conf` pointe vers `1.1.1.1` et `8.8.8.8`

Conclusion :

- la VM Vault n'utilise pas aujourd'hui un DNS interne permettant de resoudre les hostnames `.internal` ;
- ce point n'a pas bloque la mise en service de `Keycloak` sur Vault ;
- mais il reste un drift de configuration a traiter si des traitements locaux sur
  Vault doivent un jour consommer d'autres FQDN internes.

## 4. Architecture cible ajustee

### 4.1 Principe directeur

Le composant partageable reste `Keycloak`.

Le RBAC metier du Control Panel reste local a l'application.

### 4.2 Topologie ajustee

Sur la VM Vault :

- `Vault` reste en natif et garde son exposition actuelle ;
- `nginx` reste en natif et garde le vhost `secrets.cascadya.com` ;
- un nouveau scope isole heberge `postgres-keycloak` ;
- un nouveau scope isole heberge `keycloak` ;
- `nginx` ajoute un second vhost `auth.cascadya.internal` pour `Keycloak`.

Sur la VM Control Panel :

- `FastAPI` reste local ;
- `postgres-fastapi` reste local ;
- `Traefik` local continue a servir `control-panel.cascadya.internal` ;
- `Traefik` local ne doit plus servir `auth.cascadya.internal` apres bascule ;
- `cascadya_features` reste sur cette VM.

Sur la VM Monitoring :

- `Grafana` reste sur la VM monitoring ;
- l'authentification est recablee plus tard vers le Keycloak partage.

### 4.3 Choix de reverse proxy ajuste

Decision recommandee :

- ne pas introduire `Traefik` sur la VM Vault en phase 1 ;
- reutiliser le `nginx` deja en place ;
- ajouter un vhost dedie `auth.cascadya.internal`.

Justification :

- `80/443` sont deja occupes par `nginx` ;
- `nginx` fait deja le reverse proxy de `Vault` ;
- la migration la moins risquee consiste a etendre la config existante au lieu d'introduire un second frontal HTTP.

### 4.4 Exposition cible de Keycloak

Exposition navigateur :

- `https://auth.cascadya.internal` termine sur `nginx` ;
- `nginx` reverse-proxy vers `Keycloak` en local sur Vault.

Exposition backchannel phase 1 :

- `Keycloak` doit etre joignable en prive sur `10.42.2.4:8081` ;
- ce port prive sert le Control Panel pour `discovery`, `userinfo`, `token` et `admin API`.

Exposition DB :

- `postgres-keycloak` ne doit pas etre expose publiquement ;
- l'acces doit rester limite au scope `Keycloak`, idealement sans bind host inutile.

## 5. Strategie de backchannel ajustee

### 5.1 Phase 1 recommande

Conserver l'issuer public :

- `AUTH_PROTO_OIDC_ISSUER_URL=https://auth.cascadya.internal/realms/cascadya-corp`

Basculer le backchannel du Control Panel vers l'IP privee Vault :

- `AUTH_PROTO_OIDC_DISCOVERY_URL=http://10.42.2.4:8081/realms/cascadya-corp/.well-known/openid-configuration`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=http://10.42.2.4:8081`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=http://10.42.2.4:8081`

Motif :

- la resolution DNS `.internal` n'est pas garantie aujourd'hui sur les VMs ;
- le transport prive par IP reduit le risque de bascule.

### 5.1.b Constat complementaire sur `control-panel-DEV1-S`

Le comportement reel observe apres migration montre que :

- `control-panel-DEV1-S` utilise `systemd-resolved` avec des DNS publics / metadata ;
- `10.8.0.1` n'est pas consulte par defaut pour les hostnames `.cascadya.internal` ;
- un service interne peut donc sembler "tombe" alors que :
  - la route IP est bonne ;
  - la cible TCP repond ;
  - le DNS WireGuard est sain.

Implication :

- les validations post-migration doivent distinguer explicitement :
  - la connectivite IP ;
  - la resolution DNS interne ;
  - la disponibilite HTTP/TLS.
- il faut aussi distinguer :
  - l'acces depuis les VMs applicatives ;
  - l'acces depuis un poste admin WireGuard ;
  - l'existence d'un chemin retour reseau vers `10.8.0.0/16`.

### 5.2 Phase 2 optionnelle

Une fois le DNS interne et la confiance TLS stabilises :

- `AUTH_PROTO_OIDC_DISCOVERY_URL=https://auth.cascadya.internal/realms/cascadya-corp/.well-known/openid-configuration`
- `AUTH_PROTO_OIDC_INTERNAL_BASE_URL=https://auth.cascadya.internal`
- `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL=https://auth.cascadya.internal`

## 6. Ajustements majeurs du PRD initial

### 6.1 Ce qui change

- le frontal recommande sur Vault devient `nginx`, pas `Traefik`
- le role Vault cible n'est pas un role "machine vierge", mais un role additif
- la phase 1 de backchannel doit utiliser `10.42.2.4`
- la bascule DNS ne doit intervenir qu'apres validation du vhost `auth.cascadya.internal`

### 6.2 Ce qui reste valable

- `Keycloak` est le composant mutualisable
- le `realm` `cascadya-corp` est conserve
- le `Control Panel` garde son miroir utilisateur local
- `cascadya_features` et `Grafana` restent de futurs clients OIDC
- la migration doit preserver les `sub` / `keycloak_uuid`

## 7. Evolution Ansible ajustee

### 7.1 Nouveau role recommande : `vault_vm_keycloak`

Ce role doit etre additif.

Il ne doit pas prendre possession de :

- `vault.service`
- `/etc/vault.d/vault.hcl`
- le vhost `secrets.cascadya.com`
- la config globale `nginx` hors besoin minimal documente

Responsabilites du role :

- creation d'un root runtime dedie `Keycloak`
- deploiement de `postgres-keycloak`
- deploiement de `Keycloak`
- publication privee de `Keycloak` sur `10.42.2.4:8081`
- creation d'un vhost `nginx` `auth.cascadya.internal`
- health checks `http://127.0.0.1:8081` et `https://auth.cascadya.internal`

### 7.2 Nouveau role ou sous-role recommande : `vault_nginx_auth_site`

Responsabilites :

- deposer un fichier `sites-available/auth.cascadya.internal`
- l'activer via `sites-enabled`
- recharger `nginx`
- ne pas toucher au site `secrets.cascadya.com`

### 7.3 Ajustement du role Control Panel

Le role `control_panel_auth` doit :

- cesser de deployer `postgres-keycloak`
- cesser de deployer `Keycloak`
- cesser de generer un certificat `Traefik` pour `auth.cascadya.internal`
- cesser de router `auth.cascadya.internal`
- continuer a deployer `FastAPI`, `postgres-fastapi`, `Traefik`, migrations et seed RBAC

### 7.4 Ajustement des variables

Variables partagees cibles :

- `shared_idp_domain`
- `shared_idp_realm`
- `shared_idp_private_ip`
- `shared_idp_public_base_url`
- `shared_idp_private_http_base_url`
- `shared_idp_clients`

Variables Control Panel cibles :

- `control_panel_oidc_issuer_url`
- `control_panel_oidc_discovery_url`
- `control_panel_oidc_internal_base_url`
- `control_panel_keycloak_admin_base_url`

Variables DNS :

- `wireguard_dns_records` pour `auth.cascadya.internal -> 10.42.2.4`

### 7.5 Gestion des secrets

Ce point devient bloquant.

Etat cible obligatoire :

- aucun secret `Keycloak` ou token `Vault` en clair dans un inventory Git-tracked ;
- secrets fournis via `Ansible Vault`, variables d'environnement de run, ou bootstrap depuis Vault.

### 7.6 Besoin complementaire cote VM applicatives

La migration a revele un besoin qui n'est pas strictement un role Vault, mais qui devient obligatoire pour une bascule propre :

- un mecanisme persistant de resolution DNS interne sur `control-panel-DEV1-S`.

Etat du repo aujourd'hui :

- le role `wireguard_dns` configure `dnsmasq` sur `wireguard-DEV1-S` ;
- mais aucun role ne garantit que `control-panel-DEV1-S` interroge bien `10.8.0.1` pour `.cascadya.internal`.

Recommandation :

- ajouter un sous-role de type `control_panel_internal_dns` ;
- ou etendre `control_panel_auth` avec une configuration persistante de `systemd-resolved` / netplan ;
- objectif minimal :
  - router `~cascadya.internal` vers `10.8.0.1`
  - sans casser les autres resolvers deja necessaires a la VM.

Implementation technique recommande cote `control-panel-DEV1-S` :

- ne pas dependre d'un `resolvectl dns ens6 10.8.0.1` temporaire ;
- desactiver l'injection des DNS DHCP sur `ens6` ;
- poser une configuration persistante qui force :
  - `DNS=10.8.0.1`
  - `Domains=~cascadya.internal`
  - `UseDNS=false` sur le bloc DHCP de `ens6`

Forme recommandee :

- un drop-in `systemd-networkd` pour `ens6`, plutot qu'une simple commande runtime.

### 7.7 Besoin complementaire cote gateway WireGuard

La migration a aussi mis en evidence un second manque d'industrialisation sur `wireguard-DEV1-S` :

- la gateway autorise bien le forwarding `wg0 -> ens5` ;
- mais elle ne NATe pas le trafic clients admin `10.8.0.0/16` vers le LAN prive `10.42.0.0/16`.

Etat reel observe :

- `iptables -S WIREGUARD-FORWARD` contient bien les regles :
  - `10.8.0.0/16 -> 10.42.0.0/16` via `wg0 -> ens5`
  - `10.42.0.0/16 -> 10.8.0.0/16` via `ens5 -> wg0` en `ESTABLISHED,RELATED`
- mais `iptables -t nat -S WIREGUARD-POSTROUTING` ne contient que :
  - `-s 10.8.0.0/16 -o ens2 -j MASQUERADE`

Effet :

- le poste admin WireGuard atteint bien `10.8.0.1` ;
- la gateway atteint bien `10.42.1.2` et `10.42.1.7` ;
- mais les VMs du LAN n'ont pas de route retour vers `10.8.0.0/16` et renvoient donc leurs reponses vers leur route par defaut publique.

Correctif recommande :

- ajouter un role ou sous-role Ansible de type `wireguard_lan_postrouting` ;
- ou etendre le role `wireguard` existant pour poser de maniere persistante :
  - `iptables -t nat -A WIREGUARD-POSTROUTING -s 10.8.0.0/16 -o ens5 -j MASQUERADE`

Alternative plus "propre" mais plus lourde :

- ajouter sur chaque VM du LAN prive une route retour vers `10.8.0.0/16` via `10.42.1.5`.

Decision recommandee a court terme :

- conserver le modele NAT sur `wireguard-DEV1-S` pour l'acces admin prive ;
- documenter explicitement que ce NAT fait partie du chemin critique d'acces a :
  - `control-panel.cascadya.internal`
  - `wazuh.cascadya.internal`
  - plus generalement aux VMs `10.42.1.x` depuis les clients WireGuard.

Consequence fonctionnelle immediate du NAT :

- une fois le `MASQUERADE` `wg0 -> ens5` active, les services du LAN ne voient plus directement les clients admin comme `10.8.0.x` ;
- ils voient la source traduite en `10.42.1.5`, c'est-a-dire l'IP privee de `wireguard-DEV1-S`.

Implication securite importante :

- tout service protege par une allowlist CIDR basee uniquement sur `10.8.0.0/24` devient accessible en transport ;
- mais renvoie `403` si la source visible cote service devient `10.42.1.5`.

Cas observe sur `control-panel.cascadya.internal` :

- le transport HTTPS redevient fonctionnel depuis le poste admin ;
- `Traefik` renvoie `403 Forbidden` ;
- la cause est l'`ipAllowList` du frontal qui n'autorise que :
  - `10.8.0.0/24`
  - `195.68.106.70/32`
- apres NAT, le frontal voit la source `10.42.1.5`, non incluse dans la liste.

Decision recommande :

- soit ajouter explicitement `10.42.1.5/32` dans les CIDR autorises par le frontal du Control Panel ;
- soit elargir prudemment la liste a un sous-ensemble LAN documente ;
- ne pas supprimer le filtrage, car le `403` confirme au contraire que le service reste protege.

## 8. Strategie TLS ajustee

Le certificat `Let's Encrypt` existant ne couvre que `secrets.cascadya.com`.

Pour `auth.cascadya.internal`, deux options reelles existent :

Option recommande :

- certificat interne emis par la PKI Vault ;
- distribution de la CA aux clients qui doivent verifier TLS.

Option minimale :

- certificat autosigne interne, dans la continuite de l'etat actuel cote Control Panel.

Conclusion :

- il ne faut pas supposer que `Certbot` pourra gerer `auth.cascadya.internal` comme `secrets.cascadya.com`.

## 9. Plan de migration ajuste

### Phase 0 - Baseline et sauvegarde

- exporter le realm actuel
- sauvegarder `postgres-keycloak` cote Control Panel
- lister clients, users, redirect URIs et settings

### Phase 1 - Decouplage Ansible

- extraire `Keycloak` du role `control_panel_auth`
- rendre explicites les URLs OIDC/admin du Control Panel
- preparer un realm multi-clients

### Phase 2 - Provisioning Keycloak sur Vault sans bascule DNS

- deployer `postgres-keycloak`
- deployer `Keycloak`
- exposer `Keycloak` en prive sur `10.42.2.4:8081`
- ajouter le vhost `nginx` `auth.cascadya.internal`
- verifier que `secrets.cascadya.com` continue de fonctionner

Validation minimale :

- `curl -k --resolve auth.cascadya.internal:443:10.42.2.4 https://auth.cascadya.internal/realms/cascadya-corp`
- `curl http://10.42.2.4:8081/realms/cascadya-corp`

### Phase 3 - Migration des donnees Keycloak

- restaurer le realm et les users sur la nouvelle cible
- verifier la preservation des `sub` / `keycloak_uuid`

### Phase 4 - Bascule du Control Panel avant DNS

- recabler `AUTH_PROTO_OIDC_*` vers `10.42.2.4:8081`
- recabler `AUTH_PROTO_KEYCLOAK_ADMIN_BASE_URL`
- valider login, callback, logout, introspection et admin API

### Phase 5 - Bascule DNS

Seulement apres validation du vhost `nginx` et du Control Panel :

- changer `auth.cascadya.internal` vers `10.42.2.4`
- publier `portal.cascadya.internal` vers `10.42.1.2`
- verifier qu'aucun autre hostname interne critique n'a ete casse :
  - `wazuh.cascadya.internal`
  - `control-panel.cascadya.internal`
  - `features.cascadya.internal`

### Phase 6 - Onboarding de `cascadya_features`

- creer le client `cascadya-features-web`
- ajouter l'authentification OIDC a l'application

### Phase 7 - Onboarding de `Grafana`

- creer le client `grafana-monitoring`
- configurer `GF_AUTH_GENERIC_OAUTH_*`

### Phase 8 - Nettoyage

- retirer `Keycloak` et `postgres-keycloak` de la VM Control Panel
- retirer la route locale `auth.cascadya.internal` du Traefik Control Panel
- purger les secrets versionnes

### Phase 9 - Stabilisation post-bascule

- creer le client `cascadya-portal-web`
- aligner son secret avec `/etc/cascadya-portal/cascadya-portal.env`
- verifier `redirectUris`, `webOrigins` et `post.logout.redirect.uris`
  pour `https://portal.cascadya.internal`
- revalider le flux OIDC du portail

## 10. Validation attendue ajustee

### Cote Vault

- `Vault` toujours fonctionnel via `secrets.cascadya.com`
- `nginx` sert `auth.cascadya.internal` sans exposer l'UI Vault
- `Keycloak` repond sur `10.42.2.4:8081`
- `realm cascadya-corp` accessible
- la base migree contient au minimum :
  - `control-panel-web`
  - `cascadya-features-web`
  - `grafana-monitoring`

### Cote Control Panel

- `/auth/oidc/start` redirige vers `auth.cascadya.internal`
- `/auth/callback` fonctionne
- les sessions continuent de fonctionner
- les bearer tokens sont encore introspectes correctement
- le miroir utilisateur et le RBAC local restent intacts
- `nslookup auth.cascadya.internal 10.8.0.1` fonctionne
- `nslookup wazuh.cascadya.internal 10.8.0.1` fonctionne
- `nslookup wazuh.cascadya.internal` via le resolver systeme ne renvoie pas `NXDOMAIN`
- `curl -k -I https://wazuh.cascadya.internal/` repond depuis `control-panel-DEV1-S`
- si le transit admin passe par NAT via `10.42.1.5`, l'allowlist Traefik du Control Panel inclut aussi `10.42.1.5/32`

### Cote DNS

- `auth.cascadya.internal` ne pointe plus vers `10.42.1.2`
- `auth.cascadya.internal` pointe vers `10.42.2.4`
- `portal.cascadya.internal` pointe vers `10.42.1.2`
- `wazuh.cascadya.internal` continue de pointer vers `10.42.1.7`
- la chaine `client -> control-panel resolver -> 10.8.0.1 -> 10.42.1.7` reste valide

### Cote acces admin WireGuard

- depuis le poste admin, `Resolve-DnsName control-panel.cascadya.internal` retourne `10.42.1.2`
- depuis le poste admin, `Resolve-DnsName wazuh.cascadya.internal` retourne `10.42.1.7`
- depuis le poste admin, `Resolve-DnsName auth.cascadya.internal` retourne `10.42.2.4`
- depuis le poste admin, `Resolve-DnsName portal.cascadya.internal` retourne `10.42.1.2`
- la gateway `wireguard-DEV1-S` a un handshake recent avec le peer admin ;
- `https://control-panel.cascadya.internal/` redevient joignable depuis le poste admin ;
- `https://wazuh.cascadya.internal/` redevient joignable depuis le poste admin ;
- `https://features.cascadya.internal/` repond depuis le poste admin ;
- `https://portal.cascadya.internal/` repond au minimum `303` vers `/auth/login` ;
- `https://auth.cascadya.internal/realms/cascadya-corp/.well-known/openid-configuration`
  repond depuis le poste admin ;
- la translation source `10.8.0.0/16 -> ens5` est presente et persistante sur `wireguard-DEV1-S`.

Verification complementaire pour le Control Panel :

- l'acces ne doit pas seulement etre "reachable" ;
- il ne doit pas non plus finir en `403` du frontal ;
- la source vue par `Traefik` doit etre compatible avec l'allowlist retenue apres mise en place du NAT.

### Cote Wazuh non-regression

- `https://10.42.1.7/` repond toujours
- `https://wazuh.cascadya.internal/` repond toujours
- le bouton Wazuh du Control Panel ouvre encore le vrai dashboard interne

## 11. Rollback ajuste

Rollback minimal :

- remettre `auth.cascadya.internal` vers `10.42.1.2`
- retirer si besoin `portal.cascadya.internal` du DNS interne
- remettre les variables `AUTH_PROTO_OIDC_*` vers l'ancien `Keycloak` local
- conserver le vhost `nginx` `secrets.cascadya.com` intact
- ne pas toucher au service `Vault`
- restaurer si necessaire la resolution DNS interne sur `control-panel-DEV1-S` pour `.cascadya.internal`
- restaurer si necessaire la regle NAT `wg0 -> ens5` sur `wireguard-DEV1-S` pour les clients `10.8.0.0/16`

Condition de rollback :

- ne pas detruire le `Keycloak` local trop tot
- conserver le backup DB / export realm

## 12. Decision finale ajustee

La bonne architecture cible n'est pas :

- "deployer un nouvel ingress sur Vault"

La bonne architecture cible est :

- garder `Vault` et `nginx` existants sur la VM Vault ;
- ajouter un hebergement `Keycloak` isole sur cette meme VM ;
- publier `auth.cascadya.internal` via un nouveau vhost `nginx` ;
- utiliser en phase 1 un backchannel prive `10.42.2.4:8081` ;
- basculer le DNS seulement apres validation complete ;
- embarquer un controle explicite de non-regression sur `wazuh.cascadya.internal` ;
- conserver le RBAC metier du Control Panel dans l'application.

Conclusion operationnelle constatee au 2026-04-16 :

- la migration `Keycloak` vers Vault est effectivement realisee ;
- `auth.cascadya.internal` sert bien l'IdP depuis `10.42.2.4` ;
- le drift reseau/DNS autour de la migration a ete en grande partie corrige ;
- les reliquats de drift restants sont :
  - suppression de la route legacy `auth.cascadya.internal` sur le Traefik local du Control Panel ;
  - ajout idempotent du client `cascadya-portal-web` dans le provisioning `Keycloak` sur Vault ;
  - industrialisation Ansible des corrections `dnsmasq`, NAT `wg0 -> ens5` et allowlists `10.42.1.5/32`.
