#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-link-pair"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
{
# 主机侧：保留完整输出，课堂只显示链路字段
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n%s / verify · %s\n===== 查主机侧链路 =====\n' "$host" "$data_if"
  printf '[链路] 对: 10000Mb/s、Full、yes  证: 本端检测到 10G 全双工链路\n[端口类别] 看: Port 是当前驱动报告的类别，需结合交换机 Type 判断介质\n$ ethtool %s\n' "$data_if"
  if ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "ethtool '$data_if'" >"$OUT/raw/host-$host.txt" 2>&1; then
    sed -n -E '/^[[:space:]]*(Speed|Duplex|Port|Link detected):/p' "$OUT/raw/host-$host.txt"
  else
    rc=$?; tail -n 20 "$OUT/raw/host-$host.txt"; printf '完整输出：%s\n' "$OUT/raw/host-$host.txt"; exit "$rc"
  fi
done
# 交换机侧：一次连接查询三项，在每条命令前加入对应说明
printf '%s\n' 'show interfaces Ethernet1 status' \
  'show interfaces Ethernet2 status' 'show vlan id 20' >"$OUT/eos.plan"
printf '\n10.1.1.253 / verify\n'
if python3 Documents/newDoc/assets/common/eos_cli.py --mode show \
  --plan "$OUT/eos.plan" --output "$OUT/raw/arista-links.txt" >"$OUT/raw/arista-terminal.txt" 2>&1; then
  awk '
    /^\$ show interfaces Ethernet[12] status$/ {
      port=($4=="Ethernet1" ? "Et1" : "Et2")
      print "===== 查交换机 " port " 链路 ====="
      print "[端口] 对: connected、20、full、10G  证: 已连接并接入 VLAN20，使用 10G 全双工"
    }
    /^\$ show vlan id 20$/ {
      print "===== 查 VLAN20 活动端口 ====="
      print "[VLAN] 对: active，包含 Et1、Et2  证: VLAN20 已启用，两条数据链路处于活动状态"
    }
    { print }
  ' "$OUT/raw/arista-links.txt"
else
  rc=$?; tail -n 20 "$OUT/raw/arista-terminal.txt"; printf '完整输出：%s\n' "$OUT/raw/arista-terminal.txt"; exit "$rc"
fi
} 2>&1 | tee "$OUT/classroom.txt"
(cd "$OUT" && sha256sum raw/* run.env eos.plan classroom.txt >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
