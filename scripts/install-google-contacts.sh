#!/usr/bin/env bash
# Idempotently install the Hermes Google Contacts OAuth helper, runtime client,
# wrapper, and managed skill.
set -euo pipefail

HERMES_USER="${HERMES_USER:-hermes}"
HERMES_GROUP="${HERMES_GROUP:-${HERMES_USER}}"
HERMES_USER_HOME="${HERMES_USER_HOME:-${HERMES_HOME:-/home/hermes}}"
HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-${HERMES_USER_HOME}/.hermes}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OAUTH_SOURCE="${CONTACTS_OAUTH_SOURCE:-${SCRIPT_DIR}/google-contacts-oauth.py}"
API_SOURCE="${CONTACTS_API_SOURCE:-${SCRIPT_DIR}/google-contacts-api.py}"
SKILL_SOURCE="${CONTACTS_SKILL_SOURCE:-${SCRIPT_DIR}/google-contacts-skill/SKILL.md}"

TARGET_LIB_DIR="/usr/local/lib/hermes"
TARGET_OAUTH="${TARGET_LIB_DIR}/google-contacts-oauth.py"
TARGET_API="${TARGET_LIB_DIR}/google-contacts-api.py"
TARGET_WRAPPER="/usr/local/bin/hermes-google-contacts"
TARGET_USER_BIN_DIR="${HERMES_USER_HOME}/.local/bin"
TARGET_SKILL_DIR="${HERMES_CONFIG_DIR}/skills/productivity/google-contacts"
TARGET_SKILL_SCRIPTS_DIR="${TARGET_SKILL_DIR}/scripts"

syntax_check() {
  /usr/bin/python3 - "$1" <<'PY'
import ast
import sys
from pathlib import Path

path = Path(sys.argv[1])
ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
PY
}

install -d -o root -g root -m 0755 "${TARGET_LIB_DIR}"
install -d -o "${HERMES_USER}" -g "${HERMES_GROUP}" -m 0755 "${TARGET_USER_BIN_DIR}"
install -d -o "${HERMES_USER}" -g "${HERMES_GROUP}" -m 0755 "${TARGET_SKILL_SCRIPTS_DIR}"

syntax_check "${OAUTH_SOURCE}"
syntax_check "${API_SOURCE}"
install -o root -g root -m 0755 "${OAUTH_SOURCE}" "${TARGET_OAUTH}"
install -o root -g root -m 0755 "${API_SOURCE}" "${TARGET_API}"
install -o root -g root -m 0755 "${SCRIPT_DIR}/hermes-google-contacts.sh" "${TARGET_WRAPPER}"
install -o "${HERMES_USER}" -g "${HERMES_GROUP}" -m 0755 \
  "${SCRIPT_DIR}/hermes-google-contacts.sh" \
  "${TARGET_USER_BIN_DIR}/hermes-google-contacts"
install -o "${HERMES_USER}" -g "${HERMES_GROUP}" -m 0755 \
  "${TARGET_API}" "${TARGET_SKILL_SCRIPTS_DIR}/google_contacts.py"

if [ -f "${SKILL_SOURCE}" ]; then
  install -o "${HERMES_USER}" -g "${HERMES_GROUP}" -m 0644 \
    "${SKILL_SOURCE}" "${TARGET_SKILL_DIR}/SKILL.md"
else
  echo "Missing Google Contacts skill source: ${SKILL_SOURCE}" >&2
  exit 1
fi

echo "GOOGLE_CONTACTS_RUNTIME_INSTALLED"
