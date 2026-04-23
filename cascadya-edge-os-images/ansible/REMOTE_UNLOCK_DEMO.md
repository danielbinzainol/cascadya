# Remote Unlock Demo

This document describes the fastest credible demo path when the production router and WireGuard
path are not configured yet.

The goal is to demonstrate:

- the IPC contacts an external broker
- the IPC presents its client certificate
- the IPC sends TPM quote material
- the broker fetches the unlock secret from Vault
- the broker returns the secret and the IPC can unlock `/data`

This is a demo flow. The included demo broker validates:

- mTLS client trust
- certificate CN matching `device_id`
- challenge / nonce continuity
- presence of TPM quote payload fields

It does not cryptographically verify the TPM quote yet. Keep that distinction explicit.

## 1. Generate the IPC client certificates

```bash
ansible-playbook -i inventory-remote-unlock.ini remote-unlock-generate-certs.yml
```

## 2. Generate the demo broker server certificate

Use the management-network IP or DNS name that the IPC can reach.

```bash
ansible-playbook remote-unlock-generate-demo-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=192.168.50.1
```

If the laptop management IP changes, or if you first generated the cert with the
wrong IP, force a clean regeneration:

```bash
ansible-playbook remote-unlock-generate-demo-broker-certs.yml \
  -e remote_unlock_demo_broker_san_ip=192.168.50.20 \
  -e remote_unlock_generate_demo_broker_certs_force=true
```

Generated bundle:

```text
.tmp/cascadya-remote-unlock/broker/server.crt
.tmp/cascadya-remote-unlock/broker/server.key
.tmp/cascadya-remote-unlock/broker/ca.crt
```

## 3. Start Vault in dev mode on the laptop

Example:

```bash
vault server -dev -dev-listen-address=0.0.0.0:8200
```

In another shell:

```bash
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=root
vault kv put secret/remote-unlock/cascadya secret=admin
```

## 4. Start the demo broker on the laptop

### Option A: run it directly from WSL

```bash
export VAULT_TOKEN=root
python3 demo/remote_unlock_demo_broker.py \
  --listen-host 0.0.0.0 \
  --listen-port 8443 \
  --server-cert .tmp/cascadya-remote-unlock/broker/server.crt \
  --server-key .tmp/cascadya-remote-unlock/broker/server.key \
  --client-ca .tmp/cascadya-remote-unlock/broker/ca.crt \
  --vault-addr http://127.0.0.1:8200 \
  --vault-kv-mount secret \
  --vault-kv-prefix remote-unlock
```

### Option B: run it in Docker on the laptop

This is often more reliable when the IPC must reach the service through the laptop host IP.

Create a dedicated Docker network:

```bash
docker network create cascadya-demo
```

Start Vault on that network:

```bash
docker run --cap-add=IPC_LOCK --name vault-demo --network cascadya-demo -d -p 8200:8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID=dev-only-token \
  hashicorp/vault server -dev -dev-listen-address=0.0.0.0:8200
```

Seed the secret:

```bash
curl -sS \
  -H "X-Vault-Token: dev-only-token" \
  -H "Content-Type: application/json" \
  --data '{"data":{"secret":"admin"}}' \
  http://127.0.0.1:8200/v1/secret/data/remote-unlock/cascadya
```

Build the broker image:

```bash
docker build -t cascadya-demo-broker -f demo/Dockerfile.remote-unlock-demo-broker .
```

Run the broker on the same Docker network and publish `8443` on the laptop:

```bash
docker run --name remote-unlock-demo-broker --network cascadya-demo -p 8443:8443 \
  -v "$PWD/.tmp/cascadya-remote-unlock/broker:/certs:ro" \
  -e VAULT_TOKEN=dev-only-token \
  cascadya-demo-broker \
  --listen-host 0.0.0.0 \
  --listen-port 8443 \
  --server-cert /certs/server.crt \
  --server-key /certs/server.key \
  --client-ca /certs/ca.crt \
  --vault-addr http://vault-demo:8200 \
  --vault-kv-mount secret \
  --vault-kv-prefix remote-unlock
```

### If the IPC times out on `https://<LAPTOP_MGMT_IP>:8443`

On some Docker Desktop / WSL setups, the published port is only bound to loopback on Windows.
You can confirm it from an elevated PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 8443 -State Listen | Select-Object LocalAddress,LocalPort
```

If you only see `127.0.0.1` and `::1`, publish the broker through the Windows host IP with a port proxy:

```powershell
netsh interface portproxy add v4tov4 listenaddress=<LAPTOP_MGMT_IP> listenport=8443 connectaddress=127.0.0.1 connectport=8443
New-NetFirewallRule -DisplayName "Cascadya Demo Broker 8443" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443
```

Example for the current lab:

```powershell
netsh interface portproxy add v4tov4 listenaddress=192.168.50.20 listenport=8443 connectaddress=127.0.0.1 connectport=8443
New-NetFirewallRule -DisplayName "Cascadya Demo Broker 8443" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443
```

Then re-run the IPC-side validation.

## 5. Point the IPC to the demo broker in direct mode

Example inventory line:

```ini
[cascadya_ipc]
cascadya ansible_host=192.168.50.10 ansible_user=cascadya remote_unlock_transport_mode=direct remote_unlock_management_interface=enp3s0 remote_unlock_broker_url=https://<LAPTOP_MGMT_IP>:8443
```

Use the actual IPv4 of the laptop Ethernet interface connected to the IPC.
On Windows, get it with:

```powershell
ipconfig
```

Example from the current lab:

```text
Carte Ethernet Ethernet 2 : 192.168.50.20
```

So the real broker URL for this lab is:

```text
https://192.168.50.20:8443
```

Deploy or refresh the IPC-side assets:

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-stage-certs.yml \
  -e remote_unlock_enable=true

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-bootstrap.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=direct \
  -e remote_unlock_device_id=cascadya
```

## 6. Validate the demo path

```bash
ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-preflight.yml \
  -e remote_unlock_transport_mode=direct

ansible-playbook -i inventory-remote-unlock.ini -k -K remote-unlock-validate.yml \
  -e remote_unlock_enable=true \
  -e remote_unlock_transport_mode=direct
```

Expected result:

- `Dry-run remote unlock completed successfully`
- broker logs show challenge and unlock approval
- Vault contains the secret source of truth

## 7. What to tell the audience

- Today's demo proves the IPC-side integration and the Vault-backed release flow.
- The final production transport will be WireGuard through the Teltonika / cloud path.
- The TPM quote is already generated and sent by the IPC.
- The remaining production-hardening step is the server-side cryptographic verification of that quote.
