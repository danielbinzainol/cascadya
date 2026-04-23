#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_REMOTE_PATH="/opt/control-panel/control_plane/auth_prototype"
EXCLUDES_FILE="$SCRIPT_DIR/rsync-excludes.txt"

if [[ $# -lt 1 || $# -gt 2 ]]; then
  cat <<'EOF' >&2
Usage: ./auth_prototype/ansible/sync-auth-prototype.sh <ssh-target> [remote-auth-prototype-path]

Examples:
  ./auth_prototype/ansible/sync-auth-prototype.sh ubuntu@51.15.115.203
  ./auth_prototype/ansible/sync-auth-prototype.sh ubuntu@51.15.115.203 /opt/control-panel/control_plane/auth_prototype
EOF
  exit 1
fi

SSH_TARGET="$1"
REMOTE_PATH="${2:-$DEFAULT_REMOTE_PATH}"

echo "[sync] auth_prototype -> ${SSH_TARGET}:${REMOTE_PATH}"
rsync \
  -av \
  --delete \
  --exclude-from="$EXCLUDES_FILE" \
  "$SOURCE_DIR/" \
  "${SSH_TARGET}:${REMOTE_PATH}/"

echo "[cleanup] python caches on ${SSH_TARGET}:${REMOTE_PATH}"
ssh "$SSH_TARGET" "find '$REMOTE_PATH' -type d -name '__pycache__' -prune -exec rm -rf {} + && find '$REMOTE_PATH' -type f -name '*.pyc' -delete"

echo "[done] sync complete"
