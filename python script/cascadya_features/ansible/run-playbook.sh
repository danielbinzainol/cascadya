#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <inventory> [extra ansible-playbook args...]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVENTORY="$1"
shift

export ANSIBLE_ROLES_PATH="${SCRIPT_DIR}/roles"

ansible-playbook -i "${INVENTORY}" "${SCRIPT_DIR}/site.yml" "$@"

