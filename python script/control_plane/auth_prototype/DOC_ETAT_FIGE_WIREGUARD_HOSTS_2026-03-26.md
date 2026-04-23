# Doc - Etat fige actuel du Control Panel via WireGuard + hosts

Version: 1.0
Date: 2026-03-26
Statut: reference operationnelle actuelle
Auteur: Codex

## 1. Objet

Ce document fige l'etat qui fonctionne reellement aujourd'hui pour acceder au Control Panel.

Cette version n'est pas encore la cible ideale a long terme, mais elle est :

- fonctionnelle
- testee
- reproductible
- suffisante pour les tests internes immediats

Le mode de fonctionnement actuel est :

- acces via WireGuard
- resolution du nom `control-panel.cascadya.internal` via fichier `hosts`
- routage prive jusqu'a l'IP `10.42.1.2`
- Traefik sur `443`
- FastAPI en backend local

## 2. Ce qui fonctionne aujourd'hui

Chemin valide :

```text
Poste client
  -> WireGuard
  -> route vers 10.42.0.0/16
  -> 10.42.1.2
  -> Traefik :443
  -> FastAPI :127.0.0.1:8000
```

Tests validates :

- `ping 10.42.1.2` fonctionne depuis les clients WireGuard
- `curl.exe -k --resolve control-panel.cascadya.internal:443:10.42.1.2 https://control-panel.cascadya.internal/auth/login` fonctionne
- la page login HTML du prototype est bien servie

## 3. Pourquoi ca marche meme avec `DNS = 1.1.1.1`

La raison est simple :

- le fichier `hosts` est consulte avant le DNS externe pour ce hostname
- si `control-panel.cascadya.internal` est present dans `hosts`, Windows n'a pas besoin d'interroger `1.1.1.1`

Autrement dit :

- `1.1.1.1` ne sait pas resoudre `control-panel.cascadya.internal`
- mais ce n'est plus un probleme tant que le fichier `hosts` contient la bonne IP

Conclusion :

- aujourd'hui, le systeme fonctionne sans DNS interne
- parce que le `hosts` joue le role de resolution locale

## 4. Pourquoi ca ne marchait pas avant

Deux cas ont ete observes :

### 4.1 Cas ancien : nom pointe vers l'IP publique

```text
51.15.115.203 control-panel.cascadya.internal
```

Dans ce cas :

- le nom etait resolu
- mais le trafic partait vers l'IP publique
- ce n'etait pas un vrai chemin prive WireGuard

### 4.2 Cas voulu : nom pointe vers l'IP privee

```text
10.42.1.2 control-panel.cascadya.internal
```

Au debut, ce cas ne marchait pas car :

- la route retour depuis `control-panel-DEV1-S` vers `10.8.0.0/24` n'etait pas en place
- le transit WireGuard vers `10.42.0.0/16` n'etait pas correctement ancre

Une fois le routage corrige, ce chemin prive fonctionne.

## 5. Valeurs reseau figees

Valeurs reelles connues :

- gateway WireGuard publique : `51.15.84.140:51820`
- gateway WireGuard privee : `10.42.1.5`
- gateway WireGuard sur le tunnel : `10.8.0.1`
- reseau clients WireGuard : `10.8.0.0/24`
- reseau prive applicatif : `10.42.0.0/16`
- Control Panel public : `51.15.115.203`
- Control Panel prive : `10.42.1.2`
- domaine interne : `control-panel.cascadya.internal`

## 6. Configuration client a figer maintenant

## 6.1 Configuration de Daniel

```ini
[Interface]
PrivateKey = eLlW11UwSDSgFBETE1USkU5baUxrMg97lHueVJIikk0=
Address = 10.8.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = OMbdc2j857EBec4nbtGKM6dhWe9wBNFxXJwrQ+skvWo=
AllowedIPs = 10.8.0.0/24, 10.42.0.0/16, 192.168.50.0/24, 192.168.10.0/24
Endpoint = 51.15.84.140:51820
PersistentKeepalive = 25
```

## 6.2 Configuration de Luc

```ini
[Interface]
PrivateKey = xxxx
Address = 10.8.0.6/32
DNS = 1.1.1.1

[Peer]
PublicKey = OMbdc2j857EBec4nbtGKM6dhWe9wBNFxXJwrQ+skvWo=
AllowedIPs = 10.8.0.0/24, 10.42.0.0/16, 192.168.50.0/24
Endpoint = 51.15.84.140:51820
PersistentKeepalive = 25
```

## 7. Fichier hosts a figer maintenant

Sur les postes clients, la ligne correcte est :

```text
10.42.1.2 control-panel.cascadya.internal
```

Il ne faut plus utiliser :

```text
51.15.115.203 control-panel.cascadya.internal
```

Exemple de fichier `hosts` coherent :

```text
51.15.64.139 vm-broker.cascadya.local
10.42.1.6 mosquitto.cascadya.internal
10.42.1.2 control-panel.cascadya.internal
```

## 8. Regles reseau deja ancrees

## 8.1 Cote gateway WireGuard

Forwarding IPv4 active :

```text
net.ipv4.ip_forward = 1
```

Transit autorise entre :

- `10.8.0.0/24`
- `10.42.0.0/16`

Sans NAT, afin de conserver les vraies IP clients.

## 8.2 Cote Control Panel

Route retour active :

```text
10.8.0.0/24 via 10.42.1.5 dev ens6
```

## 8.3 Cote application

- `Traefik` ecoute sur `443`
- `FastAPI` ecoute uniquement sur `127.0.0.1:8000`
- le nom servi est `control-panel.cascadya.internal`

## 9. URL de reference actuelle

URL fonctionnelle cible :

```text
https://control-panel.cascadya.internal/auth/login
```

Condition :

- WireGuard doit etre actif
- `hosts` doit contenir `10.42.1.2 control-panel.cascadya.internal`

## 10. Regle de verification simple

### Avec WireGuard actif

Doit fonctionner :

```powershell
ping 10.42.1.2
curl.exe -k https://control-panel.cascadya.internal/auth/login
```

### Sans WireGuard

Doit echouer :

```powershell
ping 10.42.1.2
curl.exe -k https://control-panel.cascadya.internal/auth/login
```

## 11. Ce qui est fige aujourd'hui

Etat valide et fige pour les tests internes :

- pas de DNS interne pour le moment
- `hosts` manuel utilise comme source de verite de resolution
- clients WireGuard routes vers `10.42.0.0/16`
- Control Panel joint en prive sur `10.42.1.2`
- Traefik expose l'interface sur `443`

## 12. Ce qui n'est pas encore fige definitivement

Il reste encore une amelioration d'architecture a faire plus tard :

- remplacer `hosts` par un vrai DNS interne sur `10.8.0.1`

Mais ce point n'est pas bloquant pour l'avancement actuel.

## 13. Decision de gel

La decision de gel pour maintenant est :

- conserver `DNS = 1.1.1.1` sur les clients
- conserver le `hosts` vers `10.42.1.2`
- conserver `AllowedIPs` incluant `10.42.0.0/16`
- conserver le routage prive actuel

Cette decision est acceptable tant que :

- les utilisateurs sont peu nombreux
- l'objectif est la validation interne
- la maintenance manuelle du `hosts` reste supportable

## 14. Prochaine evolution, plus tard

La prochaine evolution naturelle sera :

- mettre un DNS interne sur `10.8.0.1`
- remplacer `DNS = 1.1.1.1` par `DNS = 10.8.0.1`
- supprimer le `hosts`

Mais ce n'est pas requis pour considerer l'etat actuel comme fonctionnel.
