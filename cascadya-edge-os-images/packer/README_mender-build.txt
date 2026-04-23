================================================================================
FICHIER : scripts/build_mender_image.sh
ROLE    : Conversion Mender de la base Debian V2
FREQ    : A chaque modification OTA / boot A/B / config Mender
================================================================================

[DESCRIPTION]
Ce script prend `output-debian-base/debian-base.img`, la convertit avec
`mender-convert`, applique l'overlay Mender Cascadya, puis sort :

- `output-mender-base/cascadya-mender-base.img`
- `output-mender-base/cascadya-mender-base.img.xz`
- `output-mender-base/cascadya-mender-base.mender` (si genere)

[CONFIGURATION]
Variables : `mender/mender-config.env`

Modes supportes :
- `standalone`
- `hosted`
- `production`

[PRE-REQUIS]
- Docker fonctionnel
- checkout `mender-convert/` present
- base image deja construite

[COMMANDE]
bash scripts/build_mender_image.sh

[ETAPE SUIVANTE]
Une fois l'image Mender convertie disponible, lancer :
`packer/debian-v2-prod.pkr.hcl`
