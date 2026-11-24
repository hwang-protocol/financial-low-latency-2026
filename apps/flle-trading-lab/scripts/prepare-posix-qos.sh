#!/usr/bin/env bash
# Chapter 02: prepare comparison clients; preserve v13 and ordinary trading.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd -- "$APP_DIR/../.." && pwd)"
RUN_ID="${1:?platform RUN_ID required}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || exit 2
case "${2:-}" in ''|--check) ;; *) exit 2;; esac
RUN_DIR="/var/tmp/flle-trading-lab-$RUN_ID"
ARCHIVE="$REPO_ROOT/artifacts/blobs/x2522/ch05-four-path/posix-qos-v1/flle-posix-qos-v1-x86_64-jammy.tgz"
python3 "$SCRIPT_DIR/posix-qos-package.py" verify-archive "$ARCHIVE"
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2)
SCP=(scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes)
check_installed(){
  "${SSH[@]}" python3 - "$RUN_DIR" < <(cat <<'PY'
import sys
from pathlib import Path
run = Path(sys.argv[1])
sys.path.insert(0, str(run/'control/apps/flle-trading-lab'))
from flle_trading.posix_qos import runtime_root
assert (run/'posix-qos.enabled').read_text().strip() == 'POSIX_QOS_V1'
assert runtime_root(run) == run/'posix-runtime/flle-posix-qos-v1'
PY
  ) || return
  (cd "$REPO_ROOT"; sha256sum apps/flle-trading-lab/scripts/*.sh \
    apps/flle-trading-lab/scripts/*.py apps/flle-trading-lab/flle_trading/*.py) |
    "${SSH[@]}" "cd '$RUN_DIR/control'; sha256sum --quiet -c -"
}
if check_installed >/dev/null 2>&1; then
  echo 'posix_client=PREPARED default_dscp=0'; exit 0
fi
if test "${2:-}" = --check; then
  echo '测试客户端尚未备齐。请在 .111 补跑：' >&2
  echo 'bash assets/02-trading-baseline/01-restore-trading-lab.sh' >&2
  exit 2
fi
STAGE="$("${SSH[@]}" "test -d '$RUN_DIR'; mktemp -d '$RUN_DIR/.posix-qos-prep.XXXXXX'")"
[[ "$STAGE" = "$RUN_DIR"/.posix-qos-prep.* ]] || exit 2
cleanup(){ "${SSH[@]}" "rm -rf -- '$STAGE'"; }
trap cleanup EXIT
"${SSH[@]}" "mkdir -p '$STAGE/control/apps/flle-trading-lab/scripts' '$STAGE/control/apps/flle-trading-lab/flle_trading'"
"${SCP[@]}" "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.py "root@10.1.1.2:$STAGE/control/apps/flle-trading-lab/scripts/"
"${SCP[@]}" "$APP_DIR"/flle_trading/*.py "root@10.1.1.2:$STAGE/control/apps/flle-trading-lab/flle_trading/"
"${SCP[@]}" "$ARCHIVE" "root@10.1.1.2:$STAGE/client.tgz"
"${SSH[@]}" bash -s -- "$RUN_DIR" "$STAGE" <<'REMOTE'
set -Eeuo pipefail
run="$1"; stage="$2"
checker="$stage/control/apps/flle-trading-lab/scripts/posix-qos-package.py"
python3 "$checker" verify-archive "$stage/client.tgz"
mkdir "$stage/package"
tar xzf "$stage/client.tgz" -C "$stage/package"
python3 "$checker" verify-root "$stage/package/flle-posix-qos-v1"
(cd "$stage/control"; find apps -type f -print0 | sort -z | xargs -0 sha256sum >MANIFEST.sha256)
# Share the physical device lock with every path switch and measurement.
exec 8>/run/lock/flle-transport-0000_03_00_0.lock
flock -w 30 8 || { echo '平台正忙，请等测试或网卡切换完成。' >&2; exit 75; }
export FLLE_TRANSPORT_LOCK_HELD=1
old="$run/control/apps/flle-trading-lab/scripts/transport_labctl.sh"
test -f "$old"
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
unit="flle-transport-controller-${run##*/flle-trading-lab-}"
unit="${unit//_/-}"
restart_controller=0
systemctl is-active --quiet "$unit" && restart_controller=1
# A missing package may be added to the Chapter 04 software snapshot. Do not
# invalidate receipts of an already-running legacy comparison client.
if ! test -s "$run/posix-qos.enabled" &&
   grep -Fxq TRANSPORT "/var/tmp/flle-transport-controller-${run##*/flle-trading-lab-}/experiment-profile"; then
  echo '请从第四章结束的普通交易快照补齐软件，再进入第五章。' >&2; exit 2
fi
had_marker=0
if test -f "$run/posix-qos.enabled"; then
  cp "$run/posix-qos.enabled" "$stage/marker-before"
  had_marker=1
fi
rollback(){
  local rc=$?
  trap - ERR
  set +e
  if test -d "$stage/control-before"; then
    if test -d "$run/control"; then mv "$run/control" "$stage/control-failed"; fi
    mv "$stage/control-before" "$run/control"
  fi
  if test "$had_marker" -eq 1; then cp "$stage/marker-before" "$run/posix-qos.enabled"
  else rm -f "$run/posix-qos.enabled"; fi
  if test "$restart_controller" -eq 1; then
    bash "$run/control/apps/flle-trading-lab/scripts/transport_labctl.sh" controller-start "${run##*/flle-trading-lab-}" || {
      echo '控制器恢复失败；保留已有交易进程，请查看本步日志。' >&2; exit 125;
    }
  fi
  exit "$rc"
}
trap rollback ERR
# Stop the controller using its existing manifest before replacing its workspace.
bash "$old" controller-stop "${run##*/flle-trading-lab-}"
mkdir -p "$run/posix-runtime"
if test -d "$run/posix-runtime/flle-posix-qos-v1"; then
  python3 "$checker" verify-root "$run/posix-runtime/flle-posix-qos-v1"
else
  mv "$stage/package/flle-posix-qos-v1" "$run/posix-runtime/"
fi
# Keep the old workspace available until the validated replacement is in place.
mv "$run/control" "$stage/control-before"
if ! mv "$stage/control" "$run/control"; then
  mv "$stage/control-before" "$run/control"
  exit 1
fi
printf 'POSIX_QOS_V1\n' >"$run/posix-qos.enabled.tmp"
mv "$run/posix-qos.enabled.tmp" "$run/posix-qos.enabled"
if test "$restart_controller" -eq 1; then
  bash "$run/control/apps/flle-trading-lab/scripts/transport_labctl.sh" controller-start "${run##*/flle-trading-lab-}"
fi
printf 'posix_client=INSTALLED default_dscp=0\n'
printf 'preserved=v13 runtime, Exchange, GUI, Chapter 04 software client\n'
trap - ERR
REMOTE
