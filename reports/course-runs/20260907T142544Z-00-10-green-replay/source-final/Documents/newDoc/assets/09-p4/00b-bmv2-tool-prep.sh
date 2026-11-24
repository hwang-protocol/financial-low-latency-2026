#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-bmv2-tool-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
python3 Documents/newDoc/assets/common/install-offline-packages.py 10.1.1.11 bmv2 2>&1 | tee "$OUT/raw/result.txt"
ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 bash -s <<'REMOTE' 2>&1 | tee -a "$OUT/raw/result.txt"
set -Eeuo pipefail
printf '%s\n' '' '10.1.1.11 / verify' '===== 查软件交换机版本 =====' '[BMv2] 对: 1.15.0-68f4a978  证: 直接接线主机具备执行 P4 JSON 的工具' '$ simple_switch --version'; simple_switch --version 2>&1
printf '%s\n' '' '10.1.1.11 / verify' '===== 查Thrift 客户端路径 =====' '[CLI] 对: /usr/bin/simple_switch_CLI  证: 可通过 9090 控制本章 BMv2 的表和寄存器' '$ command -v simple_switch_CLI'; command -v simple_switch_CLI
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
