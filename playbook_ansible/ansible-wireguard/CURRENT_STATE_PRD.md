# PRD - Etat Actuel WireGuard et Routage Prive

Version: 2.2
Date: 17 avril 2026
Statut: implemente et valide, y compris DNS interne du hub

## 1. Objet

Ce document fige l'etat reellement deploye sur l'environnement `Dev1` apres la
migration du site Teltonika vers l'architecture cible a deux interfaces
WireGuard sur `wireguard-DEV1-S`.

Il sert de reference entre :

- le runtime observe ;
- l'automatisation Terraform ;
- l'automatisation Ansible ;
- les prerequis de routage sur les VMs privees.

## 2. Architecture en place

Le hub `wireguard-DEV1-S` expose maintenant deux plans WireGuard distincts :

- `wg0` pour les admins et utilisateurs humains sur `10.8.0.0/16`
- `wg1` pour les routeurs edge sur `10.9.0.0/16`

Le hub est connecte :

- a Internet via `ens2`
- au VPC prive `10.42.0.0/16` via `ens5`

Le modele retenu est un modele route, pas un NAT complet entre VPN et VPC.

## 3. Adressage actuel

### 3.1 Hub WireGuard

- Nom: `wireguard-DEV1-S`
- IP publique: `51.15.84.140`
- IP privee VPC: `10.42.1.5`
- `wg0`: `10.8.0.1/16`
- `wg1`: `10.9.0.1/16`

### 3.2 Routeur site

- Equipement: `Teltonika RUTX50`
- Interface locale WireGuard: `wg0`
- Adresse tunnel edge: `10.9.0.5/32`
- LAN site: `192.168.10.1/24`
- Reseau process local: `192.168.50.0/24` via `192.168.10.109`

### 3.3 Wazuh

- Nom: `wazuh-Dev1-S`
- IP privee VPC: `10.42.1.7`

## 4. Etat Terraform

Terraform gere maintenant un security group dedie a `wireguard-DEV1-S`.

Ouvertures publiques actuelles :

- `51820/UDP` pour `wg0`
- `51821/UDP` pour `wg1`

Le changement n'ouvre pas `51821/UDP` sur les autres VMs.

## 5. Etat Ansible

Le role Ansible `wireguard` a ete applique avec succes sur
`wireguard-DEV1-S`.

Etat automatise :

- `wg-quick@wg0` actif et active au boot
- `wg-quick@wg1` actif et active au boot
- `dnsmasq` actif et active au boot
- `wireguard-routes.service` actif et active au boot
- `net.ipv4.ip_forward = 1`
- `rp_filter = 2`
- `netfilter-persistent` desactive pour eviter les conflits

Le firewall est gere via des chaines dediees :

- `WIREGUARD-FORWARD`
- `WIREGUARD-POSTROUTING`

Le NAT actif gere par le role est limite a :

- `10.8.0.0/16 -> ens2` pour la sortie Internet des admins

Le hub porte aussi maintenant la source de verite Ansible du DNS interne prive :

- fichier gere : `/etc/dnsmasq.d/cascadya-internal.conf`
- ecoute DNS sur `wg0`
- `listen-address = 10.8.0.1`
- upstreams publics `1.1.1.1` et `1.0.0.1`

## 6. Peers actuellement en place

### 6.1 Peers admins sur `wg0`

- Daniel: `10.8.0.2/32`
- Mahmoud: `10.8.0.3/32`
- Loris: `10.8.0.4/32`
- Luc: `10.8.0.6/32`
- Dominique: `10.8.0.7/32`

### 6.2 Peer edge sur `wg1`

- Site Teltonika 10: `10.9.0.5/32`
- LAN annonce au hub: `192.168.10.0/24`

Le reseau `192.168.50.0/24` n'est pas annonce globalement au hub afin de ne
pas introduire un prefixe duplique non scalable entre plusieurs sites.

## 7. Etat Teltonika valide

Le routeur Teltonika utilise maintenant :

- adresse tunnel locale `10.9.0.5/32`
- endpoint hub `51.15.84.140:51821`
- cle publique distante `wg1`
- `AllowedIPs = 10.8.0.0/16, 10.42.0.0/16`
- `PersistentKeepalive = 25`
- `Route allowed IPs = enabled`

Etat valide observe :

- handshake recent sur le peer `wg1`
- `10.42.1.7` joint avec succes via le tunnel prive

## 8. Etat Wazuh prive

Le flux Wazuh prive est valide depuis le site.

Le retour a ete mis en place sur `wazuh-Dev1-S` via `10.42.1.5` avec les
routes suivantes :

- `10.9.0.0/16 via 10.42.1.5`
- `192.168.10.0/24 via 10.42.1.5`

Ces routes ont ete persistees via Netplan dans :

- `/etc/netplan/60-wazuh-private-routes.yaml`

## 9. Routage actuellement valide

Les chemins suivants sont valides :

- admins `10.8.0.0/16` vers VPC `10.42.0.0/16`
- admins `10.8.0.0/16` vers edge `10.9.0.0/16`
- admins `10.8.0.0/16` vers LAN site `192.168.10.0/24`
- site edge `10.9.0.0/16` vers VPC `10.42.0.0/16`
- LAN site `192.168.10.0/24` vers Wazuh prive `10.42.1.7`

## 10. Etat de validation

Valide au 17 avril 2026 :

- `wg0` actif et persistant
- `wg1` actif et persistant
- `dnsmasq` actif et persistant
- `wireguard-routes` actif et persistant
- peer Teltonika visible sur `wg1`
- handshake Teltonika recent sur `wg1`
- `10.42.1.7` joignable depuis le Teltonika
- `infracontrol.cascadya.internal` resolu en `10.42.1.4` via `10.8.0.1`
- `portal.cascadya.internal` resolu en `10.42.1.2` via `10.8.0.1`
- `features.cascadya.internal` resolu en `10.42.1.2` via `10.8.0.1`
- verification Ansible complete terminee sans erreur

## 11. Point restant cote poste admin

Le poste admin doit encore mettre a jour son client WireGuard pour inclure le
nouveau plan edge dans `AllowedIPs`.

Valeur minimale recommandee :

```ini
AllowedIPs = 10.8.0.0/16, 10.9.0.0/16, 10.42.0.0/16, 192.168.10.0/24
```

Si l'acces au reseau process est aussi souhaite :

```ini
AllowedIPs = 10.8.0.0/16, 10.9.0.0/16, 10.42.0.0/16, 192.168.10.0/24, 192.168.50.0/24
```

## 12. Decision d'architecture figee

L'etat actuel fige les choix suivants :

- separation admins et machines par interfaces distinctes
- reseau edge dedie `10.9.0.0/16`
- modele route entre WireGuard et VPC prive
- routes retour explicites sur les VMs privees concernees
- pas d'annonce globale de `192.168.50.0/24`

Cet etat est considere comme la base de reference pour les evolutions
suivantes de la plateforme `Cascadya Scale`.

## 13. Note DNS interne ajoutee et validee le 17 avril 2026

Une derive operationnelle a ete observee sur `wireguard-DEV1-S` :

- le fichier `/etc/dnsmasq.d/cascadya-internal.conf` existait bien au runtime ;
- mais il n'etait pas encore gere par ce repo ;
- des entrees ajoutees a la main pouvaient donc disparaitre lors d'une
  reconfiguration ou d'une reconstruction manuelle.

Pour supprimer cette derive, ce repository porte maintenant la source de verite
du `dnsmasq` interne du hub, et cette cible a ete reappliquee avec succes sur
`wireguard-DEV1-S` :

- ecoute sur `wg0`
- `listen-address = 10.8.0.1`
- upstreams publics `1.1.1.1` et `1.0.0.1`

Records internes desires desormais portes par l'inventaire et observes au
runtime :

- `control-panel.cascadya.internal -> 10.42.1.2`
- `auth.cascadya.internal -> 10.42.2.4`
- `wazuh.cascadya.internal -> 10.42.1.7`
- `grafana.cascadya.internal -> 10.42.1.4`
- `infracontrol.cascadya.internal -> 10.42.1.4`
- `portal.cascadya.internal -> 10.42.1.2`
- `features.cascadya.internal -> 10.42.1.2`
- `mosquitto.cascadya.internal -> 10.42.1.6`

Validation runtime observee apres reapplique Ansible :

- `/etc/dnsmasq.d/cascadya-internal.conf` contient bien les huit records attendus
- `dnsmasq.service` est `active (running)`
- `nslookup infracontrol.cascadya.internal 10.8.0.1` retourne `10.42.1.4`
- `nslookup portal.cascadya.internal 10.8.0.1` retourne `10.42.1.2`
- `nslookup features.cascadya.internal 10.8.0.1` retourne `10.42.1.2`

Le DNS interne du hub est donc desormais :

- documente dans ce PRD
- versionne dans ce repo
- gere par Ansible
- valide au runtime sur la VM cible
