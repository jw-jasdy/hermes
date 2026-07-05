#!/usr/bin/env bash
# ===========================================================================
# ssh-iap.sh — run ON THE GITHUB ACTIONS RUNNER.
#
# Sets up (and tears down) EPHEMERAL SSH access to the VM through IAP TCP
# forwarding. No long-lived VM SSH key is ever stored as a GitHub secret:
# a fresh keypair is generated per run, registered via OS Login with a short
# TTL, and removed at the end.
#
#   ssh-iap.sh up    -> keygen + OS Login add + start IAP tunnel to localhost
#   ssh-iap.sh down  -> stop tunnel + remove the ephemeral key from OS Login
#
# State (key path, port, login user, tunnel pid) is written to $STATE_DIR/env
# so the calling workflow can `source` it:
#
#   source "$(scripts/ssh-iap.sh up)"     # prints the path to the env file
#   ssh -i "$SSH_KEY" -p "$SSH_PORT" ... "$SSH_USER"@localhost
#   scripts/ssh-iap.sh down
#
# Required env: VM_NAME, ZONE, PROJECT_ID
# Optional env:
#   LOCAL_PORT                  (default: auto-select a free localhost port)
#   STATE_DIR                   (default: $RUNNER_TEMP/hermes-ssh)
#   KEY_TTL                     (default: 3600s)
#   IAP_TUNNEL_ATTEMPTS         (default: 8)
#   IAP_TUNNEL_READY_SECONDS    (default: 20)
#   IAP_TUNNEL_RETRY_SLEEP      (default: 15)
# ===========================================================================
set -euo pipefail

: "${VM_NAME:?VM_NAME required}"
: "${ZONE:?ZONE required}"
: "${PROJECT_ID:?PROJECT_ID required}"
LOCAL_PORT="${LOCAL_PORT:-}"
KEY_TTL="${KEY_TTL:-3600s}"
STATE_DIR="${STATE_DIR:-${RUNNER_TEMP:-/tmp}/hermes-ssh}"
ENV_FILE="${STATE_DIR}/env"
IAP_TUNNEL_ATTEMPTS="${IAP_TUNNEL_ATTEMPTS:-8}"
IAP_TUNNEL_READY_SECONDS="${IAP_TUNNEL_READY_SECONDS:-20}"
IAP_TUNNEL_RETRY_SLEEP="${IAP_TUNNEL_RETRY_SLEEP:-15}"

log() { printf '[ssh-iap] %s\n' "$*" >&2; }

pick_local_port() {
  python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}

port_open() {
  (exec 3<>"/dev/tcp/127.0.0.1/${LOCAL_PORT}") 2>/dev/null
}

close_probe_fd() {
  exec 3>&- 3<&- 2>/dev/null || true
}

wait_for_oslogin_user() {
  local attempt user
  for attempt in $(seq 1 12); do
    user="$(gcloud compute os-login describe-profile \
      --project="${PROJECT_ID}" \
      --format='value(posixAccounts[0].username)' 2>/dev/null || true)"
    if [ -n "${user}" ]; then
      printf '%s\n' "${user}"
      return 0
    fi
    log "OS Login profile not ready yet (attempt ${attempt}/12); waiting..."
    sleep 5
  done
  log "ERROR: could not determine OS Login username."
  return 1
}

start_tunnel_with_retries() {
  local attempt pid rc log_file sleep_seconds
  for attempt in $(seq 1 "${IAP_TUNNEL_ATTEMPTS}"); do
    log_file="${STATE_DIR}/tunnel-${attempt}.log"
    rm -f "${STATE_DIR}/tunnel.pid" "${log_file}"

    log "Starting IAP tunnel attempt ${attempt}/${IAP_TUNNEL_ATTEMPTS}: localhost:${LOCAL_PORT} -> ${VM_NAME}:22 ..."
    nohup gcloud compute start-iap-tunnel "${VM_NAME}" 22 \
      --local-host-port="127.0.0.1:${LOCAL_PORT}" \
      --zone="${ZONE}" \
      --project="${PROJECT_ID}" >"${log_file}" 2>&1 &
    pid="$!"
    echo "${pid}" >"${STATE_DIR}/tunnel.pid"

    for _ in $(seq 1 "${IAP_TUNNEL_READY_SECONDS}"); do
      if port_open; then
        close_probe_fd
        cp "${log_file}" "${STATE_DIR}/tunnel.log" 2>/dev/null || true
        log "IAP tunnel is accepting connections."
        return 0
      fi

      if ! kill -0 "${pid}" 2>/dev/null; then
        rc=0
        wait "${pid}" 2>/dev/null || rc="$?"
        log "IAP tunnel process exited early with status ${rc}."
        break
      fi
      sleep 1
    done

    if kill -0 "${pid}" 2>/dev/null; then
      log "IAP tunnel attempt ${attempt} did not become ready after ${IAP_TUNNEL_READY_SECONDS}s; stopping it."
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi

    if [ -s "${log_file}" ]; then
      log "Last tunnel output from attempt ${attempt}:"
      tail -n 80 "${log_file}" >&2 || true
    fi

    if [ "${attempt}" != "${IAP_TUNNEL_ATTEMPTS}" ]; then
      sleep_seconds=$((IAP_TUNNEL_RETRY_SLEEP * attempt))
      [ "${sleep_seconds}" -gt 60 ] && sleep_seconds=60
      log "Waiting ${sleep_seconds}s for IAP/OS Login IAM propagation before retrying..."
      sleep "${sleep_seconds}"
    fi
  done

  log "ERROR: IAP tunnel did not come up after ${IAP_TUNNEL_ATTEMPTS} attempts."
  log "Check IAP tunnel access, OS Login admin access, and the IAP SSH firewall rule."
  return 1
}

up() {
  mkdir -p "${STATE_DIR}"
  chmod 700 "${STATE_DIR}"
  local key="${STATE_DIR}/id_ed25519"

  if [ -z "${LOCAL_PORT}" ]; then
    LOCAL_PORT="$(pick_local_port)"
  fi

  log "Generating ephemeral SSH keypair..."
  rm -f "${key}" "${key}.pub"
  ssh-keygen -t ed25519 -N "" -f "${key}" -C "hermes-ci-ephemeral" >/dev/null

  log "Registering public key with OS Login (TTL ${KEY_TTL})..."
  gcloud compute os-login ssh-keys add \
    --key-file="${key}.pub" \
    --ttl="${KEY_TTL}" \
    --project="${PROJECT_ID}" >/dev/null

  local user
  user="$(wait_for_oslogin_user)"

  start_tunnel_with_retries

  {
    echo "export SSH_KEY='${key}'"
    echo "export SSH_PORT='${LOCAL_PORT}'"
    echo "export SSH_USER='${user}'"
    echo "export SSH_OPTS='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ServerAliveInterval=30 -o ServerAliveCountMax=3'"
  } >"${ENV_FILE}"

  log "Ephemeral SSH ready (user=${user}, port=${LOCAL_PORT})."
  echo "${ENV_FILE}"
}

down() {
  if [ -f "${STATE_DIR}/tunnel.pid" ]; then
    log "Stopping IAP tunnel..."
    kill "$(cat "${STATE_DIR}/tunnel.pid")" 2>/dev/null || true
    rm -f "${STATE_DIR}/tunnel.pid"
  fi
  if [ -f "${STATE_DIR}/id_ed25519.pub" ]; then
    log "Removing ephemeral key from OS Login..."
    # --key accepts either a raw public key or its OS Login fingerprint (a hex
    # SHA-256 digest) -- NOT ssh-keygen's base64 display fingerprint, which is
    # a different format and would silently never match. Pass the public key
    # file directly to avoid the format mismatch entirely.
    gcloud compute os-login ssh-keys remove --key="${STATE_DIR}/id_ed25519.pub" --project="${PROJECT_ID}" || true
  fi
  rm -rf "${STATE_DIR}"
  log "Ephemeral SSH torn down."
}

case "${1:-}" in
  up)   up ;;
  down) down ;;
  *)    echo "Usage: $0 {up|down}" >&2; exit 2 ;;
esac
