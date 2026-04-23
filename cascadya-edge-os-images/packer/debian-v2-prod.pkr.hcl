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
variable "installer_base_image_path" {
  type    = string
  default = "output-debian-base/debian-base.img"
}
variable "payload_image_path" {
  type    = string
  default = "output-mender-base/cascadya-mender-base.img.xz"
}

source "qemu" "debian-v2-prod" {
  iso_url          = var.installer_base_image_path
  iso_checksum     = "none"
  disk_image       = true
  output_directory = "output-final"
  vm_name          = "cascadya-v2-prod.img"

  disk_interface   = "ide"
  disk_size        = "25G"
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
      "apt-get install -y cloud-guest-utils cryptsetup gdisk parted xz-utils"
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

  provisioner "file" {
    source      = "scripts/install-boot-debug.sh"
    destination = "/tmp/install-boot-debug.sh"
  }

  provisioner "file" {
    source      = "scripts/install-boot-debug.service"
    destination = "/tmp/install-boot-debug.service"
  }

  provisioner "file" {
    source      = var.payload_image_path
    destination = "/tmp/cascadya-mender-base.img.xz"
  }

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Installation du script Zero-Touch...'",
      "mkdir -p /opt/cascadya/payload",
      "mv /tmp/install-to-disk.sh /usr/local/bin/install-to-disk.sh",
      "sed -i 's/\r$//' /usr/local/bin/install-to-disk.sh",
      "chmod +x /usr/local/bin/install-to-disk.sh",
      "mv /tmp/install-mode.service /etc/systemd/system/install-mode.service",
      "mv /tmp/install-to-disk.env /etc/default/install-to-disk",
      "chmod 0644 /etc/default/install-to-disk",
      "mv /tmp/install-boot-debug.sh /usr/local/bin/install-boot-debug.sh",
      "sed -i 's/\r$//' /usr/local/bin/install-boot-debug.sh",
      "chmod +x /usr/local/bin/install-boot-debug.sh",
      "mv /tmp/install-boot-debug.service /etc/systemd/system/install-boot-debug.service",
      "mv /tmp/cascadya-mender-base.img.xz /opt/cascadya/payload/cascadya-mender-base.img.xz",
      "chmod 0644 /opt/cascadya/payload/cascadya-mender-base.img.xz",
      "systemctl enable install-mode.service",
      "systemctl enable install-boot-debug.service"
    ]
  }

  provisioner "shell" {
    execute_command = "echo '{{.SSHPassword}}' | sudo -S -E sh -c '{{ .Path }}'"
    inline = [
      "echo '>>> Relaxation des montages fstab pour le mode installateur USB...'",
      "awk 'BEGIN{OFS=\"\\t\"} $2==\"/boot/efi\" { $4=\"noauto,nofail,x-systemd.automount,x-systemd.device-timeout=1s,defaults,sync\" } $2==\"/data\" { $4=\"noauto,nofail,x-systemd.automount,x-systemd.device-timeout=1s,defaults\" } { print }' /etc/fstab > /etc/fstab.tmp",
      "mv /etc/fstab.tmp /etc/fstab"
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
      "while pgrep -x apt >/dev/null || pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null; do echo 'Waiting for apt/dpkg lock release...'; sleep 2; done",
      "apt-get autoremove -y",
      "apt-get clean",
      "rm -rf /var/lib/apt/lists/*",
      "rm -f /root/.bash_history"
    ]
  }
}
