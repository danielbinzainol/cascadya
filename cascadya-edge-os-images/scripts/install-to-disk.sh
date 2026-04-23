#!/bin/bash
set -e

# --- COULEURS ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[ATTENTION] $1${NC}"; }
success() { echo -e "${GREEN}[SUCCÈS] $1${NC}"; }
error() { echo -e "${RED}[ERREUR FATALE] $1${NC}"; exit 1; }

# --- CONFIGURATION MATÉRIELLE ---
SOURCE_DISK="/dev/sdb"
TARGET_DISK="/dev/sda"

echo "==================================================="
echo "   🚀 CASCADYA EDGE OS - AUTO INSTALLER V3.0"
echo "==================================================="

# Vérifications de base
if [ ! -b "$TARGET_DISK" ]; then error "Cible $TARGET_DISK introuvable !"; fi
if [ ! -b "$SOURCE_DISK" ]; then error "Source $SOURCE_DISK introuvable !"; fi

# Compte à rebours
warn "Le disque $TARGET_DISK va être TOTALEMENT EFFACÉ."
echo -n "Démarrage dans "
for i in {5..1}; do echo -ne "$i... "; sleep 1; done
echo "GO !"

# --- 1. NETTOYAGE ---
log "🧹 Nettoyage des signatures..."
wipefs -a "$TARGET_DISK" --force || true

# --- 2. CLONAGE ---
log "💾 Clonage du système (10 Go)..."
# On copie les 10 premiers Go (suffisant pour l'OS de base)
dd if="$SOURCE_DISK" of="$TARGET_DISK" bs=4M count=2500 status=progress conv=fsync oflag=sync

# --- 3. RÉPARATION GPT ---
log "🔧 Réparation de la table GPT..."
sgdisk -e "$TARGET_DISK" > /dev/null 2>&1 || true
partprobe "$TARGET_DISK"
sleep 2

# --- 4. EXTENSION PARTITION ---
log "📏 Agrandissement de la partition..."

# Identification de la partition racine (sda2 ou nvme0n1p2)
if [[ "$TARGET_DISK" =~ [0-9]$ ]]; then
    PART_PREFIX="${TARGET_DISK}p"
else
    PART_PREFIX="${TARGET_DISK}"
fi
ROOT_PART="${PART_PREFIX}2"

# Utilisation de growpart (installé via cloud-guest-utils dans Packer)
growpart "$TARGET_DISK" 2 || warn "Growpart n'a rien fait (déjà max ?)"
partprobe "$TARGET_DISK"
sleep 2

# --- 5. EXTENSION FICHIERS (LE FIX EST ICI) ---
log "🚑 Vérification et Extension du Filesystem..."

# A. On répare d'abord (évite l'erreur resize2fs)
e2fsck -fp "$ROOT_PART" || true

# B. On agrandit maintenant que c'est propre
resize2fs "$ROOT_PART" || error "Échec du resize2fs"

# --- 6. LOBOTOMIE (CRUCIAL) ---
log "🔪 Désarmement de l'installateur sur le SSD..."
# On monte le SSD fraîchement copié pour supprimer le script d'auto-install
# Sinon, il va redémarrer en boucle !
mkdir -p /mnt/target
mount "$ROOT_PART" /mnt/target

rm -f /mnt/target/etc/systemd/system/install-mode.service
rm -f /mnt/target/etc/systemd/system/multi-user.target.wants/install-mode.service
rm -f /mnt/target/usr/local/bin/install-to-disk.sh

# Nettoyage logs pour le client
truncate -s 0 /mnt/target/var/log/syslog
truncate -s 0 /mnt/target/var/log/kern.log

umount /mnt/target
sync

# --- FIN ---
success "✅ INSTALLATION TERMINÉE AVEC SUCCÈS !"
warn "👉 VEUILLEZ RETIRER LA CLÉ USB MAINTENANT."
warn "Extinction automatique dans 10 secondes..."
sleep 10
poweroff