================================================================================
FICHIER : debian-base.pkr.hcl
ROLE    : Construction de la base Debian d'entree pour Mender
FREQ    : Rare (quand Debian, le preseed de base ou le socle OS changent)
DUREE   : ~30 a 60 minutes selon l'hote
================================================================================

[DESCRIPTION]
Ce template construit une image Debian 12 simple (EFI + rootfs) a partir de
l'ISO netinst. Cette image ne porte ni OTA, ni LUKS, ni Zero-Touch.
Elle sert d'entree stable a la conversion Mender.

[POURQUOI CETTE ETAPE ?]
On separe l'installation Debian de la conversion Mender pour garder un socle
reproductible et limiter le rayon d'impact des changements.

[DETAILS TECHNIQUES]
1. Source        : ISO Debian netinst officiel
2. Partition     : `http/preseed-uefi-mender-base.cfg` (EFI + rootfs)
3. Utilisateur   : cree `cascadya` avec sudo NOPASSWD
4. Taille disque : image brute de 24 Go cote build
5. But           : fournir l'image de reference pour `mender-convert`

[SORTIE]
Dossier : `output-debian-base/`
Fichier : `debian-base.img`

[COMMANDES]
.\tools\packer.exe init packer/debian-base.pkr.hcl
.\tools\packer.exe build -var-file="packer/variables.pkr.hcl" packer/debian-base.pkr.hcl

[ETAPE SUIVANTE]
Une fois `debian-base.img` generee, lancer :
`scripts/build_mender_image.sh`
