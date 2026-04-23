================================================================================
FICHIER : debian-v2-prod.pkr.hcl
ROLE    : Image Zero-Touch V2 a partir de la base Debian simple + payload Mender
FREQ    : Frequemment pendant l'industrialisation
================================================================================

[DESCRIPTION]
Ce template part de `output-debian-base/debian-base.img`, ajoute le mode
installateur Zero-Touch, embarque `output-mender-base/cascadya-mender-base.img.xz`
comme payload d'installation, puis produit `output-final/cascadya-v2-prod.img`.
L'image finale ne contient toujours ni agent NATS ni certificats metier.

[CHAINAGE RECOMMANDE]
1. `packer/debian-base.pkr.hcl`
2. `scripts/build_mender_image.sh`
3. `packer/debian-v2-prod.pkr.hcl`

[MODE 2 PHASES]
1. La base Debian simple boote de maniere fiable depuis la cle USB
2. Le script `install-to-disk-v2.sh` ecrit ensuite le payload Mender sur l'IPC
   et peut chiffrer `/data` selon `/etc/default/install-to-disk`

[PRE-REQUIS]
- `output-debian-base/debian-base.img`
- `output-mender-base/cascadya-mender-base.img.xz`

[BASCULES ZERO-TOUCH]
Fichier embarque : `/etc/default/install-to-disk`

- `ZERO_TOUCH_ENABLE_LUKS=false`
  Le SSD cible garde `/data` en ext4 classique

- `ZERO_TOUCH_ENABLE_LUKS=true`
  Le SSD cible cree ou preserve un conteneur LUKS sur la partition 4

- `DATA_LUKS_PASSPHRASE=admin`
  Phrase de passe temporaire utilisee si LUKS est active

[SORTIE]
Dossier : `output-final/`
Fichier : `cascadya-v2-prod.img`

[COMMANDES]
.\tools\packer.exe init packer/debian-v2-prod.pkr.hcl
.\tools\packer.exe build -var-file="packer/variables.pkr.hcl" packer/debian-v2-prod.pkr.hcl
