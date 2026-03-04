#!/bin/bash
set -e

# --------------------------------------------------------------------------
# Répertoire du projet
# --------------------------------------------------------------------------
PROJECT_ROOT="$(pwd)"

print_status() {
    if [ "$1" -eq 0 ]; then
        echo "✅ $2"
    else
        echo "❌ $2"
        [ -n "$3" ] && echo "   💡 $3"
    fi
}

echo "========================================"
echo "   PRÉPARATION DE L'ENVIRONNEMENT"
echo "========================================"

# Chargement du .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
    echo "❌ Fichier .env introuvable"
    exit 1
fi

# Vérification KVM
if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    print_status 0 "Accélération KVM détectée."
else
    echo "⚠️  ATTENTION: /dev/kvm inaccessible."
fi

# --------------------------------------------------------------------------
# Recherche OVMF
# --------------------------------------------------------------------------
echo "--- Recherche du Firmware UEFI (OVMF) ---"

POSSIBLE_CODE_PATHS=(
    "/usr/share/OVMF/OVMF_CODE.fd"
    "/usr/share/ovmf/OVMF.fd"
    "/usr/share/qemu/OVMF.fd"
    "/usr/share/edk2/ovmf/OVMF_CODE.fd"
)

OVMF_CODE=""
for p in "${POSSIBLE_CODE_PATHS[@]}"; do
    [ -f "$p" ] && OVMF_CODE="$p" && break
done

if [ -z "$OVMF_CODE" ]; then
    OVMF_CODE=$(find /usr/share -name "OVMF_CODE.fd" -o -name "OVMF.fd" 2>/dev/null | head -n 1)
fi

[ -z "$OVMF_CODE" ] && echo "❌ OVMF_CODE introuvable" && exit 1
print_status 0 "Firmware Code trouvé : $OVMF_CODE"

OVMF_VARS=$(find /usr/share -name "OVMF_VARS*.fd" 2>/dev/null | head -n 1)
[ -z "$OVMF_VARS" ] && echo "❌ OVMF VARS introuvable" && exit 1
print_status 0 "Firmware Vars trouvé : $OVMF_VARS"

# --------------------------------------------------------------------------
# Vérification ISO
# --------------------------------------------------------------------------
echo "--- Vérification ISO ---"

if [[ "$ISO_CHECKSUM" == "file:SHA256SUMS" ]]; then
    wget -q "$(dirname "$ISO_URL")/SHA256SUMS" -O SHA256SUMS || true

    ISO_FILENAME=$(basename "$ISO_URL")
    HASH=$(grep "$ISO_FILENAME" SHA256SUMS | awk '{print $1}')

    if [ -z "$HASH" ]; then
        echo "⚠️ Hash non trouvé : tentative auto..."
        ALT=$(grep "netinst.iso" SHA256SUMS | grep amd64 | head -n 1)
        ISO_URL="$(dirname "$ISO_URL")/$(echo "$ALT" | awk '{print $2}' | sed 's/*//')"
        PACKER_ISO_CHECKSUM="sha256:$(echo "$ALT" | awk '{print $1}')"
        print_status 0 "ISO alternative trouvée : $(basename "$ISO_URL")"
    else
        PACKER_ISO_CHECKSUM="sha256:$HASH"
    fi
else
    PACKER_ISO_CHECKSUM="$ISO_CHECKSUM"
fi

# --------------------------------------------------------------------------
# Génération Preseed
# --------------------------------------------------------------------------
mkdir -p http
sed \
 -e "s|__HOSTNAME__|${HOSTNAME}|g" \
 -e "s|__USERNAME__|${USERNAME}|g" \
 -e "s|__PASSWORD__|${PASSWORD}|g" \
 http/preseed-uefi.cfg.tpl > http/preseed-uefi.cfg

if ! grep -q "reboot_in_progress" http/preseed-uefi.cfg; then
cat <<EOF >> http/preseed-uefi.cfg

# PATCH AUTO
d-i cdrom-detect/eject boolean false
d-i finish-install/reboot_in_progress note
EOF
fi

# --------------------------------------------------------------------------
# Build Packer
# --------------------------------------------------------------------------
echo "========================================"
echo "        LANCEMENT DE PACKER"
echo "========================================"

rm -rf output-debian-uefi

packer build \
 -var "iso_url=$ISO_URL" \
 -var "iso_checksum=$PACKER_ISO_CHECKSUM" \
 -var "ssh_username=$USERNAME" \
 -var "ssh_password=$PASSWORD" \
 -var "ovmf_code=$OVMF_CODE" \
 -var "ovmf_vars=$OVMF_VARS" \
 packer/debian-uefi.pkr.hcl

# --------------------------------------------------------------------------
# Détection automatique de l'image RAW
# --------------------------------------------------------------------------
echo "========================================"
echo "        CONVERSION MENDER"
echo "========================================"

IMG_RAW="output-debian-uefi/packer-debian-uefi"
IMG="$IMG_RAW.img"

if [ ! -f "$IMG" ]; then
    echo "🔄 Conversion RAW → IMG..."
    qemu-img convert -O raw "$IMG_RAW" "$IMG"
fi

echo "🚀 Lancement de mender-convert..."

cd "$HOME/mender-convert" || exit 1

sudo env MENDER_ARTIFACT_NAME="debian-uefi" \
    ./mender-convert \
        --disk-image "$HOME/project-root/$IMG"

echo "🎉 Conversion Mender TERMINÉE avec succès."
echo "📦 Artefacts Mender disponibles dans : ~/mender-convert/deploy/"

