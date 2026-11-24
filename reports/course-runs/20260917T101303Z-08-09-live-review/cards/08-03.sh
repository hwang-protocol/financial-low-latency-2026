#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-trading-bridge-compile"
OUT="Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
SRC=Documents/newDoc/assets/08-p4
NVDA_SOURCE_SHA="$(sha256sum "$SRC/trading_bridge_nvda_drop.p4" | awk '{print $1}')"
mkdir -p "$OUT/raw" "$OUT/artifacts"; printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
printf 'NVDA_SOURCE_SHA256=%s\n' "$NVDA_SOURCE_SHA" >>"$OUT/run.env"
cleanup(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "find '$REMOTE' -type f -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"; }
trap cleanup EXIT
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "mkdir '$REMOTE'"
scp -q "${FLLE_SSH_OPTS[@]}" "$SRC/trading_l2_bridge.p4" "$SRC/trading_bridge_itch_count.p4" "$SRC/trading_bridge_nvda_drop.p4" root@10.1.1.101:"$REMOTE/"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "set -Eeuo pipefail; cd '$REMOTE'; printf '%s\\n' '' 'Low-Latency-Ops / build' '===== 查编译三份 P4 程序 =====' '[p4c-bm2-ss] 对: 各生成 JSON 与 P4Info  证: --p4v 16 选择 P4-16；JSON 给 BMv2，P4Info 描述控制对象' '\$ p4c-bm2-ss --p4v 16 --p4runtime-files <name>.p4info.txt -o <name>.json <name>.p4'; for name in trading_l2_bridge trading_bridge_itch_count trading_bridge_nvda_drop; do p4c-bm2-ss --p4v 16 --p4runtime-files \"\$name.p4info.txt\" -o \"\$name.json\" \"\$name.p4\"; done; printf '%s\\n' '' 'Low-Latency-Ops / build' '===== 查生成文件与大小 =====' '[制品] 对: 三份 JSON 和三份 P4Info  证: 确认文件落盘；大小不代表转发性能' '\$ ls -lh trading_*'; ls -lh trading_*; printf '%s\\n' '' 'Low-Latency-Ops / build' '===== 查P4 源码与制品指纹 =====' '[SHA-256] 对: 源码、JSON、P4Info 各有指纹  证: 核对编译、复制和后续加载是否使用同一制品' '\$ sha256sum trading_*'; sha256sum trading_*" 2>&1 | tee "$OUT/raw/compile.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE/trading_l2_bridge.json" root@10.1.1.101:"$REMOTE/trading_l2_bridge.p4info.txt" root@10.1.1.101:"$REMOTE/trading_bridge_itch_count.json" root@10.1.1.101:"$REMOTE/trading_bridge_itch_count.p4info.txt" root@10.1.1.101:"$REMOTE/trading_bridge_nvda_drop.json" root@10.1.1.101:"$REMOTE/trading_bridge_nvda_drop.p4info.txt" "$OUT/artifacts/"
printf 'NVDA_JSON_SHA256=%s\n' "$(sha256sum "$OUT/artifacts/trading_bridge_nvda_drop.json" | awk '{print $1}')" >>"$OUT/run.env"
(cd "$OUT" && sha256sum raw/* artifacts/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
