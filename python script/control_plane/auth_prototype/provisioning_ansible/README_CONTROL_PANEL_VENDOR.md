## Control Panel Vendor Copy

Ce dossier contient la copie Ansible de provisioning IPC utilisee directement par `auth_prototype`.

Objectif :

- garder le runner du dashboard et les playbooks dans le meme repo
- simplifier le debug sur VM
- eviter de dependre d'un second repo externe pour le workflow de provisioning

Chemin attendu sur la VM :

- `/opt/control-panel/control_plane/auth_prototype/provisioning_ansible`

Notes :

- les artefacts runtime Ansible sont generes dans `provisioning_ansible/.tmp/`
- ce dossier `.tmp/` ne doit pas etre versionne ni sync en production
- certains fichiers documentaires de cette copie mentionnent encore le repo historique `cascadya-edge-os-images/ansible`
- la copie control-panel a ete ajustee pour rester compatible avec `ansible-core 2.12` sur la VM
