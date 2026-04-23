#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${MONITORING_ENV_FILE:-$REPO_DIR/.env.monitoring.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  cat <<EOF
Missing environment file: $ENV_FILE

Create it from:
  cp .env.monitoring.local.example .env.monitoring.local
EOF
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required variable: $name" >&2
    exit 1
  fi
}

require_var GRAFANA_ADMIN_USER
require_var GRAFANA_ADMIN_PASSWORD
require_var MONITORING_POSTGRES_PASSWORD

if [[ -z "${MIMIR_S3_ACCESS_KEY_ID:-}" || -z "${MIMIR_S3_SECRET_ACCESS_KEY:-}" ]]; then
  if [[ -n "${SCW_ACCESS_KEY:-}" && -n "${SCW_SECRET_KEY:-}" ]]; then
    export MIMIR_S3_ACCESS_KEY_ID="${MIMIR_S3_ACCESS_KEY_ID:-$SCW_ACCESS_KEY}"
    export MIMIR_S3_SECRET_ACCESS_KEY="${MIMIR_S3_SECRET_ACCESS_KEY:-$SCW_SECRET_KEY}"
  else
    require_var VAULT_ADDR
    require_var VAULT_TOKEN

    CURL_ARGS=(-fsS)
    if [[ "${VAULT_SKIP_VERIFY:-false}" == "true" ]]; then
      CURL_ARGS+=(-k)
    fi

    SCW_JSON="$(curl "${CURL_ARGS[@]}" -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/secret/data/scaleway")"
    export SCW_ACCESS_KEY="$(echo "$SCW_JSON" | jq -er '.data.data.access_key')"
    export SCW_SECRET_KEY="$(echo "$SCW_JSON" | jq -er '.data.data.secret_key')"
    export MIMIR_S3_ACCESS_KEY_ID="${MIMIR_S3_ACCESS_KEY_ID:-$SCW_ACCESS_KEY}"
    export MIMIR_S3_SECRET_ACCESS_KEY="${MIMIR_S3_SECRET_ACCESS_KEY:-$SCW_SECRET_KEY}"
  fi
fi

export ANSIBLE_CONFIG="$REPO_DIR/ansible.cfg"
export ANSIBLE_ROLES_PATH="$REPO_DIR/roles"

if [[ $# -eq 0 ]]; then
  set -- -i inventory/hosts.ini playbooks/monitoring.yml --limit vm-monitoring -K -vv
fi

printf 'Grafana admin user=%s\n' "$GRAFANA_ADMIN_USER"
printf 'Mimir AK prefix=%s len=%s\n' "${MIMIR_S3_ACCESS_KEY_ID:0:4}" "${#MIMIR_S3_ACCESS_KEY_ID}"
printf 'Mimir SK len=%s\n' "${#MIMIR_S3_SECRET_ACCESS_KEY}"

cd "$REPO_DIR"
ansible-playbook "$@"
