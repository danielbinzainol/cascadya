================================================================================
FICHIER : debian-base.pkr.hcl
ROLE    : Construction de l'image de fondation
FREQ    : Rare (principalement quand Debian, le preseed ou le layout changent)
DUREE   : ~30 a 60 minutes selon l'hote
================================================================================

[DESCRIPTION]
Ce template construit la couche OS Debian pure a partir de l'ISO netinst
Debian 12.13.0. Le mode par defaut est maintenant le mode "phase 1 stable" :
EFI + Root A + Root B + /data en clair.

[POURQUOI CETTE ETAPE ?]
L'installation Debian est la partie la plus lente. On la separe pour pouvoir
iterer ensuite sur l'image Zero-Touch sans reinstaller l'OS a chaque fois.

[DETAILS TECHNIQUES]
1. Source       : ISO Debian netinst officiel
2. Partition    : preseed 4 partitions (EFI + Root A + Root B + /data)
3. Utilisateur  : cree `cascadya` avec sudo NOPASSWD
4. Taille disque: image brute de 24 Go cote build
5. But          : fournir une base stable avant d'activer eventuellement LUKS

[FICHIERS PRESEED]
- Defaut stable : `http/preseed-uefi.cfg`
- Variante experimentale LUKS dans l'installeur :
  `http/preseed-uefi-v4-luks-experimental.cfg`

[SORTIE]
Dossier : `output-debian-base/`
Fichier : `debian-base.img`

[COMMANDES]
.\tools\packer.exe init packer/debian-base.pkr.hcl
.\tools\packer.exe build -var-file="packer/variables.pkr.hcl" packer/debian-base.pkr.hcl
