# Topologie WireGuard et Flux Wazuh - 2026-04-07

## 1. Objet

Ce document complete le document fige du `2026-03-26` et decrit l'etat
reellement observe les `2026-04-07` et `2026-04-08` sur le lab `Dev1`.

Objectifs :

- decrire les reseaux, les interfaces et les routes deja en place ;
- montrer quels flux WireGuard fonctionnent aujourd'hui ;
- expliquer pourquoi le chemin Wazuh public marche ;
- expliquer pourquoi le chemin Wazuh prive via WireGuard ne marchait pas au
  depart ;
- consigner la validation finale du chemin Wazuh prive apres reboot du
  Teltonika ;
- lister le changement minimal permettant de rendre Wazuh stable sans dependre
  d'une IP publique de sortie du site.

## 2. Noeuds et adresses

### 2.1 Poste client admin

- poste Daniel
- WireGuard client : `10.8.0.2/32`
- route vers :
  - `10.8.0.0/24`
  - `10.42.0.0/16`
  - `192.168.10.0/24`
  - `192.168.50.0/24`

### 2.2 VM Cloud WireGuard

- nom : `wireguard-DEV1-S`
- IP publique : `51.15.84.140`
- IP privee cloud : `10.42.1.5`
- IP tunnel WireGuard : `10.8.0.1/24`
- role :
  - hub WireGuard pour les clients `10.8.0.0/24`
  - point d'entree prive vers le reseau Cloud `10.42.x.x`
  - routeur vers les LANs site annonces par le Teltonika

### 2.3 Control Panel

- nom : `control-panel-DEV1-S`
- IP publique : `51.15.115.203`
- IP privee cloud : `10.42.1.2`

### 2.4 Wazuh

- nom : `wazuh-Dev1-S`
- hostname : `wazuh-dev1-s`
- IP publique : `51.15.48.174`
- IP privee cloud : `10.42.1.7`
- ports utiles :
  - `1514/TCP`
  - `1515/TCP`

### 2.5 Routeur site

- equipement : `Teltonika RUTX50`
- LAN site : `192.168.10.1/24`
- WireGuard site : `10.8.0.5/24`
- WAN cellulaire local : `100.89.184.107/32` sur `qmimux0`
- IP publique de sortie observee cote Internet : `80.215.101.229`

### 2.6 IPC et process

- IPC `cascadya-ipc-10-109`
- uplink IPC : `192.168.10.109/24`
- reseau process IPC : `192.168.50.1/24`
- WireGuard remote-unlock/broker : `10.30.10.109/32`
- simulateur Modbus : `192.168.50.2/24`

## 3. Vue d'ensemble

```text
Poste Daniel
  10.8.0.2
     |
     | WireGuard client
     v
wireguard-DEV1-S
  pub  51.15.84.140
  priv 10.42.1.5
  wg0  10.8.0.1
     |\
     | \__ reseau prive cloud 10.42.1.0/24
     |      |- control-panel-DEV1-S 10.42.1.2
     |      \- wazuh-Dev1-S        10.42.1.7
     |
     \__ peer site Teltonika
            10.8.0.5
              |
              |- LAN site 192.168.10.0/24
              |    \- IPC 192.168.10.109
              |
              \- route statique vers 192.168.50.0/24 via 192.168.10.109
                    \- simulateur Modbus 192.168.50.2
```

## 4. Ce qui fonctionne deja

### 4.1 Client admin vers reseau prive cloud

Observation :

- `tracert -d 10.42.1.2`
  - saut 1 : `10.8.0.1`
  - saut 2 : `10.42.1.2`

Conclusion :

- le poste admin accede bien au reseau prive cloud via `wireguard-DEV1-S`.

### 4.2 Client admin vers IPC

Observation :

- `tracert -d 192.168.10.109`
  - saut 1 : `10.8.0.1`
  - saut 2 : `10.8.0.5`
  - saut 3 : `192.168.10.109`

Conclusion :

- le LAN `192.168.10.0/24` est bien annonce par le Teltonika dans le tunnel ;
- le chemin admin vers IPC fonctionne en prive via WireGuard.

### 4.3 Client admin vers reseau process

Observation :

- `tracert -d 192.168.50.2`
  - saut 1 : `10.8.0.1`
  - saut 2 : `10.8.0.5`
  - plus de reponse ICMP ensuite
- cote Teltonika :
  - `192.168.50.0/24 via 192.168.10.109`

Conclusion :

- le reseau process est bien derriere l'IPC ;
- l'absence de reponse ICMP au dela du saut 2 ne contredit pas le routage ;
- le chemin logique est :
  - `10.8.0.2 -> 10.8.0.1 -> 10.8.0.5 -> 192.168.10.109 -> 192.168.50.2`

### 4.4 IPC vers Wazuh public

Observation :

- apres ouverture du security group Wazuh pour `80.215.101.229/32`,
  les tests suivants reussissent depuis l'IPC :
  - `1514_OK`
  - `1515_OK`
- `agent_control -i 001` est repasse `Active`
- les alertes Cascadya remontent bien sur `wazuh-dev1-s`

Conclusion :

- le chemin Wazuh public fonctionne ;
- il depend de l'IP publique de sortie du site ;
- il n'est pas durable si cette IP change apres reboot routeur ou reconnexion WAN.

## 5. Ce qui est configure aujourd'hui sur WireGuard

### 5.1 Cote client admin

Routes presentes sur le poste :

- `10.8.0.0/24`
- `10.42.0.0/16`
- `192.168.10.0/24`
- `192.168.50.0/24`

Conclusion :

- le client admin voit deja tout le graphe prive utile.

### 5.2 Cote wireguard-DEV1-S

Peer Teltonika observe :

- endpoint : `80.215.101.229:<port>`
- allowed IPs :
  - `10.8.0.5/32`
  - `192.168.10.0/24`
  - `192.168.50.0/24`

Routes observees :

- `10.42.1.7 dev ens5`
- `192.168.10.109 dev wg0`
- `192.168.50.2 dev wg0`

Conclusion :

- la VM hub sait joindre le Wazuh prive sur `ens5` ;
- la VM hub sait joindre les LANs site sur `wg0` ;
- elle joue bien le role de jonction entre le cloud prive et le site.

### 5.3 Cote Teltonika

Peer `VM_Cloud` observe :

- endpoint : `51.15.84.140:51820`
- allowed IPs :
  - `10.8.0.0/24`

Routes observees :

- `192.168.50.0/24 via 192.168.10.109`
- `ip route get 10.42.1.2`
  - sort par `qmimux0`
- `ip route get 10.42.1.7`
  - sort par `qmimux0`

Conclusion :

- le Teltonika ne route pas encore le reseau prive cloud `10.42.x.x` dans le
  tunnel WireGuard ;
- il n'annonce que le reseau WireGuard clients `10.8.0.0/24`.

## 6. Diagnostic precis du blocage Wazuh prive

### 6.1 Cote IPC

Observation :

- `ip route get 10.42.1.7`
  - `via 192.168.10.1 dev enp2s0`
- `ping 10.42.1.7` echoue
- `1514_FAIL` et `1515_FAIL` sur `10.42.1.7`

Interpretation :

- l'IPC envoie bien vers le routeur site ;
- le routeur site n'a pas de route WireGuard vers `10.42.1.7`.

### 6.2 Cote Teltonika

Observation :

- `ip route get 10.42.1.7`
  - `dev qmimux0 src 100.89.184.107`
- `ping 10.42.1.7` echoue

Interpretation :

- le routeur tente de sortir vers Internet cellulaire ;
- il n'utilise pas `wg0` pour joindre `10.42.1.7`.

### 6.3 Cote Wazuh

Observation :

- `ip route get 10.8.0.5`
  - `via 62.210.0.1 dev enp0s1`
- `ip route get 192.168.10.109`
  - `via 62.210.0.1 dev enp0s1`
- `ping 10.42.1.5` reussit
- `ping 10.8.0.5` echoue

Interpretation :

- Wazuh voit bien la gateway privee cloud `10.42.1.5` ;
- Wazuh n'a pas de route retour vers `10.8.0.0/24` ni `192.168.10.0/24`
  via `10.42.1.5`.

### 6.4 Conclusion racine

Le chemin Wazuh prive ne marche pas encore pour deux raisons :

1. le Teltonika n'annonce pas `10.42.1.7/32` ni `10.42.0.0/16` dans le peer
   WireGuard `VM_Cloud` ;
2. le retour depuis `wazuh-Dev1-S` vers `10.8.0.0/24` et `192.168.10.0/24`
   n'est pas route via `10.42.1.5`.

## 7. Ce qui est deja en place pour aider

Sur `wireguard-DEV1-S`, les observations suivantes sont favorables :

- `net.ipv4.ip_forward = 1`
- la VM hub voit :
  - `10.42.1.7` sur `ens5`
  - `192.168.10.0/24` sur `wg0`
  - `192.168.50.0/24` sur `wg0`
- des regles iptables autorisent deja le forward entre `wg0` et les reseaux site
- une regle NAT existe du cloud prive vers le LAN site :
  - `MASQUERADE ... out wg0 source 10.42.0.0/16 destination 192.168.10.0/24`

Conclusion :

- `wireguard-DEV1-S` est deja le bon point de jonction ;
- le travail restant est surtout de route/advertisement, pas de redesign complet.

## 8. Changement minimal pour activer Wazuh prive

### 8.1 Changement 1 - Teltonika

Sur le peer `VM_Cloud` du Teltonika :

- conserver :
  - endpoint `51.15.84.140:51820`
  - `Route allowed IPs`
- remplacer :
  - `Allowed IPs = 10.8.0.0/24`
- par l'une des deux options :
  - option etroite :
    - `10.8.0.0/24, 10.42.1.7/32`
  - option plus large :
    - `10.8.0.0/24, 10.42.0.0/16`

Recommendation :

- utiliser `10.42.1.7/32` si le seul besoin durable est Wazuh ;
- utiliser `10.42.0.0/16` si le site doit joindre d'autres VM privees du cloud.

### 8.2 Changement 2 - retour depuis Wazuh

Il faut ensuite une strategie de retour. Deux modeles sont possibles.

Modele A - routage propre, preferable :

- ajouter une route retour vers le site via `10.42.1.5` depuis Wazuh ou depuis
  le plan de routage prive cloud ;
- cibles minimales :
  - `192.168.10.0/24 via 10.42.1.5`
  - idealement aussi `10.8.0.0/24 via 10.42.1.5`

Modele B - NAT sur `wireguard-DEV1-S`, plus simple mais moins propre :

- SNAT du trafic site vers `10.42.1.7` pour que Wazuh voie la source
  `10.42.1.5` au lieu de l'IP reelle de l'IPC.

Recommendation :

- viser d'abord le Modele A ;
- garder le Modele B comme secours si le routage cloud n'est pas pilotable.

### 8.3 Changement 3 - Wazuh agent

Une fois le chemin prive valide :

- remplacer la cible publique `51.15.48.174`
- par la cible privee `10.42.1.7`

Valeurs cible :

- `AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT=10.42.1.7`
- `AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT=10.42.1.7`

## 9. Runbook de privatisation du lien Wazuh

Cette section donne la sequence operationnelle recommande pour sortir du mode
`Wazuh public` et passer en `Wazuh prive via WireGuard`.

### 9.1 Strategie recommandee

Mode recommande :

1. faire annoncer `10.42.1.7/32` par le peer `VM_Cloud` du Teltonika ;
2. etablir un vrai retour depuis `wazuh-Dev1-S` vers `192.168.10.0/24`
   via `10.42.1.5` ;
3. basculer la config Wazuh de l'IPC de `51.15.48.174` vers `10.42.1.7` ;
4. garder le mode public seulement comme secours temporaire.

Mode de secours si le routage retour cloud est difficile a piloter :

1. faire annoncer `10.42.1.7/32` par le Teltonika ;
2. SNATer le trafic `site -> 10.42.1.7` sur `wireguard-DEV1-S` en
   `10.42.1.5` ;
3. basculer l'agent Wazuh de l'IPC vers `10.42.1.7`.

### 9.2 Etape 1 - modifier le peer WireGuard sur le Teltonika

Dans l'UI Teltonika :

- `Services > VPN > WireGuard`
- interface : `wg0`
- peer : `VM_Cloud`

Valeurs a conserver :

- `Endpoint host = 51.15.84.140`
- `Route allowed IPs = enabled`

Valeur a modifier :

- ancien :
  - `Allowed IPs = 10.8.0.0/24`
- nouveau recommande :
  - `Allowed IPs = 10.8.0.0/24, 10.42.1.7/32`

Option plus large si le site doit joindre d'autres VMs privees :

- `Allowed IPs = 10.8.0.0/24, 10.42.0.0/16`

Verification immediate sur le Teltonika :

```sh
wg show
ip route get 10.42.1.7
ping -c 3 10.42.1.5
ping -c 3 10.42.1.7
```

Resultat attendu :

- le peer `VM_Cloud` reste en handshake ;
- `ip route get 10.42.1.7` doit sortir par `wg0` et non plus par `qmimux0`.

### 9.3 Etape 2A - routage propre cote Wazuh (recommande)

Test temporaire sur `wazuh-Dev1-S` :

```bash
sudo ip route add 192.168.10.0/24 via 10.42.1.5
sudo ip route add 192.168.50.0/24 via 10.42.1.5
ip route get 192.168.10.109
ping -c 3 10.42.1.5
```

Resultat attendu :

- `ip route get 192.168.10.109` doit maintenant sortir via `10.42.1.5`.

Persistancer recommandee sur `wazuh-Dev1-S` :

Ne pas modifier directement `50-cloud-init.yaml`, car ce fichier est gere par
cloud-init et peut etre reecrit au reboot.

Creer un fichier netplan additionnel :

```bash
sudo tee /etc/netplan/60-wazuh-private-routes.yaml >/dev/null <<'EOF'
network:
  version: 2
  ethernets:
    enp1s0:
      dhcp4: true
      routes:
        - to: 192.168.10.0/24
          via: 10.42.1.5
        - to: 10.8.0.0/24
          via: 10.42.1.5
EOF
```

Si l'on veut aussi reacher durablement le reseau process depuis le cloud prive :

```bash
sudo tee /etc/netplan/60-wazuh-private-routes.yaml >/dev/null <<'EOF'
network:
  version: 2
  ethernets:
    enp1s0:
      dhcp4: true
      routes:
        - to: 192.168.10.0/24
          via: 10.42.1.5
        - to: 192.168.50.0/24
          via: 10.42.1.5
        - to: 10.8.0.0/24
          via: 10.42.1.5
EOF
```

Puis valider :

```bash
sudo netplan generate
sudo netplan try
sudo netplan apply
ip route get 192.168.10.109
ip route get 10.8.0.5
```

Note :

- pour le seul trafic Wazuh agent -> manager, la route critique est
  `192.168.10.0/24 via 10.42.1.5` ;
- `192.168.50.0/24` est utile si l'on veut plus tard reacher le reseau process
  depuis le cloud prive ;
- `10.8.0.0/24 via 10.42.1.5` n'est utile que si l'on veut aussi que
  `wazuh-Dev1-S` parle directement aux clients admin du plan `10.8.0.0/24`.

### 9.4 Etape 2B - SNAT de secours sur wireguard-DEV1-S

Utiliser cette variante si la route retour sur `wazuh-Dev1-S` ne peut pas etre
ajoutee proprement tout de suite.

Sur `wireguard-DEV1-S` :

```bash
sudo iptables -t nat -A POSTROUTING -s 192.168.10.0/24 -d 10.42.1.7/32 -o ens5 -j SNAT --to-source 10.42.1.5
sudo iptables -t nat -L -n -v | grep 10.42.1.7
```

Ce que fait cette regle :

- l'IPC et le site continuent d'envoyer vers `10.42.1.7` via `wg0` ;
- `wireguard-DEV1-S` presente la source `10.42.1.5` a Wazuh ;
- `wazuh-Dev1-S` n'a alors plus besoin de connaitre `192.168.10.0/24` pour
  repondre au flux Wazuh.

Persistancer a faire ensuite selon la mecanique retenue sur cette VM :

- via `netfilter-persistent` si deja utilise ;
- ou en codifiant la regle dans l'automatisation infra/Ansible.

### 9.5 Etape 3 - basculer l'agent Wazuh de l'IPC vers l'IP privee

#### Mode rapide sur l'IPC

```bash
sudo cp /var/ossec/etc/ossec.conf /var/ossec/etc/ossec.conf.bak-20260407
sudo sed -i 's#51\.15\.48\.174#10.42.1.7#g' /var/ossec/etc/ossec.conf
sudo grep -nE '10\.42\.1\.7|51\.15\.48\.174' /var/ossec/etc/ossec.conf
sudo systemctl restart wazuh-agent
sudo tail -n 50 /var/ossec/logs/ossec.log
```

Resultat attendu :

- plus aucune reference active a `51.15.48.174` ;
- connexion vers `10.42.1.7:1514`.

#### Mode durable via control-plane

Sur `control-panel-DEV1-S`, dans `/etc/control-panel/auth-prototype.env` :

```env
AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_ADDRESS_DEFAULT=10.42.1.7
AUTH_PROTO_PROVISIONING_WAZUH_MANAGER_PORT_DEFAULT=1514
AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_SERVER_DEFAULT=10.42.1.7
AUTH_PROTO_PROVISIONING_WAZUH_REGISTRATION_PORT_DEFAULT=1515
```

Puis rejouer le workflow :

- `wazuh-agent-deploy-validate`

ou a minima :

- `wazuh-agent-deploy.yml`
- `wazuh-agent-validate.yml`

### 9.6 Etape 4 - valider le chemin prive de bout en bout

Sur le Teltonika :

```sh
ip route get 10.42.1.7
ping -c 3 10.42.1.7
```

Sur l'IPC :

```bash
ip route get 10.42.1.7
ping -c 3 10.42.1.7
timeout 5 bash -c 'echo > /dev/tcp/10.42.1.7/1514' && echo 1514_OK || echo 1514_FAIL
timeout 5 bash -c 'echo > /dev/tcp/10.42.1.7/1515' && echo 1515_OK || echo 1515_FAIL
sudo systemctl restart wazuh-agent
sudo tail -n 50 /var/ossec/logs/ossec.log
```

Sur `wazuh-Dev1-S` :

```bash
sudo /var/ossec/bin/agent_control -i 001
sudo tail -F /var/ossec/logs/alerts/alerts.json
```

Puis sur l'IPC :

```bash
sudo systemctl restart gateway_modbus.service
sleep 3
sudo journalctl -u gateway_modbus.service -n 10 --no-pager
```

Validation finale attendue :

- `agent_control -i 001` = `Active`
- `1514_OK`
- `1515_OK`
- alerte `100521` visible sur `wazuh-dev1-s`
- plus aucun besoin operationnel de l'IP publique `80.215.101.229/32`

### 9.7 Checklist de rollback

Si le chemin prive ne fonctionne pas immediatement :

1. remettre le peer Teltonika sur `Allowed IPs = 10.8.0.0/24` ;
2. remettre `51.15.48.174` dans `/var/ossec/etc/ossec.conf` ;
3. redemarrer `wazuh-agent` ;
4. verifier le retour du lien public avec :

```bash
timeout 5 bash -c 'echo > /dev/tcp/51.15.48.174/1514' && echo 1514_OK || echo 1514_FAIL
timeout 5 bash -c 'echo > /dev/tcp/51.15.48.174/1515' && echo 1515_OK || echo 1515_FAIL
sudo systemctl restart wazuh-agent
```

## 10. Sequence de validation apres changement

### 10.1 Teltonika

Attendu :

```sh
ip route get 10.42.1.7
```

Resultat voulu :

- sortie via `wg0`
- et non plus via `qmimux0`

### 10.2 IPC

Attendus :

```sh
ping -c 3 10.42.1.7
timeout 5 bash -c 'echo > /dev/tcp/10.42.1.7/1514' && echo 1514_OK || echo 1514_FAIL
timeout 5 bash -c 'echo > /dev/tcp/10.42.1.7/1515' && echo 1515_OK || echo 1515_FAIL
```

### 10.3 Wazuh

Attendus :

```sh
ip route get 192.168.10.109
ip route get 10.8.0.5
```

Resultat voulu :

- route via `10.42.1.5` ou mecanisme NAT confirme sur `wireguard-DEV1-S`

### 10.4 Fin de validation

Attendus :

- `agent_control -i 001` = `Active`
- alertes `100520` / `100521` visibles
- plus aucune dependance operationnelle au `/32` public du site

## 11. Addendum 2026-04-08 - reboot Teltonika valide

Le test de reboot du Teltonika a confirme les points suivants :

- apres reboot, le peer `VM_Cloud` remonte bien sur le Teltonika ;
- `ip route get 10.42.1.7` sort toujours via `wg0` ;
- cote `wireguard-DEV1-S`, le peer Teltonika reprend bien un handshake recent ;
- depuis l'IPC, `ping 10.42.1.7` redevient fonctionnel ;
- `wazuh-agent` cote IPC tente de se reconnecter vers `10.42.1.7:1514`,
  connait une phase transitoire d'erreurs pendant le reboot, puis retrouve une
  connexion stable ;
- le redemarrage de `gateway_modbus.service` aboutit de nouveau a
  `[GATEWAY] SteamSwitch gateway is running.` ;
- une nouvelle ligne `100521` est bien visible dans `alerts.json` apres reboot ;
- la preuve transport et la preuve applicative Wazuh prive sont donc toutes deux
  validees apres reprise.

Conclusion :

- le chemin prive Wazuh survit au reboot du routeur site ;
- le transport Wazuh ne depend plus operationnellement de l'IP publique NAT du
  site ;
- le fallback public `1514/TCP` et `1515/TCP` peut etre retire apres validation
  interne finale de l'equipe.

## 12. Resume executif

Etat au `2026-04-07` :

- l'admin privee via WireGuard fonctionne ;
- l'acces prive au site `192.168.10.0/24` fonctionne ;
- le reseau process `192.168.50.0/24` est bien derriere l'IPC ;
- le flux Wazuh public fonctionne ;
- le flux Wazuh prive ne fonctionne pas encore.

Cause racine du Wazuh prive non fonctionnel :

- Teltonika ne route pas `10.42.1.7` vers `wg0`
- Wazuh ne route pas `192.168.10.0/24` ni `10.8.0.0/24` vers `10.42.1.5`

Changement minimal recommande :

1. ajouter `10.42.1.7/32` ou `10.42.0.0/16` dans les `Allowed IPs` du peer
   `VM_Cloud` sur le Teltonika ;
2. ajouter la route retour vers le site via `10.42.1.5`, ou SNATer ce flux sur
   `wireguard-DEV1-S` ;
3. basculer la config Wazuh de `51.15.48.174` vers `10.42.1.7`.

Etat final au `2026-04-08` :

- ces trois changements ont ete appliques ;
- le chemin prive Wazuh est valide avant et apres reboot du Teltonika ;
- la cible d'exploitation retenue est `10.42.1.7` via `WireGuard`.
