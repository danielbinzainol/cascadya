#!/bin/sh
set -eu

LOG_FILE="/run/install-boot-debug.log"

{
    echo "=== Cascadya installer boot debug $(date -Iseconds) ==="
    echo "-- /proc/cmdline"
    cat /proc/cmdline || true
    echo

    echo "-- /etc/fstab"
    cat /etc/fstab || true
    echo

    echo "-- lsblk"
    lsblk -o NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,UUID,MOUNTPOINTS || true
    echo

    echo "-- blkid"
    blkid || true
    echo

    echo "-- boot-efi.mount"
    systemctl cat boot-efi.mount 2>/dev/null || true
    echo

    echo "-- data.mount"
    systemctl cat data.mount 2>/dev/null || true
    echo

    echo "-- mount unit status"
    systemctl status boot-efi.mount data.mount --no-pager 2>/dev/null || true
    echo
} | tee "$LOG_FILE" > /dev/console
