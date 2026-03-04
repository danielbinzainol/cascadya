# --- 1. L'IMAGE DEBIAN (Bookworm 12.13.0 - OLD STABLE) ---
iso_url      = "https://cdimage.debian.org/cdimage/archive/12.13.0/amd64/iso-cd/debian-12.13.0-amd64-netinst.iso"
iso_checksum = "sha256:2b880ffabe36dbe04a662a3125e5ecae4db69d0acce257dd74615bbf165ad76e"

# --- 2. LES IDENTIFIANTS ---
ssh_username = "cascadya"
ssh_password = "admin"

# --- 3. FICHIERS UEFI ---
# Code UEFI 64-bits (Celui-ci existe bien)
ovmf_code    = "C:/Program Files/qemu/share/edk2-x86_64-code.fd"

# CORRECTION : On revient sur la version i386 qui existe sur votre PC
ovmf_vars    = "C:/Program Files/qemu/share/edk2-i386-vars.fd"