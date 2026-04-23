#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_INVENTORY="$SCRIPT_DIR/inventory/hosts.yml"
PLAYBOOK="$SCRIPT_DIR/playbooks/auth_stack.yml"

INVENTORY="${1:-$DEFAULT_INVENTORY}"
if [[ $# -gt 0 ]]; then
  shift
fi

export ANSIBLE_ROLES_PATH="$SCRIPT_DIR/roles"

exec ansible-playbook -i "$INVENTORY" "$PLAYBOOK" "$@"
