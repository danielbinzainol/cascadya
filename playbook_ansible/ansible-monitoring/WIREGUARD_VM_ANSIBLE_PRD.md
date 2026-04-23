# PRD
# Mise En Place De La VM WireGuard
# Version: 1.0
# Date: 10 avril 2026
# Statut: cible d'implementation Ansible

## 1. Contexte

La VM `wireguard-DEV1-S` sert de point d'entree VPN, de plan de management prive, et d'overlay reseau pour l'environnement dev.

Le Terraform actuel provisionne deja la machine et son rattachement reseau :

- VM `wireguard-DEV1-S`
- type `DEV1-S`
- image `ubuntu_jammy`
- volume data `10 Go`
- reseau prive `app`
- IP publique exposee pour `51820/UDP`
- reseau VPN `10.8.0.0/24`

L'objectif de ce PRD est de definir ce que le playbook Ansible doit faire sur cette VM pour rendre le service WireGuard reproductible, persistent, auditable et compatible avec l'architecture reseau actuelle.

## 2. Etat actuel observe

Etat runtime constate au 10 avril 2026 :

- IP publique WireGuard : `51.15.84.140`
- IP privee WireGuard sur le reseau `app` : `10.42.1.5`
- interface WireGuard : `wg0`
- IP WireGuard serveur : `10.8.0.1/24`
- reseau prive cible principal : `10.42.0.0/16`
- VM monitoring privee : `10.42.1.4`

Comportement observe :

- le serveur WireGuard accepte bien les handshakes client ;
- la VM WireGuard peut joindre `10.42.1.4:3000` ;
- le forwarding IPv4 est actif ;
- les regles `iptables` de forwarding existent deja ;
- l'acces client VPN vers la VM monitoring ne fonctionne correctement qu'une fois une route de retour ajoutee sur la VM cible :
  - `10.8.0.0/24 via 10.42.1.5`

Conclusion architecture :

- le comportement effectif valide un **mode route** entre `10.8.0.0/24` et `10.42.0.0/16` ;
- ce n'est pas un mode NAT complet entre le reseau VPN et le reseau prive ;
- le playbook WireGuard doit donc assumer un role de **routeur VPN**, et la gestion des routes de retour sur les VMs privees doit etre explicite dans la solution globale.

## 3. Etat cible cote Terraform

Terraform reste la source de verite pour :

- la creation de la VM `wireguard-DEV1-S`
- l'IP publique
- le rattachement au reseau prive `app`
- les security groups
- l'ouverture de `51820/UDP`

References d'infrastructure actuelles :

- reseau VPN : `10.8.0.0/24`
- reseau prive `app` : `10.42.1.0/24`
- reseau prive global autorise : `10.42.0.0/16`
- WireGuard public endpoint : `51.15.84.140:51820`

Le playbook Ansible ne doit pas dupliquer les responsabilites Terraform sur les security groups Scaleway.

## 4. Objectif produit

Deployer sur `wireguard-DEV1-S` une configuration WireGuard serveur qui permette :

- l'acces VPN des postes admins ;
- l'acces prive aux VMs du VPC via `10.42.0.0/16` ;
- le transport eventuel de sous-reseaux distants annonces par certains peers ;
- une persistance apres reboot ;
- une configuration geree par variables Ansible ;
- un ajout de peers sans edition manuelle sur la VM.

## 5. Decision d'architecture

### Mode retenu

Le playbook cible un **mode route**.

Cela signifie :

- les clients VPN gardent une IP source de type `10.8.0.x` ;
- la VM WireGuard route le trafic entre `wg0` et le reseau prive `10.42.0.0/16` ;
- on ne NAT pas par defaut le trafic `10.8.0.0/24 -> 10.42.0.0/16`.

### Consequence importante

Pour qu'une VM privee reponde correctement a un client VPN, elle doit connaitre le chemin de retour vers `10.8.0.0/24`.

Exemple valide observe pour la VM monitoring :

- destination VPN : `10.8.0.0/24`
- next-hop : `10.42.1.5`

Le PRD du playbook WireGuard doit donc assumer deux choses :

- le role WireGuard configure correctement le serveur VPN et le forwarding ;
- la plateforme doit aussi prevoir un mecanisme de route de retour sur les VMs privees, via un role compagnon, cloud-init ou systemd.

## 6. Perimetre du playbook Ansible WireGuard

Le playbook doit gerer sur la VM WireGuard :

- installation des paquets WireGuard ;
- activation du forwarding IPv4 ;
- configuration de l'interface `wg0` ;
- declaration des peers via variables ;
- configuration persistante des regles de forwarding ;
- persistance des regles au reboot ;
- verification de sante post-deploiement ;
- optionalement, installation d'outils reseau de debug.

Le playbook peut aussi gerer :

- une route locale vers les sous-reseaux peers annonces ;
- une politique `iptables` ou `nftables` claire pour `wg0`.

## 7. Hors perimetre

Le playbook WireGuard ne doit pas, dans ce lot :

- modifier les security groups Scaleway ;
- creer la VM ;
- gerer directement les routes de retour sur toutes les VMs privees ;
- gerer une PKI TLS ;
- introduire un reverse proxy ;
- changer le modele reseau vers du NAT sans decision explicite.

## 8. Fichiers recommandes dans le repo Ansible

Structure cible recommandee pour `ansible-wireguard` :

- `inventory/hosts.ini`
- `inventory/group_vars/wireguard.yml`
- `playbooks/wireguard.yml`
- `roles/wireguard/defaults/main.yml`
- `roles/wireguard/tasks/main.yml`
- `roles/wireguard/tasks/install.yml`
- `roles/wireguard/tasks/configure.yml`
- `roles/wireguard/tasks/firewall.yml`
- `roles/wireguard/tasks/verify.yml`
- `roles/wireguard/handlers/main.yml`
- `roles/wireguard/templates/wg0.conf.j2`
- `roles/wireguard/templates/wireguard-routes.service.j2` si un service systemd est retenu
- `roles/wireguard/templates/iptables-rules.v4.j2` si `iptables-persistent` est retenu

## 9. Inventaire et point d'entree

### inventory/hosts.ini

Doit contenir au minimum :

- le host `vm-wireguard`
- `ansible_user=ubuntu`
- la cle SSH actuelle

### playbooks/wireguard.yml

Doit rester simple :

- un seul playbook d'entree ;
- `become: yes` ;
- un role unique `wireguard` tant que le perimetre reste lisible.

## 10. Variables et entrees attendues

Le role doit consommer explicitement :

- `wireguard_interface: wg0`
- `wireguard_listen_port: 51820`
- `wireguard_server_address: 10.8.0.1/24`
- `wireguard_public_interface: ens2`
- `wireguard_private_interface: ens5`
- `wireguard_private_ip: 10.42.1.5`
- `wireguard_vpn_cidr: 10.8.0.0/24`
- `wireguard_private_cidrs`
- `wireguard_allowed_client_networks`
- `wireguard_peers`

Variables recommandees :

- `wireguard_enable_ip_forward: true`
- `wireguard_manage_firewall_rules: true`
- `wireguard_firewall_backend: iptables`
- `wireguard_enable_nat_to_private: false`
- `wireguard_enable_nat_to_internet: true`
- `wireguard_debug_tools_enabled: true`

Secrets requis au runtime :

- `WIREGUARD_PRIVATE_KEY`

Optionnellement :

- `wireguard_preshared_key` par peer

Les cles privees ne doivent pas etre versionnees en clair.

## 11. Modele de peers

Le role doit permettre une definition declarative des peers, par exemple :

```yaml
wireguard_peers:
  - name: daniel-windows
    public_key: "..."
    allowed_ips:
      - "10.8.0.2/32"
    client_routes:
      - "10.42.0.0/16"
      - "192.168.50.0/24"
      - "192.168.10.0/24"
    persistent_keepalive: 25
```

Le role doit supporter deux cas :

- peer simple : uniquement une IP VPN `/32`
- peer routeur/site distant : une IP VPN plus un ou plusieurs LAN additionnels

## 12. Configuration WireGuard attendue

Le fichier `wg0.conf` doit :

- definir l'adresse `10.8.0.1/24` ;
- ecouter sur `51820` ;
- charger la cle privee depuis une variable secrete ;
- declarer tous les peers ;
- rester lisible et entierement genere par template.

Le service cible doit etre :

- `wg-quick@wg0`
- active au boot
- relance correctement si la configuration change

## 13. Forwarding et routage

Le playbook doit rendre persistants :

- `net.ipv4.ip_forward = 1`
- les regles de forwarding entre `wg0` et `ens5`

Regles minimales attendues en mode route :

- accept `wg0 -> reseaux prives`
- accept `reseaux prives -> wg0`
- accept `wg0 -> LANs peers annonces`
- accept retour `RELATED,ESTABLISHED`

Le role doit **eviter par defaut** une regle de type :

- `MASQUERADE` pour `10.8.0.0/24 -> 10.42.0.0/16`

car cela changerait le modele d'architecture et imposerait des adaptations de security groups sur les VMs cibles.

En revanche, le NAT de sortie vers Internet peut rester possible si necessaire pour les clients VPN.

## 14. Routes de retour sur les VMs privees

Ce point doit apparaitre noir sur blanc dans le PRD de solution :

- l'acces VPN aux VMs privees ne sera complet que si les VMs cibles savent renvoyer `10.8.0.0/24` vers `10.42.1.5`

Mecanismes acceptables hors role WireGuard :

- cloud-init Terraform par VM
- role Ansible compagnon
- unit systemd dediee par VM
- netplan si la fusion de config est maitrisee

Exemple valide :

```bash
ip route replace 10.8.0.0/24 via 10.42.1.5 dev ens6
```

## 15. Changements attendus dans le role

### install.yml

A gerer :

- installation de `wireguard`
- installation de `iptables-persistent` si retenu
- installation optionnelle de `curl`, `tcpdump`, `net-tools`

### configure.yml

A gerer :

- creation de `/etc/wireguard`
- rendu du template `wg0.conf`
- permissions strictes sur les fichiers sensibles
- activation de `wg-quick@wg0`

### firewall.yml

A gerer :

- `sysctl` de forwarding
- regles `iptables`
- persistance apres reboot

### verify.yml

A gerer :

- `wg show`
- `ip addr show wg0`
- `ip route`
- presence des regles firewall
- connectivite vers une VM privee de reference

## 16. Exigences de securite

Le role doit :

- eviter tout secret en clair dans les templates versionnes ;
- proteger `wg0.conf` en `0600` ;
- ne pas ouvrir de ports locaux supplementaires inutiles ;
- ne pas casser l'acces SSH d'administration ;
- rendre les changements de peers auditables par git.

## 17. Exigences de compatibilite

Le playbook doit etre compatible avec :

- Windows clients WireGuard
- peers simples `/32`
- peers annonçant des sous-reseaux additionnels
- l'overlay `10.8.0.0/24`
- le VPC prive `10.42.0.0/16`

Il doit aussi rester coherent avec les security groups Terraform deja en place, qui referencent explicitement `10.8.0.0/24` pour certains acces d'administration.

## 18. Criteres d'acceptation

Le role est considere termine si :

- `wg-quick@wg0` est actif et active au boot ;
- `wg show` liste les peers attendus ;
- `net.ipv4.ip_forward = 1` ;
- les regles de forwarding persistent apres reboot ;
- un client `10.8.0.x` peut joindre une VM privee `10.42.x.x` lorsque la route de retour existe sur la VM cible ;
- l'acces a `http://10.42.1.4:3000/` depuis un client VPN fonctionne ;
- aucune cle privee n'est en clair dans le repo ;
- l'ajout d'un peer passe par variables Ansible, pas par edition manuelle sur le serveur.

## 19. Ordre de developpement recommande

1. Creer l'inventaire et le playbook d'entree.
2. Poser `defaults/main.yml`.
3. Implementer l'installation WireGuard.
4. Templater `wg0.conf`.
5. Activer `wg-quick@wg0`.
6. Ajouter `sysctl` et forwarding.
7. Ajouter la persistance firewall.
8. Ajouter les taches de verification.
9. Documenter explicitement la dependance aux routes de retour sur les VMs privees.

## 20. Resume executif

La VM `wireguard-DEV1-S` n'est pas seulement un point d'entree VPN. Dans l'architecture actuelle, elle joue aussi le role de routeur entre :

- `10.8.0.0/24` (reseau VPN)
- `10.42.0.0/16` (reseau prive VPC)

Le playbook Ansible cible doit donc faire plus qu'installer WireGuard :

- gerer `wg0`
- gerer le forwarding
- gerer la persistance
- gerer les peers
- expliciter le besoin de routes de retour sur les VMs privees

Le point cle mis en evidence pendant le debug est le suivant :

- le serveur WireGuard et le monitoring etaient sains ;
- la panne provenait du **chemin de retour** depuis la VM monitoring vers `10.8.0.0/24`.

Le PRD du role WireGuard doit donc figer ce choix d'architecture et eviter qu'il reste implicite.
