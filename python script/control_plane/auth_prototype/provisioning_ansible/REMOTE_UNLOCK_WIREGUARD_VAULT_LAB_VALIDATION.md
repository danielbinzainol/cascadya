# Remote Unlock WireGuard + Vault Lab Validation

This document is the execution protocol for validating the frozen
`remote-unlock` workflow in the lab.

Target shape:

- `IPC -> WireGuard -> broker -> Vault`
- broker WireGuard IP: `10.30.0.1/24`
- IPC WireGuard IP: `10.30.0.10/32`
- broker URL: `https://10.30.0.1:8443`
- Vault path: `secret/data/remote-unlock/cascadya`

This protocol is split into:

- workflow validation through `cutover`
- separate reboot milestone after `remove-local-tpm`

## 1. Preconditions

Before starting, confirm:

- IPC reachable over management SSH
- broker reachable over SSH
- Vault reachable from the broker host
- `UDP 51820` opened to the broker host
- broker certificate generated for SAN `10.30.0.1`
- client certificate bundle generated for the IPC
- `REMOTE_UNLOCK_BROKER_VAULT_TOKEN` exported in the shell that runs the broker playbooks

Recommended starting point:

- [REMOTE_UNLOCK_WIREGUARD_VAULT_RUNBOOK.md](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/REMOTE_UNLOCK_WIREGUARD_VAULT_RUNBOOK.md)
- [inventory-remote-unlock.ini.example](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/inventory-remote-unlock.ini.example)
- [inventory-remote-unlock-broker.ini.example](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/inventory-remote-unlock-broker.ini.example)

## 2. Execution sequence

### Step 1. Prepare broker WireGuard

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-prepare-broker-wireguard.yml
```

Expected result:

- `wg-quick@wg0` enabled and active on the broker
- `/etc/wireguard/server.key` present
- `/etc/wireguard/server.pub` present
- `/etc/wireguard/wg0.conf` present

Collect:

- `sudo systemctl status wg-quick@wg0 --no-pager`
- `sudo wg show`
- `ip addr show wg0`

Gate:

- stop here if `wg0` is not active or if `10.30.0.1/24` is missing

### Step 2. Deploy the broker

```bash
ansible-playbook remote-unlock-generate-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=10.30.0.1 \
  -e remote_unlock_generate_demo_broker_certs_force=true

ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-deploy-broker.yml
```

Expected result:

- broker container up
- `8443` listening locally
- broker certificate SAN matches `10.30.0.1`

Collect:

- `sudo ss -ltnp | grep 8443`
- `cd /opt/remote-unlock-broker && sudo docker compose ps || sudo docker-compose ps`
- `cd /opt/remote-unlock-broker && sudo docker compose logs --tail 50 || sudo docker-compose logs --tail 50`

Gate:

- stop here if `8443` is not listening or if the broker container is restarting

### Step 3. Seed the Vault secret

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-seed-vault-secret.yml \
  -e remote_unlock_device_id=cascadya \
  -e remote_unlock_vault_secret_value='CHANGE_ME'
```

Expected result:

- secret present under `secret/data/remote-unlock/cascadya`

Collect:

- playbook output showing the final Vault path and field name

Gate:

- stop here if the playbook reports the field missing after write

### Step 4. Bootstrap the IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml
```

Expected result:

- WireGuard packages installed if needed
- IPC `wg0.conf` rendered correctly
- `wg-quick@wg0` active
- certs staged
- AK public material exported
- `unlock.env` present
- `cascadya-unlock-data.service` present

Collect:

- `sudo systemctl status wg-quick@wg0 --no-pager`
- `sudo cat /etc/wireguard/wg0.conf`
- `sudo ls -l /etc/cascadya/unlock`
- `sudo ls -l /etc/cascadya/unlock/tpm`

Gate:

- stop here if `AllowedIPs` or `DNS` are malformed in `wg0.conf`

### Step 5. Preflight

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml
```

Expected result:

- management and uplink interfaces detected
- route to broker host present
- `wg-quick@wg0` active
- broker mTLS challenge returns `challenge_id` and `nonce`

Collect:

- full play recap
- summary block from the playbook

Gate:

- stop here if the broker challenge is incomplete or if no route exists to `10.30.0.1`

### Step 6. Manual network proof from the IPC

Run on the IPC:

```bash
sudo wg show
ip route get 10.30.0.1
ping -c 3 10.30.0.1
sudo curl -v \
  --cert /etc/cascadya/unlock/client.crt \
  --key /etc/cascadya/unlock/client.key \
  --cacert /etc/cascadya/unlock/ca.crt \
  -H "Content-Type: application/json" \
  --data '{"device_id":"cascadya","hostname":"cascadya","wg_interface":"wg0","management_interface":"enp3s0","uplink_interface":"enp2s0"}' \
  https://10.30.0.1:8443/challenge
```

Expected result:

- recent WireGuard handshake
- route through `wg0`
- ping success
- `HTTP 200`
- JSON with `challenge_id` and `nonce`

Gate:

- stop here if the manual `curl` does not succeed over the WireGuard IP

### Step 7. Validate

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml
```

Expected result:

- dry-run succeeds
- validation marker written at `/var/lib/cascadya/unlock/last-validate.json`
- summary shows WireGuard runtime and latest handshakes

Collect:

- play recap
- `sudo cat /var/lib/cascadya/unlock/last-validate.json`

Gate:

- stop here if the dry-run path fails or if the validation marker is absent

### Step 8. Cut over

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-cutover.yml
```

Expected result:

- `crypttab` backup created
- remote-unlock crypttab line written
- `cascadya-unlock-data.service` enabled
- cutover marker written at `/var/lib/cascadya/unlock/cutover-ready.json`

Collect:

- `sudo grep '^cascadya_data ' /etc/crypttab`
- `sudo cat /var/lib/cascadya/unlock/crypttab-cascadya_data.pre-remote-unlock`
- `sudo cat /var/lib/cascadya/unlock/cutover-ready.json`
- `sudo systemctl status cascadya-unlock-data.service --no-pager`

Gate:

- stop here if the crypttab backup is missing or if the cutover marker is absent

## 3. Acceptance criteria through cutover

The workflow is accepted up to `cutover` when all of the following are true:

- broker `wg0` active on `10.30.0.1/24`
- IPC `wg0` active on `10.30.0.10/32`
- broker challenge succeeds over `https://10.30.0.1:8443`
- `remote-unlock-preflight.yml` succeeds
- `remote-unlock-validate.yml` succeeds
- `last-validate.json` exists
- `remote-unlock-cutover.yml` succeeds
- `crypttab` backup exists
- `cutover-ready.json` exists

At that point the system is considered:

- ready for remote unlock
- not yet proven for exclusive remote unlock at boot

## 4. Separate reboot milestone after local TPM removal

This is intentionally outside the main acceptance gate.

### Step 9. Remove the local TPM token

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-remove-local-tpm.yml \
  -e remote_unlock_allow_remove_local_tpm=true
```

Expected result:

- local `systemd-tpm2` token removed from the LUKS header

Collect:

- `sudo cryptsetup luksDump /dev/sda4`

### Step 10. Controlled reboot

Reboot the IPC in a controlled window.

Expected result:

- `cascadya-unlock-data.service` runs automatically
- `/data` unlocks and mounts without local TPM fallback

Collect:

- `sudo journalctl -u cascadya-unlock-data.service -n 100 --no-pager`
- `findmnt /data`
- `sudo systemctl status cascadya-unlock-data.service --no-pager`

Final acceptance:

- `/data` mounted after reboot
- no local TPM token present in LUKS
- service journal shows the remote unlock path was used successfully

## 5. Failure matrix

If the failing point is:

- broker WG setup: inspect peer public key, allowed IPs, and `UDP 51820`
- broker deploy: inspect Docker Compose status and broker logs
- Vault seed: inspect broker Vault addr, token source, and KV path
- IPC bootstrap: inspect `/etc/wireguard/wg0.conf` and cert bundle staging
- preflight: inspect route, `wg show`, and manual `curl`
- validate: inspect `/usr/local/libexec/cascadya-unlock-data.sh` output and broker logs
- cutover: inspect `/etc/crypttab`, backup marker, and systemd unit state
- reboot milestone: inspect `journalctl -u cascadya-unlock-data.service` and broker logs around reboot time
