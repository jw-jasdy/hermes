#!/usr/bin/env bash
# ===========================================================================
# hermes-ops.sh — lightweight operational wrapper, run ON THE VM.
#
# Responds to the small set of operational commands the VM is allowed to
# handle. All heavy lifting stays on GitHub Actions; this is just a thin
# convenience around systemctl, journalctl, host diagnostics, and the hermes CLI.
#
# Usage: hermes-ops.sh {start|stop|restart|status|logs|journal-boot|env-check|summary|disk|memory|doctor|update}
# ===========================================================================
set -euo pipefail

HERMES_USER="${HERMES_USER:-hermes}"
HERMES_HOME="${HERMES_HOME:-/home/hermes}"
HERMES_CONFIG_DIR="${HERMES_CONFIG_DIR:-${HERMES_HOME}/.hermes}"
HERMES_BIN="${HERMES_HOME}/.local/bin/hermes"
SERVICE="hermes-agent.service"
ENV_FILE="/etc/hermes-agent/hermes.env"

run_hermes() {
  # Source the runtime env (Gemini/Telegram keys) without echoing it.
  sudo -u "${HERMES_USER}" \
    HERMES_HOME="${HERMES_CONFIG_DIR}" \
    HOME="${HERMES_HOME}" \
    bash -c 'set -a; [ -r /etc/hermes-agent/hermes.env ] && . /etc/hermes-agent/hermes.env; set +a; exec "$@"' _ "${HERMES_BIN}" "$@"
}

env_check() {
  if sudo test -r "${ENV_FILE}"; then
    sudo grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" | sed 's/=$//' | sort
  else
    echo "ERROR: ${ENV_FILE} not found or unreadable." >&2
    exit 1
  fi
}

summary() {
  echo "== Host =="
  hostnamectl || true
  echo
  echo "== Service =="
  sudo systemctl is-enabled "${SERVICE}" || true
  sudo systemctl is-active "${SERVICE}" || true
  sudo systemctl --no-pager --full status "${SERVICE}" || true
  echo
  echo "== Hermes binary =="
  ls -l "${HERMES_BIN}" || true
  "${HERMES_BIN}" --version || true
  echo
  echo "== Disk =="
  df -h / "${HERMES_HOME}" "${HERMES_CONFIG_DIR}" 2>/dev/null || df -h / || true
  echo
  echo "== Memory =="
  free -h || true
  echo
  echo "== Runtime env keys (values redacted) =="
  env_check || true
  echo
  echo "== Recent logs =="
  sudo journalctl -u "${SERVICE}" --no-pager -n "${LINES:-80}" || true
}

cmd="${1:-status}"
case "${cmd}" in
  start)   sudo systemctl start "${SERVICE}" ;;
  stop)    sudo systemctl stop "${SERVICE}" ;;
  restart) sudo systemctl restart "${SERVICE}" ;;
  status)  sudo systemctl --no-pager --full status "${SERVICE}" ;;
  logs)    sudo journalctl -u "${SERVICE}" --no-pager -n "${LINES:-200}" ;;
  # Full journal since the last boot -- useful for diagnosing crash loops or
  # startup failures that scrolled past the tail-limited `logs` action.
  journal-boot) sudo journalctl -u "${SERVICE}" --no-pager -b ;;
  # Lists which env var KEYS are set in the runtime env file, values redacted.
  # Use to confirm e.g. TELEGRAM_BOT_TOKEN made it to the VM without ever
  # printing secret values.
  env-check) env_check ;;
  summary) summary ;;
  disk) df -h / "${HERMES_HOME}" "${HERMES_CONFIG_DIR}" 2>/dev/null || df -h / ;;
  memory) free -h ;;
  doctor)  run_hermes doctor ;;
  update)
    run_hermes update
    sudo systemctl restart "${SERVICE}"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|journal-boot|env-check|summary|disk|memory|doctor|update}" >&2
    exit 2
    ;;
esac
