#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
INSTALL_LOG="/var/log/install-to-disk.log"

mkdir -p "$(dirname "$INSTALL_LOG")"
exec > >(tee -a "$INSTALL_LOG") 2>&1

log() { echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
success() { echo -e "${GREEN}[SUCCESS] $1${NC}"; }
error() { echo -e "${RED}[FATAL] $1${NC}"; exit 1; }

ZERO_TOUCH_ENABLE_LUKS="${ZERO_TOUCH_ENABLE_LUKS:-false}"
DATA_LUKS_PASSPHRASE="${DATA_LUKS_PASSPHRASE:-admin}"
TARGET_CRYPTTAB_NAME="${TARGET_CRYPTTAB_NAME:-cascadya_data}"
PAYLOAD_IMAGE_PATH="${PAYLOAD_IMAGE_PATH:-}"
PAYLOAD_IMAGE_COMPRESSION="${PAYLOAD_IMAGE_COMPRESSION:-none}"
MENDER_DEVICE_TYPE="${MENDER_DEVICE_TYPE:-cascadya-ipc}"
LUKS_MAPPER_NAME="cascadya_data_target"
TARGET_MAPPER_PATH="/dev/mapper/${LUKS_MAPPER_NAME}"
MENDER_STATE_BACKUP_DIR="/tmp/cascadya-mender-data"
TARGET_ROOT_MOUNT="/mnt/target"
TARGET_DATA_MOUNT="${TARGET_ROOT_MOUNT}/data"
SOURCE_DATA_MOUNT="/mnt/source-data"

dump_disk_state() {
    local disk="$1"

    warn "Block layout snapshot for ${disk}:"
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS "$disk" || true

    warn "GPT snapshot for ${disk}:"
    sgdisk -p "$disk" || true
}

fatal_with_disk_state() {
    local message="$1"
    local disk="${2:-}"

    echo -e "${RED}[FATAL] ${message}${NC}"
    if [ -n "$disk" ]; then
        dump_disk_state "$disk"
    fi
    exit 1
}

get_source_disk() {
    local root_source
    local parent_name

    root_source="$(findmnt -n -o SOURCE / || true)"
    [ -n "$root_source" ] || error "Unable to determine the running system root device."

    parent_name="$(lsblk -no PKNAME "$root_source" 2>/dev/null | head -n1)"
    [ -n "$parent_name" ] || error "Unable to determine the source disk from $root_source."

    echo "/dev/${parent_name}"
}

get_target_disk() {
    local source_disk="$1"
    local target_disk

    target_disk="$(
        lsblk -dpno NAME,TYPE,RM,TRAN | awk -v src="$source_disk" '
            $2 == "disk" && $1 != src && $3 == "0" { print $1; exit }
        '
    )"

    if [ -z "$target_disk" ]; then
        target_disk="$(
            lsblk -dpno NAME,TYPE | awk -v src="$source_disk" '
                $2 == "disk" && $1 != src { print $1; exit }
            '
        )"
    fi

    [ -n "$target_disk" ] || error "Unable to determine the internal target disk."
    echo "$target_disk"
}

partition_path() {
    local disk="$1"
    local number="$2"

    if [[ "$disk" =~ [0-9]$ ]]; then
        echo "${disk}p${number}"
    else
        echo "${disk}${number}"
    fi
}

is_truthy() {
    case "${1,,}" in
        1|true|yes|on)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

refresh_partition_view() {
    local disk="$1"

    partprobe "$disk"
    udevadm settle || true
    partx -u "$disk" >/dev/null 2>&1 || true
    udevadm settle || true
    sleep 1
}

wait_for_block_device() {
    local device="$1"
    local attempts="${2:-10}"
    local delay_seconds="${3:-1}"
    local attempt

    for attempt in $(seq 1 "$attempts"); do
        if [ -b "$device" ]; then
            return 0
        fi

        udevadm settle || true
        sleep "$delay_seconds"
    done

    return 1
}

install_payload_image() {
    local target_disk="$1"

    [ -n "$PAYLOAD_IMAGE_PATH" ] || error "PAYLOAD_IMAGE_PATH is empty."
    [ -f "$PAYLOAD_IMAGE_PATH" ] || error "Target image payload not found at ${PAYLOAD_IMAGE_PATH}."

    case "${PAYLOAD_IMAGE_COMPRESSION,,}" in
        ""|none)
            dd if="$PAYLOAD_IMAGE_PATH" of="$target_disk" bs=4M status=progress conv=fsync oflag=sync
            ;;
        xz)
            xz -dc "$PAYLOAD_IMAGE_PATH" | dd of="$target_disk" bs=4M status=progress conv=fsync oflag=sync
            ;;
        *)
            error "Unsupported PAYLOAD_IMAGE_COMPRESSION='${PAYLOAD_IMAGE_COMPRESSION}'."
            ;;
    esac

    sync
}

backup_target_mender_state() {
    local data_fstype

    rm -rf "$MENDER_STATE_BACKUP_DIR"
    mkdir -p "$MENDER_STATE_BACKUP_DIR"
    mkdir -p "$SOURCE_DATA_MOUNT"

    data_fstype="$(blkid -s TYPE -o value "$DATA_PART" 2>/dev/null || true)"
    if [ -z "$data_fstype" ]; then
        warn "Could not determine the filesystem type of ${DATA_PART}; skipping Mender state backup."
        return 0
    fi

    if [ "$data_fstype" = "crypto_LUKS" ]; then
        warn "${DATA_PART} is already encrypted; skipping Mender state backup from the source payload."
        return 0
    fi

    if ! mount -o ro "$DATA_PART" "$SOURCE_DATA_MOUNT"; then
        warn "Could not mount ${DATA_PART} read-only to back up Mender state."
        return 0
    fi

    if [ -d "${SOURCE_DATA_MOUNT}/mender" ]; then
        cp -a "${SOURCE_DATA_MOUNT}/mender/." "$MENDER_STATE_BACKUP_DIR/"
        success "Backed up the embedded Mender persistent state from ${DATA_PART}."
    else
        warn "No /mender directory was found on ${DATA_PART}; continuing with generated defaults."
    fi

    umount "$SOURCE_DATA_MOUNT" || true
}

mount_target_data_volume() {
    mkdir -p "$TARGET_DATA_MOUNT"

    if [ "$TARGET_DATA_MODE" = "luks" ]; then
        printf '%s' "$DATA_LUKS_PASSPHRASE" | cryptsetup open "$DATA_PART" "$LUKS_MAPPER_NAME" --key-file=- || fatal_with_disk_state \
            "cryptsetup could not reopen the LUKS target on ${DATA_PART} for finalization." \
            "$TARGET_DISK"
        wait_for_block_device "$TARGET_MAPPER_PATH" 10 1 || fatal_with_disk_state \
            "Expected mapper ${TARGET_MAPPER_PATH} is missing during finalization." \
            "$TARGET_DISK"
        mount "$TARGET_MAPPER_PATH" "$TARGET_DATA_MOUNT"
    else
        mount "$DATA_PART" "$TARGET_DATA_MOUNT"
    fi
}

unmount_target_data_volume() {
    umount "$TARGET_DATA_MOUNT" 2>/dev/null || true

    if [ "$TARGET_DATA_MODE" = "luks" ] && cryptsetup status "$LUKS_MAPPER_NAME" >/dev/null 2>&1; then
        cryptsetup close "$LUKS_MAPPER_NAME" || true
    fi
}

restore_target_mender_state() {
    mkdir -p "${TARGET_DATA_MOUNT}/mender"

    if [ -d "$MENDER_STATE_BACKUP_DIR" ] && [ -n "$(ls -A "$MENDER_STATE_BACKUP_DIR" 2>/dev/null)" ]; then
        cp -a "${MENDER_STATE_BACKUP_DIR}/." "${TARGET_DATA_MOUNT}/mender/"
        success "Restored the embedded Mender persistent state onto the target /data partition."
    fi

    if [ ! -f "${TARGET_DATA_MOUNT}/mender/device_type" ]; then
        printf 'device_type=%s\n' "$MENDER_DEVICE_TYPE" > "${TARGET_DATA_MOUNT}/mender/device_type"
        chmod 0444 "${TARGET_DATA_MOUNT}/mender/device_type"
    fi

    if [ ! -f "${TARGET_DATA_MOUNT}/mender/mender.conf" ]; then
        cat > "${TARGET_DATA_MOUNT}/mender/mender.conf" <<EOF
{
  "RootfsPartA": "$(partition_path "$TARGET_DISK" 2)",
  "RootfsPartB": "$(partition_path "$TARGET_DISK" 3)"
}
EOF
        chmod 0600 "${TARGET_DATA_MOUNT}/mender/mender.conf"
    fi

    chown -R root:root "${TARGET_DATA_MOUNT}/mender"
}

ensure_target_root_slot_layout() {
    local mount_root="$1"

    mkdir -p "${mount_root}/var/lib"

    if [ ! -L "${mount_root}/var/lib/mender" ]; then
        rm -rf "${mount_root}/var/lib/mender"
        ln -s /data/mender "${mount_root}/var/lib/mender"
    fi
}

disable_target_mender_managed_services() {
    local mount_root="$1"

    rm -f "${mount_root}/etc/systemd/system/multi-user.target.wants/mender-updated.service"
    rm -f "${mount_root}/etc/systemd/system/multi-user.target.wants/mender-authd.service"
    rm -f "${mount_root}/etc/systemd/system/multi-user.target.wants/mender-client.service"
}

finalize_target_root_slot() {
    local root_part="$1"

    [ -b "$root_part" ] || return 0

    mount "$root_part" "$TARGET_ROOT_MOUNT"

    rm -f "${TARGET_ROOT_MOUNT}/etc/systemd/system/install-mode.service"
    rm -f "${TARGET_ROOT_MOUNT}/etc/systemd/system/multi-user.target.wants/install-mode.service"
    rm -f "${TARGET_ROOT_MOUNT}/etc/systemd/system/install-boot-debug.service"
    rm -f "${TARGET_ROOT_MOUNT}/etc/systemd/system/local-fs.target.wants/install-boot-debug.service"
    rm -f "${TARGET_ROOT_MOUNT}/usr/local/bin/install-to-disk.sh"
    rm -f "${TARGET_ROOT_MOUNT}/usr/local/bin/install-boot-debug.sh"
    rm -f "${TARGET_ROOT_MOUNT}/etc/default/install-to-disk"

    if [ "$TARGET_DATA_MODE" = "luks" ]; then
        configure_target_luks_mount "$TARGET_ROOT_MOUNT"
    else
        configure_target_plain_data_mount "$TARGET_ROOT_MOUNT"
    fi

    ensure_target_root_slot_layout "$TARGET_ROOT_MOUNT"
    disable_target_mender_managed_services "$TARGET_ROOT_MOUNT"

    rmdir "${TARGET_ROOT_MOUNT}/srv/rootfs-b" || true

    truncate -s 0 "${TARGET_ROOT_MOUNT}/var/log/syslog" || true
    truncate -s 0 "${TARGET_ROOT_MOUNT}/var/log/kern.log" || true

    umount "$TARGET_ROOT_MOUNT"
}

assert_v2_source_layout() {
    local source_disk="$1"
    local source_data_part
    local source_partition_count

    source_data_part="$(partition_path "$source_disk" 4)"
    source_partition_count="$(
        lsblk -lnpo TYPE "$source_disk" | awk '$1 == "part" { count++ } END { print count + 0 }'
    )"

    if [ "$source_partition_count" -lt 4 ] || [ ! -b "$source_data_part" ]; then
        fatal_with_disk_state \
            "Source media ${source_disk} does not expose the V2 layout (expected partition 4). Rebuild and reflash the USB image." \
            "$source_disk"
    fi
}

copy_size_blocks() {
    local source_disk="$1"
    local last_sector
    local sector_size
    local last_byte
    local block_size=$((4 * 1024 * 1024))

    last_sector="$(parted -sm "$source_disk" unit s print | awk -F: '$1 ~ /^[0-9]+$/ { gsub("s", "", $3); last=$3 } END { print last }')"
    sector_size="$(blockdev --getss "$source_disk")"
    last_byte=$(( (last_sector + 1) * sector_size ))

    echo $(( (last_byte + block_size - 1) / block_size ))
}

configure_target_plain_data_mount() {
    local mount_root="$1"
    local data_uuid

    data_uuid="$(blkid -s UUID -o value "$DATA_PART")"

    if [ -f "${mount_root}/etc/fstab" ]; then
        sed -i '\| /srv/rootfs-b |d' "${mount_root}/etc/fstab"
        sed -i '\| /data |d' "${mount_root}/etc/fstab"
    fi

    if [ -f "${mount_root}/etc/crypttab" ]; then
        sed -i "/^${TARGET_CRYPTTAB_NAME}[[:space:]]/d" "${mount_root}/etc/crypttab"
    fi

    printf 'UUID=%s /data ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2\n' "$data_uuid" >> "${mount_root}/etc/fstab"
}

configure_target_luks_mount() {
    local mount_root="$1"
    local luks_uuid

    luks_uuid="$(blkid -s UUID -o value "$DATA_PART")"

    if [ -f "${mount_root}/etc/fstab" ]; then
        sed -i '\| /srv/rootfs-b |d' "${mount_root}/etc/fstab"
        sed -i '\| /data |d' "${mount_root}/etc/fstab"
    fi

    touch "${mount_root}/etc/crypttab"
    sed -i "/^${TARGET_CRYPTTAB_NAME}[[:space:]]/d" "${mount_root}/etc/crypttab"

    printf '%s UUID=%s none luks,nofail,tpm2-device=auto,tpm2-pcrs=7\n' "$TARGET_CRYPTTAB_NAME" "$luks_uuid" >> "${mount_root}/etc/crypttab"
    printf '/dev/mapper/%s /data ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2\n' "$TARGET_CRYPTTAB_NAME" >> "${mount_root}/etc/fstab"
}

resize_plain_data_volume() {
    local data_fstype

    data_fstype="$(blkid -s TYPE -o value "$DATA_PART" || true)"
    [ "$data_fstype" = "ext4" ] || fatal_with_disk_state \
        "Expected plain ext4 on ${DATA_PART}, found '${data_fstype:-unknown}'." \
        "$TARGET_DISK"

    e2fsck -fp "$DATA_PART" || true
    resize2fs "$DATA_PART"
}

ensure_luks_data_volume() {
    if cryptsetup isLuks "$DATA_PART"; then
        log "Detected an existing LUKS container on ${DATA_PART}."
        printf '%s' "$DATA_LUKS_PASSPHRASE" | cryptsetup open "$DATA_PART" "$LUKS_MAPPER_NAME" --key-file=- || fatal_with_disk_state \
            "cryptsetup could not open the LUKS volume on ${DATA_PART}." \
            "$TARGET_DISK"
        cryptsetup resize "$LUKS_MAPPER_NAME"
    else
        log "Creating a fresh LUKS container on ${DATA_PART}."
        printf '%s' "$DATA_LUKS_PASSPHRASE" | cryptsetup luksFormat --batch-mode "$DATA_PART" --key-file=- || fatal_with_disk_state \
            "cryptsetup could not create the LUKS container on ${DATA_PART}." \
            "$TARGET_DISK"
        printf '%s' "$DATA_LUKS_PASSPHRASE" | cryptsetup open "$DATA_PART" "$LUKS_MAPPER_NAME" --key-file=- || fatal_with_disk_state \
            "cryptsetup could not open the freshly created LUKS volume on ${DATA_PART}." \
            "$TARGET_DISK"
        mkfs.ext4 -F "$TARGET_MAPPER_PATH"
    fi

    wait_for_block_device "$TARGET_MAPPER_PATH" 10 1 || fatal_with_disk_state \
        "Expected mapper ${TARGET_MAPPER_PATH} is missing after cryptsetup open." \
        "$TARGET_DISK"

    e2fsck -fp "$TARGET_MAPPER_PATH" || true
    resize2fs "$TARGET_MAPPER_PATH"
    cryptsetup close "$LUKS_MAPPER_NAME"
}

trap 'fatal_with_disk_state "Unexpected error at line ${LINENO}." "${TARGET_DISK:-}"' ERR

SOURCE_DISK="$(get_source_disk)"
TARGET_DISK="$(get_target_disk "$SOURCE_DISK")"
ROOT_PART="$(partition_path "$TARGET_DISK" 2)"
DATA_PART="$(partition_path "$TARGET_DISK" 4)"

echo "==================================================="
echo "   CASCADYA EDGE OS - AUTO INSTALLER V5"
echo "==================================================="
log "Installer log file: ${INSTALL_LOG}"
log "Installer media disk: ${SOURCE_DISK}"
log "Target disk: ${TARGET_DISK}"
log "Target /data LUKS mode: ${ZERO_TOUCH_ENABLE_LUKS}"
if [ -n "$PAYLOAD_IMAGE_PATH" ]; then
    log "Embedded target payload: ${PAYLOAD_IMAGE_PATH} (${PAYLOAD_IMAGE_COMPRESSION})"
fi

[ -b "$SOURCE_DISK" ] || error "Source disk $SOURCE_DISK not found."
[ -b "$TARGET_DISK" ] || error "Target disk $TARGET_DISK not found."

warn "The disk ${TARGET_DISK} will be fully overwritten."
echo -n "Starting in "
for i in {5..1}; do echo -ne "$i... "; sleep 1; done
echo "GO!"

log "Cleaning previous signatures..."
wipefs -a "$TARGET_DISK" --force || true

if [ -n "$PAYLOAD_IMAGE_PATH" ]; then
    log "Writing the embedded Mender target image to ${TARGET_DISK}..."
    install_payload_image "$TARGET_DISK"
else
    DD_COUNT="$(copy_size_blocks "$SOURCE_DISK")"
    assert_v2_source_layout "$SOURCE_DISK"
    log "Cloning the installer image footprint..."
    dd if="$SOURCE_DISK" of="$TARGET_DISK" bs=4M count="$DD_COUNT" status=progress conv=fsync oflag=sync
    sync
fi

log "Repairing GPT headers..."
sgdisk -e "$TARGET_DISK" || fatal_with_disk_state "sgdisk failed to relocate GPT headers on ${TARGET_DISK}." "$TARGET_DISK"
refresh_partition_view "$TARGET_DISK"

log "Checking expected data partition ${DATA_PART}..."
wait_for_block_device "$DATA_PART" 10 1 || fatal_with_disk_state \
    "Expected target partition ${DATA_PART} is missing. The source media probably does not contain the V2 4-partition layout." \
    "$TARGET_DISK"

log "Backing up the Mender persistent data prepared in the target image."
backup_target_mender_state

log "Expanding data partition..."
growpart "$TARGET_DISK" 4 || fatal_with_disk_state \
    "growpart failed while expanding partition 4 on ${TARGET_DISK}." \
    "$TARGET_DISK"
refresh_partition_view "$TARGET_DISK"
wait_for_block_device "$DATA_PART" 10 1 || fatal_with_disk_state \
    "Partition ${DATA_PART} disappeared after growpart/partprobe." \
    "$TARGET_DISK"

TARGET_DATA_MODE="plain"

if is_truthy "$ZERO_TOUCH_ENABLE_LUKS"; then
    TARGET_DATA_MODE="luks"
    log "Applying LUKS to the target /data partition."
    ensure_luks_data_volume
elif cryptsetup isLuks "$DATA_PART"; then
    TARGET_DATA_MODE="luks"
    warn "Source image already contains a LUKS /data layout. Preserving the encrypted target volume."
    ensure_luks_data_volume
else
    log "Keeping /data as a plain ext4 filesystem on the target."
    resize_plain_data_volume
fi

log "Disarming installer on the cloned SSD..."
mkdir -p "$TARGET_ROOT_MOUNT"
mount_target_data_volume

restore_target_mender_state
finalize_target_root_slot "$(partition_path "$TARGET_DISK" 2)"
finalize_target_root_slot "$(partition_path "$TARGET_DISK" 3)"

unmount_target_data_volume
sync

success "Installation completed successfully."
warn "Remove the USB media now."
warn "Automatic power off in 10 seconds..."
sleep 10
poweroff
