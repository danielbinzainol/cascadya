#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <user@host>"
  exit 1
fi

TARGET="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

rsync -avz --delete \
  --exclude ".git/" \
  --exclude ".env" \
  --exclude ".env.local" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude "run.stdout.log" \
  --exclude "run.stderr.log" \
  "${REPO_DIR}/" "${TARGET}:/opt/cascadya_features/"
