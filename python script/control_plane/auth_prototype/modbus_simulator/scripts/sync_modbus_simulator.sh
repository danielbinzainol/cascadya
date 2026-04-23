#!/usr/bin/env bash
set -euo pipefail

SIMULATOR_HOST="${1:-192.168.50.2}"
SIMULATOR_USER="${SIMULATOR_USER:-cascadya}"
REMOTE_DIR="${REMOTE_DIR:-/home/cascadya/simulator_sbc}"
SERVICE_NAME="${SERVICE_NAME:-modbus-serveur.service}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
SIM_ROOT="${REPO_ROOT}/auth_prototype/modbus_simulator"

rsync -av --delete \
  "${SIM_ROOT}/src/" \
  "${SIMULATOR_USER}@${SIMULATOR_HOST}:${REMOTE_DIR}/"

scp "${SIM_ROOT}/systemd/${SERVICE_NAME}" \
  "${SIMULATOR_USER}@${SIMULATOR_HOST}:${REMOTE_DIR}/${SERVICE_NAME}"

ssh "${SIMULATOR_USER}@${SIMULATOR_HOST}" "
  sudo install -m 0644 '${REMOTE_DIR}/${SERVICE_NAME}' '/etc/systemd/system/${SERVICE_NAME}' &&
  sudo systemctl daemon-reload &&
  sudo systemctl restart '${SERVICE_NAME}' &&
  sudo systemctl status '${SERVICE_NAME}' --no-pager
"
