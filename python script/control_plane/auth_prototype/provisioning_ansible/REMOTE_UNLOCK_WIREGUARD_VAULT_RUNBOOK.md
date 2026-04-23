# Remote Unlock WireGuard + Vault Runbook

This is the canonical remote-unlock workflow frozen for the current lab-proven
shape:

- `IPC -> WireGuard -> broker -> Vault`
- broker URL over WireGuard: `https://10.30.0.1:8443`
- validation through `cutover`
- `remove-local-tpm` kept as a separate post-validation milestone

Important scope note:

- this workflow is the current day-0/day-1 reference implementation
- it is not yet the future control plane
- broker-side cryptographic TPM quote verification is still out of scope here

Lab execution and acceptance are documented in:

- [REMOTE_UNLOCK_WIREGUARD_VAULT_LAB_VALIDATION.md](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/REMOTE_UNLOCK_WIREGUARD_VAULT_LAB_VALIDATION.md)

## 1. Prepare inventories

Start from:

- [inventory-remote-unlock.ini.example](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/inventory-remote-unlock.ini.example)
- [inventory-remote-unlock-broker.ini.example](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/inventory-remote-unlock-broker.ini.example)

Notes:

- the IPC inventory is now wireguard-first
- list-shaped values are expressed as JSON lists in inventory
- do not store the broker Vault token in Git-tracked inventory files

Export the broker Vault token in your shell instead:

```bash
export REMOTE_UNLOCK_BROKER_VAULT_TOKEN='CHANGE_ME'
```

## 2. Generate IPC certificates

```bash
ansible-playbook -i inventory-remote-unlock.ini remote-unlock-generate-certs.yml
```

## 3. Prepare broker WireGuard

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-prepare-broker-wireguard.yml
```

This playbook installs `wireguard-tools`, creates or reuses the broker key pair,
renders `/etc/wireguard/wg0.conf`, and ensures `wg-quick@wg0` is active.

Manual infra step still required:

- open `UDP 51820` to the broker host
- keep or close public `TCP 8443` according to your rollout strategy

## 4. Generate the broker certificate for the WireGuard IP

```bash
ansible-playbook remote-unlock-generate-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=10.30.0.1 \
  -e remote_unlock_generate_demo_broker_certs_force=true
```

## 5. Deploy the broker

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-deploy-broker.yml
```

The broker playbook reads the Vault token from:

- `remote_unlock_broker_vault_token`, or
- `REMOTE_UNLOCK_BROKER_VAULT_TOKEN`

## 6. Seed the Vault secret

```bash
ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-seed-vault-secret.yml \
  -e remote_unlock_device_id=cascadya \
  -e remote_unlock_vault_secret_value='CHANGE_ME'
```

## 7. Bootstrap the IPC

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml
```

This is the canonical bootstrap entry point. It must be able to guarantee:

- packages present
- cert bundle present
- persistent AK exported
- `unlock.env` present
- unlock script present
- systemd unit present
- `wg0` up when `remote_unlock_transport_mode=wireguard`

## 8. Preflight

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml
```

Preflight now checks the effective path, not just file presence:

- `wg` available when needed
- `wg-quick@wg0` active
- route to the broker host
- broker mTLS reachability through `POST /challenge`
- client cert bundle present
- TPM artifacts present

## 9. Validate

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml
```

This playbook keeps the dry-run path as the proof point for:

- WireGuard runtime
- broker contact through WG
- Vault-backed secret retrieval path
- persisted validation marker in `/var/lib/cascadya/unlock`

## 10. Cut over

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-cutover.yml
```

Cutover now:

- requires a successful validation marker first
- backs up the current `crypttab` entry
- writes the deterministic remote-unlock `crypttab` policy
- enables `cascadya-unlock-data.service`
- persists a `cutover-ready` marker

At this stage the system is ready for remote unlock, but the exclusive boot path
is not yet proven.

## 11. Remove the local TPM token only after explicit approval

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-remove-local-tpm.yml \
  -e remote_unlock_allow_remove_local_tpm=true
```

Guards now enforced:

- explicit opt-in required
- validation marker must exist and be recent
- cutover marker must exist

This remains a separate milestone. The actual proof of exclusive remote unlock
is only established after the controlled reboot that follows local TPM removal.
