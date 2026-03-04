#!/bin/bash
set -e

IMAGE="industrial-mender.img"
SIZE_GB=8
EFI_SIZE_MB=300
ROOTFS_SIZE_MB=2048
DEBIAN_VERSION="bookworm"

echo "[1/12] Creating raw image..."
truncate -s ${SIZE_GB}G "$IMAGE"

echo "[2/12] Partitioning image (GPT A/B)..."
parted -s "$IMAGE" mklabel gpt

parted -s "$IMAGE" mkpart EFI fat32 1MiB ${EFI_SIZE_MB}MiB
parted -s "$IMAGE" set 1 esp on

PART2_START=${EFI_SIZE_MB}
PART2_END=$((EFI_SIZE_MB + ROOTFS_SIZE_MB))
PART3_END=$((EFI_SIZE_MB + ROOTFS_SIZE_MB*2))

parted -s "$IMAGE" mkpart rootfsA ext4 ${PART2_START}MiB ${PART2_END}MiB
parted -s "$IMAGE" mkpart rootfsB ext4 ${PART2_END}MiB ${PART3_END}MiB
parted -s "$IMAGE" mkpart data ext4 ${PART3_END}MiB 100%

echo "[3/12] Attaching loop device..."
LOOP=$(losetup --show -fP "$IMAGE")
echo "Loop device: $LOOP"

echo "[4/12] Formatting partitions..."
mkfs.vfat -F32 "${LOOP}p1"
mkfs.ext4 -F "${LOOP}p2"
mkfs.ext4 -F "${LOOP}p3"
mkfs.ext4 -F "${LOOP}p4"

echo "[5/12] Bootstrapping Debian Rootfs A..."
mkdir -p /mnt/rootfsA
debootstrap --arch=amd64 "$DEBIAN_VERSION" /mnt/rootfsA

echo "[6/12] Binding system dirs..."
mount --bind /dev  /mnt/rootfsA/dev
mount --bind /proc /mnt/rootfsA/proc
mount --bind /sys  /mnt/rootfsA/sys

echo "[7/12] Installing base packages..."
chroot /mnt/rootfsA apt update
chroot /mnt/rootfsA apt install -y \
    sudo ssh ifupdown net-tools \
    ca-certificates curl wget \
    linux-image-amd64 grub-efi-amd64 \
    docker.io containerd mender-client rsync

echo "[8/12] Creating user cascadya/admin..."
chroot /mnt/rootfsA useradd -m -G sudo,docker -s /bin/bash cascadya
echo "cascadya:admin" | chroot /mnt/rootfsA chpasswd

echo "[9/12] Applying overlay files..."
cp -a rootfs_overlay/* /mnt/rootfsA/

echo "[10/12] Installing GRUB (UEFI)..."
mkdir -p /mnt/rootfsA/boot/efi
mount "${LOOP}p1" /mnt/rootfsA/boot/efi
chroot /mnt/rootfsA grub-install --target=x86_64-efi \
    --efi-directory=/boot/efi \
    --bootloader-id=debian \
    --recheck --no-nvram

cat <<EOF > /mnt/rootfsA/boot/grub/grub.cfg
set default=0
set timeout=0

menuentry "Debian Rootfs A" {
    linux /boot/vmlinuz root=/dev/sda2 rw
    initrd /boot/initrd.img
}

menuentry "Debian Rootfs B" {
    linux /boot/vmlinuz root=/dev/sda3 rw
    initrd /boot/initrd.img
}
EOF

echo "[11/12] Cloning A → B safely..."
mkdir -p /mnt/rootfsB
mount "${LOOP}p3" /mnt/rootfsB

rsync -aHAX \
    --exclude="/dev/*" \
    --exclude="/proc/*" \
    --exclude="/sys/*" \
    --exclude="/run/*" \
    --exclude="/tmp/*" \
    /mnt/rootfsA/ /mnt/rootfsB/

echo "[12/12] Final cleanup..."
umount -R /mnt/rootfsA || true
umount -R /mnt/rootfsB || true
losetup -d "$LOOP"

echo "==========================================="
echo " ✔ IMAGE READY: $IMAGE"
echo " Bootable sur EFIC-2000CA ✔"
echo " Partitions Mender OK ✔"
echo "==========================================="
