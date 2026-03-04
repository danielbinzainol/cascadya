packer {
  required_plugins {
    qemu = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/qemu"
    }
    ansible = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/ansible"
    }
  }
}

variable "ssh_username" { type = string }
variable "ssh_password" { type = string }
variable "ovmf_code"    { type = string }
variable "ovmf_vars"    { type = string }

source "qemu" "debian-final" {
  # --- SOURCE & DESTINATION ---
  iso_url           = "output-debian-base/debian-base.img"
  iso_checksum      = "none"
  disk_image        = true
  output_directory  = "output-final"
  vm_name           = "cascadya-v1.img"
  
  # --- CONFIGURATION VM ---
  disk_interface    = "virtio"
  format            = "raw"
  accelerator       = "none"
  headless          = false
  shutdown_command  = "echo '${var.ssh_password}' | sudo -S shutdown -P now"

  # --- UEFI ---
  efi_boot          = true
  efi_firmware_code = var.ovmf_code
  efi_firmware_vars = var.ovmf_vars

  # --- SSH ---
  ssh_username      = var.ssh_username
  ssh_password      = var.ssh_password
  ssh_timeout       = "20m"

  memory            = 2048
  cpus              = 1
}

build {
  sources = ["source.qemu.debian-final"]

  # --- 1. INSTALLATION DES OUTILS (CRUCIAL) ---
  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Ajout des dépôts non-free...'",
      "sed -i 's/main$/main contrib non-free non-free-firmware/' /etc/apt/sources.list",
      "apt-get update",
      "echo '>>> Installation des outils système...'",
      "apt-get install -y ansible cloud-guest-utils gdisk parted git"
    ]
  }

  # --- 2. PREPARATION HARDENING (NOUVEAU) ---
  # On copie le fichier de dépendances Ansible
  provisioner "file" {
    source      = "ansible/requirements.yml"
    destination = "/tmp/requirements.yml"
  }

  # On installe les rôles de sécurité (DevSec)
  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Installation des rôles Ansible Galaxy...'",
      "ansible-galaxy install -r /tmp/requirements.yml"
    ]
  }

  # --- 3. ANSIBLE (EXECUTION) ---
  provisioner "ansible-local" {
    playbook_file = "ansible/site.yml"
    # IMPORTANT : Permet à Ansible de voir le dossier 'files' (pour l'agent et les certs)
    playbook_dir  = "ansible"
  }

  # --- 4. SCRIPTS ZERO TOUCH ---
  provisioner "file" {
    source      = "scripts/install-to-disk.sh"
    destination = "/tmp/install-to-disk.sh"
  }

  provisioner "file" {
    source      = "scripts/install-mode.service"
    destination = "/tmp/install-mode.service"
  }

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Installation du script Zero-Touch...'",
      "mv /tmp/install-to-disk.sh /usr/local/bin/install-to-disk.sh",
      
      # --- SECURITE ANTI-WINDOWS (CRITICAL FIX) ---
      "sed -i 's/\r$//' /usr/local/bin/install-to-disk.sh",
      
      "chmod +x /usr/local/bin/install-to-disk.sh",
      "mv /tmp/install-mode.service /etc/systemd/system/install-mode.service",
      "systemctl enable install-mode.service"
    ]
  }

  # --- 5. FIX GRAPHIQUE (HDMI) ---
  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Application du fix graphique...'",
      "sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT=\"quiet nomodeset console=tty0\"/' /etc/default/grub",
      "update-grub"
    ]
  }

  # --- 6. NETTOYAGE FINAL & BLACKLIST WIFI ---
  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Désactivation Wifi/BT (Mode Industriel)...'",
      "echo 'blacklist iwlwifi' > /etc/modprobe.d/blacklist-iwlwifi.conf",
      "echo 'blacklist btintel' >> /etc/modprobe.d/blacklist-iwlwifi.conf",
      "echo 'blacklist btrtl' >> /etc/modprobe.d/blacklist-iwlwifi.conf",
      
      "echo '>>> Nettoyage final...'",
      "apt-get remove -y ansible git",
      "apt-get autoremove -y",
      "apt-get clean",
      "rm -rf /var/lib/apt/lists/*",
      "rm -f /root/.bash_history",
      "rm -f /tmp/requirements.yml"
    ]
  }
}