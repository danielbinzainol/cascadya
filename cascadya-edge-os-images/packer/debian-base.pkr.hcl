packer {
  required_plugins {
    qemu = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "iso_url"      { type = string }
variable "iso_checksum" { type = string }
variable "ssh_username" { type = string }
variable "ssh_password" { type = string }
variable "ovmf_code"    { type = string }
variable "ovmf_vars"    { type = string }
variable "preseed_filename" {
  type    = string
  default = "preseed-uefi-mender-base.cfg"
}

source "qemu" "debian-base" {
  # --- SOURCE : ISO INTERNET ---
  iso_url      = var.iso_url
  iso_checksum = var.iso_checksum

  # --- SORTIE INTERMÉDIAIRE ---
  output_directory = "output-debian-base"
  vm_name          = "debian-base.img"
  
  shutdown_command = "echo '${var.ssh_password}' | sudo -S shutdown -P now"
  disk_size        = "24G"
  format           = "raw"
  accelerator      = "whpx"
  headless         = false

  efi_boot          = true
  efi_firmware_code = var.ovmf_code
  efi_firmware_vars = var.ovmf_vars

  ssh_username = var.ssh_username
  ssh_password = var.ssh_password
  
  # --- TIMEOUT CRITIQUE POUR SANS ACCÉLÉRATION ---
  # On laisse 1h30 à Debian pour s'installer tranquillement
  ssh_timeout  = "1h30m"

  # --- CONFIG STABLE ---
  # 1 CPU pour éviter le crash "RCU Stall"
  # 4GB RAM pour compenser la lenteur CPU
  memory = 4096
  cpus   = 1

  boot_wait = "20s"
  boot_command = [
    "<wait><wait><wait>",
    "c",
    "<wait><wait>",
    "linux /install.amd/vmlinuz ",
    "auto=true ",
    "priority=critical ",
    "url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/${var.preseed_filename} ",
    "domain=local ",
    "hostname=cascadya ",
    "--- <enter>",
    "<wait><wait>",
    "initrd /install.amd/initrd.gz<enter>",
    "<wait><wait>",
    "boot<enter>"
  ]

  http_directory = "http"
}

build {
  sources = ["source.qemu.debian-base"]

  # AUCUN PROVISIONER ICI
  # Juste l'installation de l'OS.
}
