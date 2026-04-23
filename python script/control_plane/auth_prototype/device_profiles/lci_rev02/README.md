# Device Profile - LCI Rev02

Date: 2026-04-21

Ce dossier contient la premiere formalisation HAL du profil chaudiere LCI Rev02.

## Fichiers

| Fichier | Usage |
|---|---|
| `simulation.json` | Profil digital twin. Les commandes Rev02 restent en `%MW1000+`, mais les variables procede sont decalees avec `simulation_address = real_address + 9200`. |
| `real.json` | Profil automate physique LCI. Les commandes Rev02 restent en `%MW1000+` et les variables procede sont lues aux adresses natives LCI. |

## Statut

Ces fichiers sont pour l'instant de la documentation executable et une base de
comparaison. Ils ne sont pas encore charges par `gateway_modbus_sbc.py` au
runtime.

La premiere etape d'integration recommandee est un mode `comparison_only`:

1. charger `simulation.json` ou `real.json`;
2. comparer les registres du profil avec les constantes Python actuelles;
3. alerter si divergence;
4. ne changer aucun comportement runtime tant que la comparaison n'est pas stable.

## Invariants de securite

- Les actions NATS existantes ne changent pas: `upsert`, `delete`, `reset`,
  `read_plan`, `monitor_snapshot`.
- Le contrat d'ecriture Rev02 reste identique en simulation et en reel.
- En simulation, les registres procede terrain bas ne doivent pas etre ecrits.
- En reel, le watchdog strict est obligatoire.
- Tout registre d'ecriture doit etre explicitement declare dans
  `allowed_write_ranges`.

