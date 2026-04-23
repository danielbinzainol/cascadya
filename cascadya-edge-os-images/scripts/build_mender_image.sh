#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MENDER_CONVERT_DIR="${REPO_ROOT}/mender-convert"
CONFIG_ENV="${REPO_ROOT}/mender/mender-config.env"
CUSTOM_CONFIG="${REPO_ROOT}/mender/cascadya_x86-64_hdd_config"
DEFAULT_BASE_IMAGE="${REPO_ROOT}/output-debian-base/debian-base.img"
OUTPUT_DIR="${REPO_ROOT}/output-mender-base"

INPUT_IMAGE_DIR="${MENDER_CONVERT_DIR}/input/image"
INPUT_CONFIG_DIR="${MENDER_CONVERT_DIR}/input/config"
OVERLAY_DIR="${MENDER_CONVERT_DIR}/input/rootfs_overlay_cascadya"
CONTAINER_OVERLAY_DIR="input/rootfs_overlay_cascadya"

log() {
    printf '[mender-build] %s\n' "$1"
}

fail() {
    printf '[mender-build] ERROR: %s\n' "$1" >&2
    exit 1
}

normalize_mender_convert_scripts() {
    local script
    while IFS= read -r -d '' script; do
        sed -i 's/\r$//' "$script"
    done < <(
        find "$MENDER_CONVERT_DIR" -type f \
            \( \
                -name '*.sh' -o \
                -name '*.cfg' -o \
                -name '*.conf' -o \
                -name '*_config' -o \
                -path "$MENDER_CONVERT_DIR/configs/*" -o \
                -name 'docker-*' -o \
                -name 'mender-convert*' \
            \) \
            -print0
    )

    for script in \
        "${MENDER_CONVERT_DIR}/docker-build" \
        "${MENDER_CONVERT_DIR}/docker-entrypoint.sh" \
        "${MENDER_CONVERT_DIR}/docker-mender-convert" \
        "${MENDER_CONVERT_DIR}/mender-convert" \
        "${MENDER_CONVERT_DIR}/mender-convert-extract" \
        "${MENDER_CONVERT_DIR}/mender-convert-modify" \
        "${MENDER_CONVERT_DIR}/mender-convert-package"; do
        [ -f "$script" ] || continue
        chmod +x "$script"
    done
}

[ -d "$MENDER_CONVERT_DIR" ] || fail "mender-convert checkout not found at ${MENDER_CONVERT_DIR}"
[ -f "$CONFIG_ENV" ] || fail "Mender config env not found at ${CONFIG_ENV}"
[ -f "$CUSTOM_CONFIG" ] || fail "Custom mender-convert config not found at ${CUSTOM_CONFIG}"

BASE_IMAGE_PATH_OVERRIDE="${BASE_IMAGE_PATH:-}"

# shellcheck disable=SC1090
source "$CONFIG_ENV"

BASE_IMAGE="${BASE_IMAGE_PATH_OVERRIDE:-${BASE_IMAGE_PATH:-${DEFAULT_BASE_IMAGE}}}"
[ -f "$BASE_IMAGE" ] || fail "Base image not found at ${BASE_IMAGE}. Build packer/debian-base.pkr.hcl first."

: "${MENDER_ARTIFACT_NAME:?MENDER_ARTIFACT_NAME must be set in mender-config.env}"
: "${DEPLOY_IMAGE_NAME:?DEPLOY_IMAGE_NAME must be set in mender-config.env}"
: "${MENDER_DEVICE_TYPE:?MENDER_DEVICE_TYPE must be set in mender-config.env}"
: "${MENDER_SERVER_MODE:=standalone}"
: "${MENDER_HOSTED_REGION:=eu}"
: "${PAYLOAD_ARCHIVE_FORMAT:=xz}"

mkdir -p "$OUTPUT_DIR" "$INPUT_IMAGE_DIR" "$INPUT_CONFIG_DIR"
rm -f "${INPUT_IMAGE_DIR}/$(basename "$BASE_IMAGE")"
log "Staging base image from ${BASE_IMAGE}"
cp --sparse=always -f "$BASE_IMAGE" "${INPUT_IMAGE_DIR}/$(basename "$BASE_IMAGE")"

rm -rf "$OVERLAY_DIR"
mkdir -p "$OVERLAY_DIR"
if [ -d "${REPO_ROOT}/mender/rootfs_overlay" ]; then
    cp -a "${REPO_ROOT}/mender/rootfs_overlay/." "$OVERLAY_DIR/"
fi

case "$MENDER_SERVER_MODE" in
    standalone)
        log "Preparing a standalone Mender overlay."
        mkdir -p "${OVERLAY_DIR}/etc/mender"
        cat > "${OVERLAY_DIR}/etc/mender/mender.conf" <<EOF
{
  "HttpsClient": {},
  "Security": {},
  "Connectivity": {},
  "DeviceTypeFile": "/var/lib/mender/device_type",
  "UpdatePollIntervalSeconds": 1800,
  "InventoryPollIntervalSeconds": 28800,
  "RetryPollIntervalSeconds": 300
}
EOF
        ;;
    hosted)
        [ -n "${MENDER_TENANT_TOKEN:-}" ] || fail "MENDER_TENANT_TOKEN is required for hosted mode."
        log "Generating hosted Mender configuration overlay."
        "${MENDER_CONVERT_DIR}/scripts/bootstrap-rootfs-overlay-hosted-server.sh" \
            --output-dir "$OVERLAY_DIR" \
            --region "$MENDER_HOSTED_REGION" \
            --tenant-token "$MENDER_TENANT_TOKEN"
        ;;
    production)
        [ -n "${MENDER_SERVER_URL:-}" ] || fail "MENDER_SERVER_URL is required for production mode."
        log "Generating production Mender configuration overlay."
        if [ -n "${MENDER_SERVER_CERT:-}" ]; then
            "${MENDER_CONVERT_DIR}/scripts/bootstrap-rootfs-overlay-production-server.sh" \
                --output-dir "$OVERLAY_DIR" \
                --server-url "$MENDER_SERVER_URL" \
                --server-cert "$MENDER_SERVER_CERT"
        else
            "${MENDER_CONVERT_DIR}/scripts/bootstrap-rootfs-overlay-production-server.sh" \
                --output-dir "$OVERLAY_DIR" \
                --server-url "$MENDER_SERVER_URL"
        fi
        ;;
    *)
        fail "Unsupported MENDER_SERVER_MODE='${MENDER_SERVER_MODE}'. Expected standalone, hosted or production."
        ;;
esac

cp -f "$CUSTOM_CONFIG" "${INPUT_CONFIG_DIR}/$(basename "$CUSTOM_CONFIG")"
rm -f "${MENDER_CONVERT_DIR}/deploy/${DEPLOY_IMAGE_NAME}.img" "${MENDER_CONVERT_DIR}/deploy/${DEPLOY_IMAGE_NAME}.mender"

normalize_mender_convert_scripts

pushd "$MENDER_CONVERT_DIR" >/dev/null
if ! docker image inspect mender-convert >/dev/null 2>&1; then
    log "Building the mender-convert Docker image."
    ./docker-build
fi

log "Running mender-convert on the validated Debian base image."
MENDER_ARTIFACT_NAME="$MENDER_ARTIFACT_NAME" \
MENDER_DEVICE_TYPE="$MENDER_DEVICE_TYPE" \
MENDER_STORAGE_TOTAL_SIZE_MB="$MENDER_STORAGE_TOTAL_SIZE_MB" \
MENDER_BOOT_PART_SIZE_MB="$MENDER_BOOT_PART_SIZE_MB" \
MENDER_DATA_PART_SIZE_MB="$MENDER_DATA_PART_SIZE_MB" \
IMAGE_ROOTFS_SIZE="$IMAGE_ROOTFS_SIZE" \
IMAGE_ROOTFS_EXTRA_SPACE="${IMAGE_ROOTFS_EXTRA_SPACE:-0}" \
MENDER_ADDON_CONNECT_INSTALL="${MENDER_ADDON_CONNECT_INSTALL:-n}" \
MENDER_ADDON_CONFIGURE_INSTALL="${MENDER_ADDON_CONFIGURE_INSTALL:-n}" \
MENDER_SETUP_INSTALL="${MENDER_SETUP_INSTALL:-auto}" \
MENDER_SNAPSHOT_INSTALL="${MENDER_SNAPSHOT_INSTALL:-auto}" \
DEPLOY_IMAGE_NAME="$DEPLOY_IMAGE_NAME" \
./docker-mender-convert \
    --disk-image "input/image/$(basename "$BASE_IMAGE")" \
    --config "input/config/$(basename "$CUSTOM_CONFIG")" \
    --overlay "$CONTAINER_OVERLAY_DIR"
popd >/dev/null

[ -f "${MENDER_CONVERT_DIR}/deploy/${DEPLOY_IMAGE_NAME}.img" ] || fail "Converted image not found in deploy/${DEPLOY_IMAGE_NAME}.img"
cp -f "${MENDER_CONVERT_DIR}/deploy/${DEPLOY_IMAGE_NAME}.img" "${OUTPUT_DIR}/${DEPLOY_IMAGE_NAME}.img"

case "$PAYLOAD_ARCHIVE_FORMAT" in
    xz)
        log "Compressing the converted disk image payload to ${OUTPUT_DIR}/${DEPLOY_IMAGE_NAME}.img.xz"
        rm -f "${OUTPUT_DIR}/${DEPLOY_IMAGE_NAME}.img.xz"
        xz -T0 -z -f -k "${OUTPUT_DIR}/${DEPLOY_IMAGE_NAME}.img"
        ;;
    none)
        log "Skipping compressed payload generation."
        rm -f "${OUTPUT_DIR}/${DEPLOY_IMAGE_NAME}.img.xz"
        ;;
    *)
        fail "Unsupported PAYLOAD_ARCHIVE_FORMAT='${PAYLOAD_ARCHIVE_FORMAT}'. Expected xz or none."
        ;;
esac

if [ -f "${MENDER_CONVERT_DIR}/deploy/${DEPLOY_IMAGE_NAME}.mender" ]; then
    cp -f "${MENDER_CONVERT_DIR}/deploy/${DEPLOY_IMAGE_NAME}.mender" "${OUTPUT_DIR}/${DEPLOY_IMAGE_NAME}.mender"
fi

log "Mender-converted base image ready in ${OUTPUT_DIR}"
