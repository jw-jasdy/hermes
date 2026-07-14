#!/usr/bin/env bash
# Run the Hermes Google Workspace OAuth helper with Hermes' own Python venv.
set -euo pipefail

USER_HOME="${HERMES_USER_HOME:-${HOME:-/home/hermes}}"
if [ -n "${HERMES_CONFIG_DIR:-}" ]; then
  CONFIG_DIR="${HERMES_CONFIG_DIR}"
elif [ -n "${HERMES_HOME:-}" ] && [ "$(basename "${HERMES_HOME}")" = ".hermes" ]; then
  CONFIG_DIR="${HERMES_HOME}"
else
  CONFIG_DIR="${HERMES_HOME:-${USER_HOME}}/.hermes"
fi
HELPER="${HERMES_GOOGLE_WORKSPACE_HELPER:-/usr/local/lib/hermes/google-workspace-oauth.py}"

PYTHON_BIN=""
for candidate in \
  "${CONFIG_DIR}/hermes-agent/venv/bin/python" \
  "${CONFIG_DIR}/hermes-agent/.venv/bin/python"; do
  if [ -x "${candidate}" ]; then
    PYTHON_BIN="${candidate}"
    break
  fi
done

if [ -z "${PYTHON_BIN}" ]; then
  echo "Hermes Python venv not found under ${CONFIG_DIR}/hermes-agent." >&2
  echo "Run Deploy Hermes Agent successfully before provisioning Google Workspace." >&2
  exit 1
fi

export HOME="${USER_HOME}"
export HERMES_CONFIG_DIR="${CONFIG_DIR}"
exec "${PYTHON_BIN}" "${HELPER}" "$@"
