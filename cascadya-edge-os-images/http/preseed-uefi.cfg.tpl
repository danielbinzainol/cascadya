#_preseed_V4_Two_Phase_Default
d-i debian-installer/locale string en_US.UTF-8
d-i keyboard-configuration/xkb-keymap select us
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string __HOSTNAME__
d-i mirror/country string manual
d-i mirror/http/hostname string deb.debian.org
d-i mirror/http/directory string /debian
d-i mirror/http/proxy string

# --- Utilisateur ---
d-i passwd/root-login boolean false
d-i passwd/user-fullname string Cascadya Admin
d-i passwd/username string __USERNAME__
d-i passwd/user-password password __PASSWORD__
d-i passwd/user-password-again password __PASSWORD__
d-i user-setup/allow-password-weak boolean true

# --- Partitionnement Expert UEFI ---
d-i partman-auto/method string regular
d-i partman-auto/disk string /dev/vda
# Réponse alignée avec le preseed stable validé en V3.
d-i partman-basicfilesystems/no_swap boolean false
d-i partman-auto/expert_recipe string \
      mender-ab-data :: \
              300 300 300 fat32 \
                      $primary{ } \
                      $bootable{ } \
                      method{ efi } \
                      format{ } \
              . \
              10240 10240 10240 ext4 \
                      $primary{ } \
                      method{ format } \
                      format{ } \
                      use_filesystem{ } \
                      filesystem{ ext4 } \
                      mountpoint{ / } \
              . \
              10240 10240 10240 ext4 \
                      $primary{ } \
                      method{ format } \
                      format{ } \
                      use_filesystem{ } \
                      filesystem{ ext4 } \
                      mountpoint{ /srv/rootfs-b } \
              . \
              1024 4096 -1 ext4 \
                      $primary{ } \
                      method{ format } \
                      format{ } \
                      use_filesystem{ } \
                      filesystem{ ext4 } \
                      mountpoint{ /data } \
              .

d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# --- Bootloader ---
d-i grub-installer/only_debian boolean true
d-i grub-installer/with_other_os boolean true
d-i grub-installer/force-efi-extra-removable boolean true

# --- Paquets ---
tasksel tasksel/first multiselect standard, ssh-server
d-i pkgsel/include string sudo python3 python3-apt curl grub-efi-amd64

# --- Late Command (Phase 1 only) ---
d-i preseed/late_command string in-target mkdir -p /home/__USERNAME__/.ssh; in-target chown -R 1000:1000 /home/__USERNAME__/.ssh; in-target chmod 700 /home/__USERNAME__/.ssh; in-target sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config; in-target usermod -aG sudo __USERNAME__; in-target /bin/sh -c "echo '__USERNAME__ ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/packer"
