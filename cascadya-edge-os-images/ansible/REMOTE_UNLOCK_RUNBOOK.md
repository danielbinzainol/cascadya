# Remote Unlock Runbook

This runbook applies the `/data` remote unlock model to already-installed IPCs.
It does not modify Mender, Packer, or the bake pipeline.

## Controller-side prerequisites

Prepare one boot-unlock certificate bundle per host on the Ansible controller:

```text
ansible/.tmp/cascadya-remote-unlock/<inventory_hostname>/ca.crt
ansible/.tmp/cascadya-remote-unlock/<inventory_hostname>/client.crt
ansible/.tmp/cascadya-remote-unlock/<inventory_hostname>/client.key
```

The bundle must be separate from the `edge-agent` certificates stored under `/data`.

## Phase order

Run the phases in this order:

1. `baseline-report.yml`
2. `remote-unlock-bootstrap.yml`
3. `remote-unlock-preflight.yml`
4. ensure WireGuard transport exists and reaches the broker
5. `remote-unlock-validate.yml`
6. `remote-unlock-cutover.yml`
7. Reboot and validate the IPC
8. `remote-unlock-remove-local-tpm.yml`

Do not remove the local TPM token until the network-unlock boot path has already been proven.

## Fresh IPC boot checks before provisioning

If the IPC has just been started or rebooted, confirm the local state before
launching another remote-unlock phase:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
systemctl status wg-quick@wg0 --no-pager
systemctl status cascadya-unlock-data.service --no-pager
sudo mender-update show-artifact
```

If `/data` is not mounted but the host has already been prepared for remote
unlock, bring it back first:

```bash
sudo systemctl status systemd-cryptsetup@cascadya_data.service --no-pager
sudo systemctl start systemd-cryptsetup@cascadya_data.service
sudo mount -a
findmnt /data
```

Only continue with `remote-unlock-preflight.yml`, `remote-unlock-validate.yml`,
or edge-agent validation once `/data` is mounted again.

## Playbooks

### Recommended inventory

Create a small inventory file from [inventory-remote-unlock.ini.example](c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/inventory-remote-unlock.ini.example):

```ini
[cascadya_ipc]
cascadya ansible_host=192.168.50.10 ansible_user=cascadya remote_unlock_management_interface=enp3s0 remote_unlock_uplink_interface=enp2s0 remote_unlock_gateway_ip=192.168.137.1 network_uplink_address=192.168.137.10/24
```

Using a host alias such as `cascadya` is recommended because:

- the certificate bundle path becomes stable
- `remote_unlock_device_id` stays readable
- the controller-side generated files land under `.tmp/cascadya-remote-unlock/cascadya/`

For the current lab topology:

- `ansible_host=192.168.50.10` is the management path over `enp3s0`
- `remote_unlock_uplink_interface=enp2s0` is the Internet/WireGuard path
- `remote_unlock_gateway_ip=192.168.137.1` is the Windows sharing gateway on the uplink path
- `network_uplink_address=192.168.137.10/24` assigns the expected ICS-side IPv4 to the uplink interface
- Ansible should run normally from WSL or a personal laptop through the management link
- do not keep `ANSIBLE_CONFIG=ansible-wsl-ics.cfg` enabled for this mode

### Production router path (for example: Teltonika 5G router)

The remote unlock architecture does not require a direct path from the IPC to the cloud VMs.
It works correctly when the IPC reaches the Internet through an intermediate router such as a
Teltonika 5G device.

What changes in practice:

- `remote_unlock_uplink_interface` must match the IPC NIC physically connected to the router
- `remote_unlock_gateway_ip` must be the router LAN IP seen by the IPC
- `network_uplink_address` should be set only if you want Ansible to enforce a static IPv4 on that NIC
- `network_wireguard_endpoint` must be the public WireGuard server endpoint reachable through the router
- `remote_unlock_broker_url` should preferably target the broker over the WireGuard tunnel, using the broker's private WG IP or private DNS name

Recommended production example:

```ini
[cascadya_ipc]
cascadya ansible_host=192.168.50.10 ansible_user=cascadya remote_unlock_management_interface=enp3s0 remote_unlock_uplink_interface=enp2s0 remote_unlock_gateway_ip=192.168.8.1 remote_unlock_broker_url=https://10.20.0.5:8443 network_uplink_address=192.168.8.10/24 network_wireguard_address=10.30.0.10/32 network_wireguard_private_key=REPLACE_DEVICE_PRIVATE_KEY network_wireguard_peer_public_key=REPLACE_SERVER_PUBLIC_KEY network_wireguard_endpoint=vpn.cascadya.com:51820
```

Notes:

- a Teltonika or other NAT router does not change the trust model
- the IPC only needs outbound connectivity to the WireGuard server
- no inbound port-forwarding toward the IPC is required for the basic client tunnel
- the current gateway-MAC collection remains audit-only; in this topology it would simply record the Teltonika MAC if available
- if the mobile operator or router policy interferes with UDP on the chosen WireGuard port, move the WireGuard endpoint to a port that is allowed in that environment

### Demo path without the router yet

If the Teltonika or production WireGuard path is not configured yet, you can still demonstrate the
unlock flow in a controlled lab mode.

Recommended demo topology:

- keep Ansible over the management link on `enp3s0`
- host the demo broker and Vault on a laptop reachable from the IPC over that same management network
- switch the IPC remote-unlock transport to `direct` for the demo only

In that mode:

- the IPC still uses mTLS and TPM quote generation
- the broker/Vault call path is demonstrated
- WireGuard is intentionally bypassed for the demo
- the final production target remains `remote_unlock_transport_mode=wireguard`

Example inventory line for the demo:

```ini
[cascadya_ipc]
cascadya ansible_host=192.168.50.10 ansible_user=cascadya remote_unlock_transport_mode=direct remote_unlock_management_interface=enp3s0 remote_unlock_broker_url=https://<LAPTOP_MGMT_IP>:8443
```

This is good enough to demonstrate:

- the IPC does not unlock `/data` only with the TPM local state
- the IPC contacts an external broker
- the broker can be backed by Vault
- the unlock decision is released remotely

This is not yet the full production proof for:

- WireGuard transport
- router traversal through Teltonika
- final cloud reachability model

### WSL mode through Windows OpenSSH

If WSL cannot directly reach an IPC on the Windows shared network, use the dedicated Ansible config:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
export ANSIBLE_CONFIG="$PWD/ansible-wsl-ics.cfg"
cp inventory-remote-unlock.ini.example inventory-remote-unlock.ini
ansible -i inventory-remote-unlock.ini all -m ping
```

This forces Ansible to use the Windows `ssh.exe`, `scp.exe`, and `sftp.exe`, which follow
the Windows network path when you need it.

### WSL mode through the direct management network

For the current setup with:

- `Laptop 1 -> 192.168.50.10 -> enp3s0` for SSH/Ansible
- `Laptop 2 -> 192.168.137.x -> enp2s0` for Internet sharing

run Ansible from WSL with the native Linux SSH client:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
unset ANSIBLE_CONFIG
ansible -i inventory-remote-unlock.ini all -k -m ping
```

If you previously exported `ANSIBLE_CONFIG="$PWD/ansible-wsl-ics.cfg"`, you must clear it before using the direct management path.

### If WSL cannot reach the IPC over the Windows shared network

If `ansible-playbook` from WSL times out on `192.168.137.x`, keep the same Ansible workflow
but execute it locally on the IPC.

1. Copy this `ansible/` directory to the IPC.
2. Install Ansible on the IPC.
3. Place the boot-unlock certificate bundle inside the copied repo under:

```text
.tmp/cascadya-remote-unlock/<inventory_hostname>/
```

4. Run the playbooks with:

```bash
ansible-playbook -i "localhost," -c local -K <playbook>.yml
```

This still keeps the integration purely Ansible-based while avoiding the WSL-to-ICS routing issue.

### 1. Baseline

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K baseline-report.yml
```

From WSL with the Windows SSH workaround:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
export ANSIBLE_CONFIG="$PWD/ansible-wsl-ics.cfg"
ansible-playbook -i inventory-remote-unlock.ini -k -K baseline-report.yml
```

From WSL on the direct management link:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
unset ANSIBLE_CONFIG
ansible-playbook -i inventory-remote-unlock.ini -k -K baseline-report.yml
```

### 1b. Generate the boot-unlock certificate bundle on the controller

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini remote-unlock-generate-certs.yml
```

If a previous run created an empty `client.crt`, force a clean regeneration:

```bash
ansible-playbook -i inventory-remote-unlock.ini remote-unlock-generate-certs.yml \
  -e remote_unlock_generate_certs_force=true
```

Generated files:

```text
.tmp/cascadya-remote-unlock/ca/ca.crt
.tmp/cascadya-remote-unlock/ca/ca.key
.tmp/cascadya-remote-unlock/<inventory_hostname>/ca.crt
.tmp/cascadya-remote-unlock/<inventory_hostname>/client.crt
.tmp/cascadya-remote-unlock/<inventory_hostname>/client.key
```

### 1c. Place only the boot-unlock certificates on the IPC

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-stage-certs.yml \
  -e remote_unlock_enable=true
```

### 2. Bootstrap

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_broker_url="https://unlock-broker.internal" \
  -e remote_unlock_device_id="cascadya"
```

If WireGuard is already managed outside this role, keep the default
`remote_unlock_manage_wireguard=false`.

Only enable the `network` role from this playbook if you explicitly want Ansible
to install and manage WireGuard on the IPC:

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_manage_wireguard=true
```

### 3. Validate the broker path without cutting over

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true
```

### 3a. Check prerequisites before the real validation

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml
```

The preflight must confirm:

- the management interface exists
- the uplink interface exists
- the default route is present on the uplink path
- `resolv.conf` contains usable nameservers
- the broker hostname resolves
- `wg` is installed
- `wg-quick@wg0.service` exists

If `wg` or `wg-quick@wg0.service` is missing, do not run `remote-unlock-validate.yml` yet.

### 3b. Validate the current WSL connection path before the real work

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible -i inventory-remote-unlock.ini all -k -m ping
```

## WireGuard prerequisite

The remote unlock flow depends on a working `wg0` transport on the IPC.

Before `remote-unlock-validate.yml`, the IPC must have:

- the `wireguard` package installed
- the `wg` binary available
- a valid `/etc/wireguard/wg0.conf`
- `wg-quick@wg0.service` enabled or startable
- broker reachability through that tunnel

If WireGuard is managed outside this repo, provision it first and only then run:

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true
```

If you want this repo to provision WireGuard on the IPC, define the WireGuard
variables in inventory or via `-e`, then run:

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_manage_wireguard=true \
  -e network_uplink_address="192.168.137.10/24" \
  -e network_wireguard_address="10.x.x.x/32" \
  -e network_wireguard_private_key="<device-private-key>" \
  -e network_wireguard_peer_public_key="<server-public-key>" \
  -e network_wireguard_endpoint="vpn.cascadya.com:51820"
```

Optional:

```bash
-e network_wireguard_allowed_ips='["10.0.0.0/8"]'
-e network_wireguard_dns='["1.1.1.1","8.8.8.8"]'
-e network_wireguard_extra_packages='["resolvconf"]'
```

### 4. Cut over to remote unlock

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-cutover.yml \
  -e remote_unlock_enable=true
```

### 5. Remove the local TPM token only after a successful reboot

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-remove-local-tpm.yml \
  -e remote_unlock_enable=true
```

## Commands to show the current protection level

Run these directly on the IPC:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /data
cat /etc/crypttab
sudo cryptsetup luksDump /dev/sda4 | sed -n '1,120p'
sudo cryptsetup luksDump /dev/sda4 | grep -i systemd-tpm2
sudo tpm2_pcrread sha256:7
sudo mender-update show-artifact
sudo wg show
```

Interpretation:

- LUKS/dm-crypt performs the actual data encryption on `/data`.
- TPM2 authorizes or helps authorize access to the LUKS secret.
- WireGuard is the trusted transport for the remote unlock flow.
- Mender state remains available only when `/data` is mounted.

## Commands to validate the new remote unlock flow

On the IPC:

```bash
systemctl status wg-quick@wg0 --no-pager
systemctl status cascadya-unlock-data.service --no-pager
journalctl -u cascadya-unlock-data.service -n 50 --no-pager
findmnt /data
sudo mender-update show-artifact
```

Expected result:

- `wg-quick@wg0` is active
- `cascadya-unlock-data.service` succeeds
- `/data` is mounted
- `mender-update show-artifact` returns the installed artifact

## Offline fallback

If the broker or WireGuard is unavailable, use the manual helper on the IPC:

```bash
sudo /usr/local/bin/unlock-data-manual
```

Then verify:

```bash
findmnt /data
sudo mender-update show-artifact
```
