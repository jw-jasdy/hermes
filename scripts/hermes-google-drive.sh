#!/usr/bin/env bash
# Run the folder-bound Google Drive/Docs/Sheets client with system Python.
set -euo pipefail

USER_HOME="${HERMES_USER_HOME:-${HOME:-/home/hermes}}"
if [ -n "${HERMES_CONFIG_DIR:-}" ]; then
  CONFIG_DIR="${HERMES_CONFIG_DIR}"
elif [ -n "${HERMES_HOME:-}" ] && [ "$(basename "${HERMES_HOME}")" = ".hermes" ]; then
  CONFIG_DIR="${HERMES_HOME}"
else
  CONFIG_DIR="${HERMES_HOME:-${USER_HOME}}/.hermes"
fi

SCRIPT="${HERMES_GOOGLE_DRIVE_SCRIPT:-${CONFIG_DIR}/skills/productivity/google-workspace/scripts/google_drive.py}"
if [ ! -f "${SCRIPT}" ]; then
  echo "Hermes Google Drive workspace client not found: ${SCRIPT}" >&2
  echo "Run Google Workspace Runtime Repair." >&2
  exit 1
fi

export HOME="${USER_HOME}"
export HERMES_HOME="${CONFIG_DIR}"
export HERMES_CONFIG_DIR="${CONFIG_DIR}"
exec /usr/bin/python3 "${SCRIPT}" "$@"
