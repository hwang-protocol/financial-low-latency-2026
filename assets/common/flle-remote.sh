#!/usr/bin/env bash

# A pasted course card may source this library again in the same shell.
# Recognise a complete earlier load, including versions without this guard.
if declare -F flle_finish >/dev/null 2>&1 && declare -p FLLE_SSH_OPTS >/dev/null 2>&1; then
  return 0
fi

set -Eeuo pipefail

readonly FLLE_JUMP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly FLLE_IDENTITY_FILE="${FLLE_IDENTITY_FILE:-/root/.ssh/flle_course_ed25519}"
readonly FLLE_SSH_KNOWN_HOSTS="${FLLE_JUMP_ROOT}/assets/common/ssh_known_hosts"
readonly FLLE_SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=8
  -o IdentitiesOnly=yes
  -o "IdentityFile=${FLLE_IDENTITY_FILE}"
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=3
  -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=${FLLE_SSH_KNOWN_HOSTS}"
)

readonly FLLE_VM1="10.1.1.1"
readonly FLLE_VM2="10.1.1.2"
readonly FLLE_VM11="10.1.1.11"
readonly FLLE_VM101="10.1.1.101"
readonly FLLE_ARISTA="10.1.1.253"

flle_die() {
  printf 'FLLE_ERROR %s\n' "$*" >&2
  exit 1
}

flle_note() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

flle_require_jump_host() {
  [[ -f "${FLLE_JUMP_ROOT}/00-cpu-cache-memory-os-basics.md" ]] || flle_die "repository root not found"
  [[ "$(pwd -P)" == "$FLLE_JUMP_ROOT" ]] \
    || flle_die "run from ${FLLE_JUMP_ROOT}"
  [[ -r "$FLLE_IDENTITY_FILE" ]] \
    || flle_die "missing course SSH identity: ${FLLE_IDENTITY_FILE}"
  [[ -r "$FLLE_SSH_KNOWN_HOSTS" ]] \
    || flle_die "missing pinned SSH host keys: ${FLLE_SSH_KNOWN_HOSTS}"
  for command_name in ssh scp sha256sum timeout; do
    command -v "$command_name" >/dev/null \
      || flle_die "missing local command: ${command_name}"
  done
}

flle_new_run() {
  local slug="$1"
  FLLE_RUN_ID="$(date -u +'%Y%m%dT%H%M%SZ')-${slug}"
  FLLE_EVIDENCE_DIR="${FLLE_JUMP_ROOT}/reports/course-runs/${FLLE_RUN_ID}"
  mkdir -p "$FLLE_EVIDENCE_DIR/raw" "$FLLE_EVIDENCE_DIR/derived"
  printf 'RUN_ID=%s\nSLUG=%s\nSTART_UTC=%s\n' \
    "$FLLE_RUN_ID" "$slug" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    >"${FLLE_EVIDENCE_DIR}/run.env"
  export FLLE_RUN_ID FLLE_EVIDENCE_DIR
  flle_note "RUN_ID=${FLLE_RUN_ID}"
}

flle_assert_ip() {
  case "$1" in
    "$FLLE_VM1"|"$FLLE_VM2"|"$FLLE_VM11"|"$FLLE_VM101"|"$FLLE_ARISTA") ;;
    *) flle_die "refusing unknown target: $1" ;;
  esac
}

flle_ssh_root() {
  local host="$1"
  shift
  flle_assert_ip "$host"
  [[ "$host" != "$FLLE_ARISTA" ]] || flle_die "use EOS helper for the switch"
  ssh "${FLLE_SSH_OPTS[@]}" "root@${host}" "$@"
}

flle_copy_to_root() {
  local host="$1"
  local source_path="$2"
  local target_path="$3"
  flle_assert_ip "$host"
  [[ "$host" != "$FLLE_ARISTA" ]] || flle_die "SCP to EOS is not a course path"
  scp "${FLLE_SSH_OPTS[@]}" "$source_path" "root@${host}:${target_path}"
}

flle_copy_from_root() {
  local host="$1"
  local source_path="$2"
  local target_path="$3"
  flle_assert_ip "$host"
  [[ "$host" != "$FLLE_ARISTA" ]] || flle_die "SCP from EOS is not a course path"
  scp "${FLLE_SSH_OPTS[@]}" "root@${host}:${source_path}" "$target_path"
}

flle_capture_root() {
  local host="$1"
  local output_file="$2"
  shift 2
  flle_ssh_root "$host" "$@" >"$output_file" 2>&1
}

flle_assert_vm_identity() {
  local host="$1"
  local expected_mgmt="$2"
  local expected_data="$3"
  flle_capture_root "$host" "${FLLE_EVIDENCE_DIR}/raw/${host}-identity.txt" \
    bash -s -- "$expected_mgmt" "$expected_data" <<'REMOTE'
set -Eeuo pipefail
expected_mgmt="$1"
expected_data="$2"
id -u | grep -Fxq 0
ip -4 -o addr show dev ens33 | grep -Fq " ${expected_mgmt}/"
ip route show default | grep -Eq 'dev ens33( |$)'
ip -4 -o addr show | grep -Fq " ${expected_data}/"
printf 'VM_IDENTITY_OK mgmt=%s data=%s host=%s\n' \
  "$expected_mgmt" "$expected_data" "$(hostname)"
REMOTE
  grep -Fq 'VM_IDENTITY_OK' "${FLLE_EVIDENCE_DIR}/raw/${host}-identity.txt" \
    || flle_die "identity gate failed for ${host}"
}

flle_assert_key_access() {
  local host
  for host in "$@"; do
    flle_note "checking public-key SSH: ${host}"
    flle_ssh_root "$host" true \
      || flle_die "public-key SSH failed: root@${host}"
  done
}

flle_finish() {
  local marker="$1"
  printf 'END_UTC=%s\nFINAL_MARKER=%s\n' \
    "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$marker" \
    >>"${FLLE_EVIDENCE_DIR}/run.env"
  (cd "$FLLE_EVIDENCE_DIR" && find . -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum >SHA256SUMS)
  printf '%s run_id=%s evidence=%s\n' "$marker" "$FLLE_RUN_ID" "$FLLE_EVIDENCE_DIR"
}
