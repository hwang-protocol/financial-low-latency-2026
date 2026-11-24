#!/usr/bin/env bash
# 在交易系统保持在线的前提下，用网卡硬件时间戳直接测一次单向延时。
#
# 路径：.1 Exchange / X2522 -> Et1 -> 7150 (cut-through) -> Et2 -> .2 Trader / X2522
# 本卡不修改交换机任何配置，也不停止第 05 章交易系统；只在两端临时打开网卡硬件
# 打戳、发一批小帧、按 seq 配对相减，结束后把打戳开关还原。
#
# 两档对照：nosync 档不启动任何 PTP 进程，ptp 档启动 ptp4l 主从。本实验台两端
# 是同一块双口 X2522 的两个端口，时基天生一致，两档结果应当接近；这正是正文
# 那句边界说明的证据。
set -Eeuo pipefail
cd /qyt-fll

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-oneway-latency"
OUT="reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
DERIVED="$OUT/derived"
COMMON="assets/common"
ASSET_ROOT="assets/06-arista-time"
SUPPORT="$ASSET_ROOT/live-support/oneway"
PTP_SUPPORT="$ASSET_ROOT/live-support/ptp"
SUPPORT_MANIFEST="$ASSET_ROOT/LIVE-SUPPORT-SHA256SUMS"
REMOTE_DIR="/root/flle-oneway-live-$RUN_ID"
TMP="$(mktemp -d)"
REMOTE_DEPLOYED=0
ACTIVE_STAGE=''

FRAME_COUNT="${FRAME_COUNT:-2000}"
PAYLOAD_BYTES="${PAYLOAD_BYTES:-64}"
SEND_GAP_S="${SEND_GAP_S:-0.001}"
UDP_PORT="${UDP_PORT:-30001}"
GUI_URL="http://10.1.1.101:8088/api/state"

test ! -e "$OUT"
mkdir -p "$RAW" "$DERIVED"
SUPPORT_MANIFEST_SHA256="$(sha256sum "$SUPPORT_MANIFEST" | awk '{print $1}')"
printf 'RUN_ID=%s\nRESULT_KIND=FRESH_LIVE_MEASUREMENT\nSUPPORT_MANIFEST_SHA256=%s\nTRADING_ONLINE=1\n' \
  "$RUN_ID" "$SUPPORT_MANIFEST_SHA256" >"$OUT/run.env"
install -m 0644 "$SUPPORT_MANIFEST" "$RAW/LIVE-SUPPORT-SHA256SUMS"
(cd "$ASSET_ROOT" && sha256sum -c LIVE-SUPPORT-SHA256SUMS) \
  >"$RAW/local-support-sha256.txt"

# 记录进场前的打戳开关，收尾按这个值还原，而不是写死 0/0。
declare -A BASE_TX BASE_RX
for spec in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host iface <<<"$spec"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "/usr/sbin/hwstamp_ctl -i '$iface'" >"$RAW/hwstamp-baseline-$host.txt"
  BASE_TX[$host]="$(awk '/tx_type/{print $2; exit}' "$RAW/hwstamp-baseline-$host.txt")"
  BASE_RX[$host]="$(awk '/rx_filter/{print $2; exit}' "$RAW/hwstamp-baseline-$host.txt")"
done

remote_cleanup() {
  local host="$1" role="$2" iface="$3"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "/usr/bin/bash '$REMOTE_DIR/cleanup-oneway-node.sh' '$iface' '$REMOTE_DIR/$role-ptp.pid' '${BASE_TX[$host]}' '${BASE_RX[$host]}' '$REMOTE_DIR/$role-cleanup.log' '$RUN_ID-$role'" \
    >/dev/null 2>&1
}

cleanup() {
  local original_rc=$? cleanup_failed=0
  trap - EXIT INT TERM HUP
  set +e
  if test "$REMOTE_DEPLOYED" -eq 1; then
    remote_cleanup 10.1.1.1 master ens64np0 || cleanup_failed=1
    remote_cleanup 10.1.1.2 client ens64np1 || cleanup_failed=1
  fi
  find "$TMP" -depth -delete
  if test "$cleanup_failed" -ne 0; then
    printf 'ONEWAY_CLEANUP=FAIL original_rc=%s\n' "$original_rc" >&2
    exit 125
  fi
  if test "$original_rc" -ne 0; then exit "$original_rc"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# 前置门：两端必须无任何同步进程残留，网卡在位、数据口通。交易系统保持在线，
# 因此这里不检查大页，也不要求 Onload 栈为空。
for spec in '10.1.1.1 ens64np0 20.1.1.1/24 20.1.1.2' \
            '10.1.1.2 ens64np1 20.1.1.2/24 20.1.1.1'; do
  read -r host iface data_ip peer <<<"$spec"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; test -x /usr/sbin/ptp4l; test -x /usr/sbin/hwstamp_ctl; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 addr show dev '$iface' | grep -Fq '$data_ip'; for p in ptp4l phc2sys ts2phc sfptpd; do pgrep -x \"\$p\" >/dev/null && exit 1 || :; done; test -c /dev/ptp0; ethtool -T '$iface'; ping -q -I '$iface' -c 3 -W 1 '$peer'" \
    >"$RAW/preflight-$host.txt"
done

# 交易系统必须在进场前就是健康的，收尾还要再验一次。
curl -sf -m 5 "$GUI_URL" >"$RAW/trading-before.json"
python3 - "$RAW/trading-before.json" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
assert x["data_plane_mode"] == "SFC", x
assert x["data_plane_transition"] == "READY", x
assert x["data_plane_owner"] == "sfc", x
PY

install -m 0755 "$SUPPORT/cleanup-oneway-node.sh" "$TMP/cleanup-oneway-node.sh"
install -m 0644 "$SUPPORT/oneway_rx.py" "$TMP/oneway_rx.py"
install -m 0644 "$SUPPORT/oneway_tx.py" "$TMP/oneway_tx.py"
install -m 0644 "$PTP_SUPPORT/ptp-master.cfg" "$TMP/ptp-master.cfg"
install -m 0644 "$PTP_SUPPORT/ptp-client.cfg" "$TMP/ptp-client.cfg"
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; test ! -e '$REMOTE_DIR'; mkdir -m 700 '$REMOTE_DIR'"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "$TMP/cleanup-oneway-node.sh" "$TMP/oneway_rx.py" "$TMP/oneway_tx.py" \
    "$TMP/ptp-master.cfg" "$TMP/ptp-client.cfg" "root@$host:$REMOTE_DIR/"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "chmod 700 '$REMOTE_DIR/cleanup-oneway-node.sh'"
done
REMOTE_DEPLOYED=1

sample_market_pps() {
  # 交易系统在线，这里量化行情竞争强度，供正文写清尾部数字的边界。
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    'a=$(cat /sys/class/net/ens64np1/statistics/rx_packets); sleep 2; b=$(cat /sys/class/net/ens64np1/statistics/rx_packets); echo $(( (b-a)/2 ))'
}

start_ptp4l() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    "set -eu; cd '$REMOTE_DIR'; nohup /usr/sbin/ptp4l -f '$REMOTE_DIR/ptp-master.cfg' -i ens64np0 -m -q >'$REMOTE_DIR/master-ptp4l.log' 2>&1 & echo \$! >'$REMOTE_DIR/master-ptp.pid'"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "set -eu; cd '$REMOTE_DIR'; nohup /usr/sbin/ptp4l -f '$REMOTE_DIR/ptp-client.cfg' -i ens64np1 -m -q -s >'$REMOTE_DIR/client-ptp4l.log' 2>&1 & echo \$! >'$REMOTE_DIR/client-ptp.pid'"
  local slave=0
  for _ in $(seq 1 120); do
    if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
        "grep -Fq 'INITIALIZING to LISTENING' '$REMOTE_DIR/client-ptp4l.log' && grep -Eq 'UNCALIBRATED to SLAVE|LISTENING to SLAVE' '$REMOTE_DIR/client-ptp4l.log'" 2>/dev/null; then
      slave=1
      break
    fi
    sleep 0.5
  done
  test "$slave" -eq 1
  # 进入 SLAVE 后再等 servo 收敛几秒，避免拿到还在拉偏的样本。
  sleep 10
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "/usr/sbin/pmc -u -b 0 -d 24 'GET CURRENT_DATA_SET'" >"$RAW/ptp-client-pmc.txt"
}

run_stage() {
  local stage="$1" use_ptp="$2" pps_before rx_pid
  ACTIVE_STAGE="$stage"

  if test "$use_ptp" = yes; then
    start_ptp4l
  else
    # 不跑 PTP 时要自己打开硬件打戳；跑 PTP 时 ptp4l 已经打开。
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
      "/usr/sbin/hwstamp_ctl -i ens64np0 -t 1 -r 1" >"$RAW/$stage-hwstamp-master.txt"
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
      "/usr/sbin/hwstamp_ctl -i ens64np1 -t 1 -r 1" >"$RAW/$stage-hwstamp-client.txt"
  fi

  pps_before="$(sample_market_pps)"
  printf '%s\n' "$pps_before" >"$RAW/$stage-market-rx-pps.txt"

  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "cd '$REMOTE_DIR' && env LISTEN_IP=20.1.1.2 LISTEN_PORT=$UDP_PORT EXPECT_COUNT=$FRAME_COUNT IDLE_TIMEOUT_S=15 OUT_PATH='$REMOTE_DIR/$stage-rx.jsonl' READY_MARKER='$REMOTE_DIR/$stage-rx.ready' python3 oneway_rx.py" \
    >"$RAW/$stage-rx.txt" 2>&1 &
  rx_pid=$!

  local ready=0
  for _ in $(seq 1 60); do
    if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
        "test -s '$REMOTE_DIR/$stage-rx.ready'" 2>/dev/null; then
      ready=1
      break
    fi
    kill -0 "$rx_pid" 2>/dev/null
    sleep 0.25
  done
  test "$ready" -eq 1

  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    "cd '$REMOTE_DIR' && env SRC_IP=20.1.1.1 DEST_IP=20.1.1.2 DEST_PORT=$UDP_PORT FRAME_COUNT=$FRAME_COUNT PAYLOAD_BYTES=$PAYLOAD_BYTES SEND_GAP_S=$SEND_GAP_S DRAIN_TIMEOUT_S=20 OUT_PATH='$REMOTE_DIR/$stage-tx.jsonl' python3 oneway_tx.py" \
    >"$RAW/$stage-tx.txt" 2>&1
  wait "$rx_pid"

  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.1:$REMOTE_DIR/$stage-tx.jsonl" "$RAW/$stage-tx.jsonl"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.2:$REMOTE_DIR/$stage-rx.jsonl" "$RAW/$stage-rx.jsonl"

  if test "$use_ptp" = yes; then
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@10.1.1.2:$REMOTE_DIR/client-ptp4l.log" "$RAW/ptp-client.ptp4l.log"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@10.1.1.1:$REMOTE_DIR/master-ptp4l.log" "$RAW/ptp-master.ptp4l.log"
  fi

  python3 "$SUPPORT/analyze_oneway.py" "$RAW/$stage-tx.jsonl" "$RAW/$stage-rx.jsonl" \
    >"$DERIVED/$stage-oneway.json"
  python3 - "$DERIVED/$stage-oneway.json" "$FRAME_COUNT" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
want = int(sys.argv[2])
assert x["paired_count"] >= want * 0.99, x
assert x["one_way_ns"]["p50"] > 0, x
PY

  remote_cleanup 10.1.1.1 master ens64np0
  remote_cleanup 10.1.1.2 client ens64np1
  ACTIVE_STAGE=''
}

run_stage nosync no
run_stage ptp yes

# 收尾复核：两端无同步进程残留、打戳开关已还原、链路通、交易系统仍然健康。
for spec in '10.1.1.1 ens64np0 20.1.1.2' '10.1.1.2 ens64np1 20.1.1.1'; do
  read -r host iface peer <<<"$spec"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; for p in ptp4l phc2sys ts2phc sfptpd; do pgrep -x \"\$p\" >/dev/null && exit 1 || :; done; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; /usr/sbin/hwstamp_ctl -i '$iface'; ping -q -I '$iface' -c 3 -W 1 '$peer'" \
    >"$RAW/final-$host.txt"
  grep -Fq "tx_type ${BASE_TX[$host]}" "$RAW/final-$host.txt"
  grep -Fq "rx_filter ${BASE_RX[$host]}" "$RAW/final-$host.txt"
done

curl -sf -m 5 "$GUI_URL" >"$RAW/trading-after.json"
python3 - "$RAW/trading-after.json" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
assert x["data_plane_mode"] == "SFC", x
assert x["data_plane_transition"] == "READY", x
assert x["data_plane_owner"] == "sfc", x
PY

REMOTE_DEPLOYED=0
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; case '$REMOTE_DIR' in /root/flle-oneway-live-*-07-oneway-latency) ;; *) exit 2;; esac; find '$REMOTE_DIR' -depth -delete; test ! -e '$REMOTE_DIR'"
done

python3 - "$DERIVED/nosync-oneway.json" "$DERIVED/ptp-oneway.json" \
  "$RAW/nosync-market-rx-pps.txt" "$RAW/ptp-market-rx-pps.txt" \
  >"$OUT/result.json" <<'PY'
import json, sys
nosync, ptp = [json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3]]
pps = [int(open(p, encoding="utf-8").read().strip()) for p in sys.argv[3:5]]
print(json.dumps({
    "result": "PASS",
    "evidence_kind": "fresh_live_measurement",
    "trading_online": True,
    "market_rx_pps": {"nosync": pps[0], "ptp": pps[1]},
    "nosync": nosync,
    "ptp": ptp,
    "switch_config_changed": False,
    "shared_adapter_note":
        "两端为同一块双口 X2522 的两个端口，时基天生一致；两档接近属预期，"
        "不得据此宣称 PTP 造成了可比性",
}, ensure_ascii=False, indent=2))
PY
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)

python3 - "$OUT/result.json" "$OUT" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
n, p = x["nosync"]["one_way_ns"], x["ptp"]["one_way_ns"]
print("vm-2522-01 -> 7150 -> vm-2522-02")
print("===== 查配对 =====")
print("[oneway] 对: 发出与收到的帧按 seq 全部配上  证: 每一帧都有两端硬件戳")
print("$ python3 analyze_oneway.py ptp-tx.jsonl ptp-rx.jsonl")
print("paired=%s/%s  unpaired=%s" % (
    x["ptp"]["paired_count"], x["ptp"]["tx_count"], x["ptp"]["unpaired_tx"]))
print("===== 查单向延时 =====")
print("[ptp4l 已进入 SLAVE] 对: p50 在数百纳秒  证: 一帧真正的单程时间")
print("$ cat derived/ptp-oneway.json")
print("one_way_ns  min=%s  p50=%s  p99=%s  max=%s" % (
    p["min"], p["p50"], p["p99"], p["max"]))
print("===== 查对照 =====")
print("[未启动 PTP] 对: 与上一档接近  证: 本机两端共用同一块网卡时基")
print("$ cat derived/nosync-oneway.json")
print("one_way_ns  min=%s  p50=%s  p99=%s  max=%s" % (
    n["min"], n["p50"], n["p99"], n["max"]))
print("===== 查现场边界 =====")
print("market_rx_pps nosync=%s ptp=%s  switch_config_changed=%s" % (
    x["market_rx_pps"]["nosync"], x["market_rx_pps"]["ptp"],
    x["switch_config_changed"]))
print("evidence=" + sys.argv[2])
PY
