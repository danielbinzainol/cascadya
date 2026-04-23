README — Image Debian Industrielle (EFIC-2000CA) + Mender A/B

Auteur : Stagiaire
Date : 01/09/2025

Ce document présente un résumé simple du travail réalisé pour créer, réparer et déployer une image Debian 12 fonctionnelle sur un PC industriel EFIC-2000CA, avec un partitionnement Mender A/B et un boot UEFI totalement opérationnel.

🎯 Objectif

Obtenir une image Debian :

Bootable en UEFI

Compatible Mender A/B (2 partitions)

Correctement configurée (hostname, locales FR, clavier FR)

Réseau Ethernet (DHCP) opérationnel

SSH fonctionnel

Installée proprement sur le SSD interne

🧩 Résumé des actions réalisées
✔️ 1. Correction du boot UEFI

Réparation complète de la partition EFI.

Installation propre de GRUB UEFI.

Ajout du fallback universel : EFI/BOOT/BOOTX64.EFI.

✔️ 2. Vérification et utilisation du bon rootfs

Le système Debian complet se trouvait dans rootfsB (p3), pas dans p2.

✔️ 3. Configuration système

Hostname + fichier hosts corrigés.

Locales FR générées (fr\_FR.UTF-8).

Clavier configuré en AZERTY.

✔️ 4. Réseau \& SSH

Détection interface Ethernet (DHCP).

Correction d’un conflit d’adresse IP Windows.

Service SSH testé et opérationnel.

✔️ 5. Flash final sur SSD interne

Rufus transformant l’image en disque →
→ clonage complet USB → SSD via dd.

🧪 Commandes essentielles
Monter l’image
losetup -fP --show industrial-mender.img
mount /dev/loopXp3 /mnt/img
mount /dev/loopXp1 /mnt/efi

Clonage USB → SSD (cas Rufus)
sudo dd if=/dev/sdb of=/dev/sda bs=4M status=progress conv=fsync
sync

✅ Résultat final

Le PC industriel démarre désormais :

Sans clé USB

En UEFI propre

Avec un rootfs fonctionnel (Mender B)

Un système Debian stable, propre et prêt pour un environnement industriel.

