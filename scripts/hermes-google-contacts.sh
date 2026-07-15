#!/usr/bin/env bash
# Run the dependency-free Hermes Google Contacts client.
set -euo pipefail

USER_HOME="${HERMES_USER_HOME:-${HOME:-/home/hermes}}"
if [ -n "${HERMES_CONFIG_DIR:-}" ]; then
  CONFIG_DIR="${HERMES_CONFIG_DIR}"
elif [ -n "${HERMES_HOME:-}" ] && [ "$(basename "${HERMES_HOME}")" = ".hermes" ]; then
  CONFIG_DIR="${HERMES_HOME}"
else
  CONFIG_DIR="${HERMES_HOME:-${USER_HOME}}/.hermes"
fi
CLIENT="${HERMES_GOOGLE_CONTACTS_CLIENT:-/usr/local/lib/hermes/google-contacts-api.py}"

export HOME="${USER_HOME}"
export HERMES_CONFIG_DIR="${CONFIG_DIR}"
exec /usr/bin/python3 "${CLIENT}" "$@"
