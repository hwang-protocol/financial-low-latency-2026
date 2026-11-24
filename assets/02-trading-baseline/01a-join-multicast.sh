#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
TOOLS=assets/02-trading-baseline
source reports/run-state/02-trading-baseline.env
BASE_RUN_ID="$RUN_ID"; RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-igmp-join"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nBASE_RUN_ID=%s\n' "$RUN_ID" "$BASE_RUN_ID" >"$OUT/run.env"
CTL=apps/flle-trading-lab/scripts/transport_labctl.sh
{
  printf '10.1.1.2 / join\n===== 确认网卡由 sfc 管理 =====\n$ bash %s status %s\n' "$CTL" "$BASE_RUN_ID"
  bash "$CTL" status "$BASE_RUN_ID" >"$OUT/raw/status.json"
  check='import json,sys; s=json.load(open(sys.argv[1])); print("mode=%s transition=%s owner=%s" % (s["mode"],s["transition"],s["owner"])); assert (s["mode"],s["transition"],s["owner"]) == ("SFC","READY","sfc")'
  printf '$ python3 -c %q %q\n' "$check" "$OUT/raw/status.json"
  python3 -c "$check" "$OUT/raw/status.json"
  printf '%s\n' '===== 让统一接收器保持组播订阅 =====' '[配置说明] direct 是本项目的接收配置：保留内部单播并订阅 A/B 两组，对应 --multicast-receiver 1，不是网卡直通。' '[范围说明] 本步不切换 Exchange 的行情发送模式；主机加组、交换机学到成员和实际收包分别检查。'
  printf '$ bash %s feed-profile %s direct\n' "$CTL" "$BASE_RUN_ID"
  printf '[接收器原生命令：默认参数已展开，仅展示；已有匹配进程时不重复启动]\n$ %q --data-ip 20.1.1.2 --unicast-port 42121 --multicast-group 233.74.125.32 --multicast-port 31032 --multicast-group-b 233.74.125.33 --multicast-port-b 31033 --multicast-source 20.1.1.1 --multicast-receiver 1 --receive-buffer-bytes 4194304 --client-queue-bytes 8388608 --client-queue-packets 32768 --telemetry-host 10.1.1.101 --socket %q\n' "$RUN_DIR/flle-feed-receiver" "$RUN_DIR/feed.sock"
  bash "$CTL" feed-profile "$BASE_RUN_ID" direct
  printf '===== 查 Trader 数据口加入了哪些组 =====\n[成员] 对: inet 233.74.125.32 与 inet 233.74.125.33，各有一个订阅  证: 加组发生在 ens64np1\n$ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 ip maddr show dev ens64np1\n'
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'ip maddr show dev ens64np1' | tee "$OUT/raw/membership.txt"
  printf '===== 查主机组播源过滤 =====\n[源过滤] 核对 A、B 两组的来源均为 20.1.1.1；INC 是包含该源的引用数，EXC 是排除该源的引用数。\n$ ssh root@10.1.1.2 cat /proc/net/mcfilter\n'
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'cat /proc/net/mcfilter' | tee "$OUT/raw/mcfilter.txt"
  printf '[接口编号] 旧内核可能缩短 Device 名称，按 Idx 对应 ens64np1。\n$ ssh root@10.1.1.2 cat /sys/class/net/ens64np1/ifindex\n'
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'cat /sys/class/net/ens64np1/ifindex' | tee "$OUT/raw/data-ifindex.txt"
  printf '[地址读法] 将上面的十六进制地址转为 IP；这是主机记录，不是交换机按源转发的证明。\n$ python3 %s/format-mcfilter.py %q %q ens64np1\n' "$TOOLS" "$OUT/raw/mcfilter.txt" "$OUT/raw/data-ifindex.txt"
  python3 "$TOOLS/format-mcfilter.py" "$OUT/raw/mcfilter.txt" "$OUT/raw/data-ifindex.txt" ens64np1
} 2>&1 | tee "$OUT/raw/classroom.txt"
sha256sum "$TOOLS/01a-join-multicast.sh" "$TOOLS/format-mcfilter.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
