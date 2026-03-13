packer {
  required_plugins {
    qemu = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "ssh_username" { type = string }
variable "ssh_password" { type = string }
variable "ovmf_code"    { type = string }
variable "ovmf_vars"    { type = string }
variable "iso_url" {
  type    = string
  default = ""
}
variable "iso_checksum" {
  type    = string
  default = ""
}

source "qemu" "debian-v2-prod" {
  iso_url          = "output-debian-base/debian-base.img"
  iso_checksum     = "none"
  disk_image       = true
  output_directory = "output-final"
  vm_name          = "cascadya-v2-prod.img"

  disk_interface   = "virtio"
  format           = "raw"
  accelerator      = "none"
  headless         = false
  shutdown_command = "echo '${var.ssh_password}' | sudo -S shutdown -P now"

  efi_boot          = true
  efi_firmware_code = var.ovmf_code
  efi_firmware_vars = var.ovmf_vars

  ssh_username = var.ssh_username
  ssh_password = var.ssh_password
  ssh_timeout  = "20m"

  memory = 2048
  cpus   = 1
}

build {
  sources = ["source.qemu.debian-v2-prod"]

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "apt-get update",
      "echo '>>> Installation des outils systeme du mode installateur...'",
      "apt-get install -y cloud-guest-utils cryptsetup gdisk parted"
    ]
  }

  provisioner "file" {
    source      = "scripts/install-to-disk-v2.sh"
    destination = "/tmp/install-to-disk.sh"
  }

  provisioner "file" {
    source      = "scripts/install-mode.service"
    destination = "/tmp/install-mode.service"
  }

  provisioner "file" {
    source      = "scripts/install-to-disk.env"
    destination = "/tmp/install-to-disk.env"
  }

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Installation du script Zero-Touch...'",
      "mv /tmp/install-to-disk.sh /usr/local/bin/install-to-disk.sh",
      "sed -i 's/\r$//' /usr/local/bin/install-to-disk.sh",
      "chmod +x /usr/local/bin/install-to-disk.sh",
      "mv /tmp/install-mode.service /etc/systemd/system/install-mode.service",
      "mv /tmp/install-to-disk.env /etc/default/install-to-disk",
      "chmod 0644 /etc/default/install-to-disk",
      "systemctl enable install-mode.service"
    ]
  }

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Application du fix graphique...'",
      "sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT=\"quiet nomodeset console=tty0\"/' /etc/default/grub",
      "update-grub"
    ]
  }

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Desactivation Wifi/BT (Mode Industriel)...'",
      "echo 'blacklist iwlwifi' > /etc/modprobe.d/blacklist-iwlwifi.conf",
      "echo 'blacklist btintel' >> /etc/modprobe.d/blacklist-iwlwifi.conf",
      "echo 'blacklist btrtl' >> /etc/modprobe.d/blacklist-iwlwifi.conf",
      "echo '>>> Nettoyage final...'",
      "apt-get autoremove -y",
      "apt-get clean",
      "rm -rf /var/lib/apt/lists/*",
      "rm -f /root/.bash_history"
    ]
  }
}
