================================================================================
FICHIER : debian-base.pkr.hcl
ROLE    : Construction de l'image de Fondation (Golden Master)
FREQ    : Très Rare (Uniquement lors d'un changement de version Debian)
DUREE   : ~30 à 60 minutes (selon hardware)
================================================================================

[DESCRIPTION]
Ce fichier Packer est responsable de la création de la couche "OS" pure.
Il part de l'ISO officiel de Debian 13 (Trixie) et effectue l'installation
silencieuse via le fichier de réponse automatique "http/preseed-uefi.cfg".

[POURQUOI CETTE ÉTAPE ?]
L'installation de Debian est longue (surtout sans accélération matérielle).
Pour éviter de perdre 45 minutes à chaque fois qu'on veut tester un script,
on isole cette étape lourde. Une fois cette image générée, on ne la touche plus.

[DÉTAILS TECHNIQUES]
1. Source       : Télécharge l'ISO Debian Netinst depuis internet.
2. Partition    : Utilise le partitionnement défini dans le Preseed (EFI + Ext4).
3. Utilisateur  : Crée l'utilisateur 'cascadya' (UID 1000).
4. Droits       : Configure 'sudo' en mode NOPASSWD (via le Preseed) pour faciliter
                  l'automatisation future par Ansible.
5. Optimisation :
   - RAM  : 4096 Mo (Pour compenser la lenteur CPU).
   - CPU  : 1 (Pour éviter le crash "RCU Stall" fréquent en émulation QEMU).
   - Timeout : 1h30 (Pour éviter que Packer ne coupe le build si l'install est lente).

[SORTIE]
Génère le dossier : output-debian-base/
Contient le fichier : debian-base.img (Disque dur virtuel de 8Go avec Debian installé).

[COMMANDE POUR LANCER]
.\packer build -var-file="packer/variables.pkr.hcl" packer/debian-base.pkr.hcl