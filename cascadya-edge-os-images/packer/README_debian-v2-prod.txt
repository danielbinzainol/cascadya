================================================================================
FICHIER : debian-v2-prod.pkr.hcl
ROLE    : Image Zero-Touch V2 basee sur le modele 2 phases
FREQ    : Frequemment pendant l'industrialisation
================================================================================

[DESCRIPTION]
Ce template part de `output-debian-base/debian-base.img`, ajoute uniquement le
mode installateur Zero-Touch, puis produit `output-final/cascadya-v2-prod.img`.
L'image finale ne contient toujours ni agent NATS ni certificats metier.

[MODE 2 PHASES]
1. Phase 1 stable
   - le preseed ne chiffre pas `/data`
   - l'objectif est d'avoir un installateur et un clonage fiables
2. Phase 2 chiffrement
   - le script `install-to-disk-v2.sh` peut ensuite creer ou conserver LUKS
   - le comportement est pilote par `/etc/default/install-to-disk`

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
