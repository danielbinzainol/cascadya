# Monitoring Playbook Reference

This repo expects several runtime secrets. To avoid missing one at playbook
launch time, use the local env file plus the helper script below.

## One-time setup

```bash
cd ~/git/cascadya-project/playbook_ansible/ansible-monitoring
cp .env.monitoring.local.example .env.monitoring.local
```

Edit `.env.monitoring.local` and fill in:

```bash
VAULT_ADDR=https://secrets.cascadya.com
VAULT_SKIP_VERIFY=true
VAULT_TOKEN=replace_with_vault_token

GRAFANA_ADMIN_USER=replace_with_grafana_admin_user
GRAFANA_ADMIN_PASSWORD=replace_with_grafana_admin_password
MONITORING_POSTGRES_PASSWORD=replace_with_postgres_password
```

Notes:

- `.env.monitoring.local` is ignored by git.
- Scaleway S3 credentials are fetched from Vault automatically by the helper
  script unless you set `MIMIR_S3_ACCESS_KEY_ID` and
  `MIMIR_S3_SECRET_ACCESS_KEY` directly in `.env.monitoring.local`.

## Standard launch

```bash
cd ~/git/cascadya-project/playbook_ansible/ansible-monitoring
bash scripts/run-monitoring-playbook.sh
```

This command automatically:

- loads `.env.monitoring.local`
- checks `GRAFANA_ADMIN_USER`
- checks `GRAFANA_ADMIN_PASSWORD`
- checks `MONITORING_POSTGRES_PASSWORD`
- fetches Scaleway credentials from Vault when needed
- exports `ANSIBLE_CONFIG` and `ANSIBLE_ROLES_PATH`
- runs:

```bash
ansible-playbook -i inventory/hosts.ini playbooks/monitoring.yml --limit vm-monitoring -K -vv
```

Default behavior is optimized for the main path:

- the stack is not force-recreated unless a monitoring config file changed
- runtime checks run only when the stack or proxy actually changed
- only core external checks run by default
- `infracontrol` root traffic is routed to the dedicated Vite frontend service
  on `5173`, while `/api` and `/health` stay on the backend service on `3001`

## Full validation on demand

If you want the heavier internal checks too (`Loki`, `Mimir`, `Alloy`), run:

```bash
cd ~/git/cascadya-project/playbook_ansible/ansible-monitoring
bash scripts/run-monitoring-playbook.sh -i inventory/hosts.ini playbooks/monitoring.yml --limit vm-monitoring -K -vv -e monitoring_runtime_validation_scope=full
```

If you want to force a full container recreation:

```bash
cd ~/git/cascadya-project/playbook_ansible/ansible-monitoring
bash scripts/run-monitoring-playbook.sh -i inventory/hosts.ini playbooks/monitoring.yml --limit vm-monitoring -K -vv -e monitoring_force_recreate_stack=true
```

## Custom launch

You can pass any normal `ansible-playbook` arguments after the script name.

```bash
cd ~/git/cascadya-project/playbook_ansible/ansible-monitoring
bash scripts/run-monitoring-playbook.sh -i inventory/hosts.ini playbooks/monitoring.yml --limit vm-monitoring --syntax-check
```

## Manual fallback

If you prefer not to use the helper script:

```bash
cd ~/git/cascadya-project/playbook_ansible/ansible-monitoring
set -a
source .env.monitoring.local
set +a

SCW_JSON="$(curl -ksS -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/secret/data/scaleway")"
export SCW_ACCESS_KEY="$(echo "$SCW_JSON" | jq -er '.data.data.access_key')"
export SCW_SECRET_KEY="$(echo "$SCW_JSON" | jq -er '.data.data.secret_key')"
export MIMIR_S3_ACCESS_KEY_ID="${MIMIR_S3_ACCESS_KEY_ID:-$SCW_ACCESS_KEY}"
export MIMIR_S3_SECRET_ACCESS_KEY="${MIMIR_S3_SECRET_ACCESS_KEY:-$SCW_SECRET_KEY}"
export ANSIBLE_CONFIG="$PWD/ansible.cfg"
export ANSIBLE_ROLES_PATH="$PWD/roles"

ansible-playbook -i inventory/hosts.ini playbooks/monitoring.yml --limit vm-monitoring -K -vv
```

## Useful checks

```bash
ssh ubuntu@51.15.83.22
curl -k -H 'Host: infracontrol.cascadya.internal' https://127.0.0.1/health
curl -k -H 'Host: infracontrol.cascadya.internal' https://127.0.0.1/
curl --max-time 5 http://127.0.0.1:9009/ready
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```
