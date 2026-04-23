# Remote Unlock Broker Direct Deployment

Legacy note:

- this direct broker exposure flow is now kept only for diagnostics and lab fallback
- the canonical workflow is the WireGuard + Vault runbook in
  [REMOTE_UNLOCK_WIREGUARD_VAULT_RUNBOOK.md](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/REMOTE_UNLOCK_WIREGUARD_VAULT_RUNBOOK.md)

This document deploys the current remote-unlock broker implementation directly on
`broker-DEV1-S` on port `8443`, without Traefik.

Use this when:

- the IPC-side remote unlock flow is already deployed
- `vault-DEV1-S` is reachable
- you want the fastest credible server-side path for `POST /challenge` and
  `POST /unlock`

Important scope note:

- the broker implementation deployed here is the current repository broker
  implementation
- it already enforces mTLS, `device_id` / cert CN continuity, challenge TTL,
  and Vault-backed secret release
- it does **not** yet cryptographically verify the TPM quote

## 1. Generate the broker server certificate bundle

The broker certificate must match the URL used by the IPC.

Example with the public broker IP:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

ansible-playbook remote-unlock-generate-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=51.15.64.139 \
  -e remote_unlock_generate_demo_broker_certs_force=true
```

Generated bundle:

```text
.tmp/cascadya-remote-unlock/broker/server.crt
.tmp/cascadya-remote-unlock/broker/server.key
.tmp/cascadya-remote-unlock/broker/ca.crt
```

## 2. Create a broker inventory

Use [inventory-remote-unlock-broker.ini.example](c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/cascadya-edge-os-images/ansible/inventory-remote-unlock-broker.ini.example)
as the starting point.

Recommended initial shape:

```ini
[remote_unlock_broker]
broker-DEV1-S ansible_host=51.15.64.139 ansible_user=ubuntu remote_unlock_broker_bind_port=8443 remote_unlock_broker_vault_addr=http://51.15.36.65:8200 remote_unlock_broker_vault_token=CHANGE_ME remote_unlock_broker_vault_kv_mount=secret remote_unlock_broker_vault_kv_prefix=remote-unlock
```

Notes:

- replace `CHANGE_ME` with a real Vault token or pass it via `-e`
- keep the token out of Git; prefer a local inventory copy or Ansible Vault
- `remote_unlock_broker_vault_addr` should point to the real Vault endpoint seen
  by `broker-DEV1-S`

## 3. Deploy the broker

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

ansible-playbook -i inventory-remote-unlock-broker.ini -k -K remote-unlock-deploy-broker.yml
```

What this playbook does:

- copies the broker TLS bundle to `/opt/remote-unlock-broker/certs`
- copies the current broker Python service from this repo
- writes a local Dockerfile and compose file
- writes `broker.env` with the Vault token
- runs `docker compose up -d --build` or `docker-compose up -d --build`
- waits for port `8443` to listen locally on the broker host

## 4. Verify on broker-DEV1-S

```bash
sudo ss -ltnp | grep 8443
cd /opt/remote-unlock-broker
sudo docker compose ps || sudo docker-compose ps
sudo docker compose logs --tail 50 || sudo docker-compose logs --tail 50
```

Expected result:

- a container named `remote_unlock_broker` is up
- `8443` is listening

## 5. Point the IPC to the real broker

Example:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_broker_url=https://51.15.64.139:8443

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml \
  -e remote_unlock_broker_url=https://51.15.64.139:8443

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_broker_url=https://51.15.64.139:8443
```

Expected result:

- `remote-unlock-preflight.yml` shows broker TCP reachable
- `remote-unlock-validate.yml` completes the dry-run successfully

Before `remote-unlock-validate.yml`, make sure Vault contains a secret for the
IPC `device_id`.

Fastest path with the broker inventory already in place:

```bash
cd ~/git/cascadya-project/cascadya-edge-os-images/ansible

ansible-playbook -i inventory-remote-unlock-broker.ini remote-unlock-seed-vault-secret.yml \
  -e ansible_ssh_private_key_file=~/.ssh/id_ed25519 \
  -e ansible_ssh_transfer_method=piped \
  -e remote_unlock_device_id=cascadya \
  -e remote_unlock_vault_secret_value='admin'
```

The current broker accepts any one of these fields at
`secret/remote-unlock/<device_id>`:

- `secret_b64`
- `secret`
- `luks_passphrase`

If Vault returns `404` for `/unlock`, this secret is missing or written to the
wrong path.

## 6. Multi-IPC scaling

This architecture scales correctly to multiple IPCs because:

- each IPC has its own client certificate bundle
- each IPC keeps its own `device_id`
- the broker can map each `device_id` to a dedicated Vault path
- the broker centralizes the authorization and logging policy instead of
  pushing Vault trust directly to every IPC
