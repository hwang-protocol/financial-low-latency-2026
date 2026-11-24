#!/usr/bin/env bash
# Deploy all course trading capabilities once; later chapters only select profiles.
set -Eeuo pipefail
cd /qyt-fll
REPO_ROOT=/qyt-fll
SELF="$REPO_ROOT/assets/02-trading-baseline/01-restore-trading-lab.sh"
CTL="$REPO_ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh"
CAPABILITIES="$REPO_ROOT/apps/flle-trading-lab/scripts/prepare-course-capabilities.sh"
STATE="$REPO_ROOT/reports/run-state/02-trading-baseline.env"
case "${1:-}" in ""|--upgrade-ab|--prepare-capabilities) ;; *) echo "usage: $0 [--upgrade-ab|--prepare-capabilities]" >&2; exit 2;; esac
exec 9>/run/lock/flle-platform-deploy.lock; flock -n 9
# Keep each command's full stream separate from the classroom transcript.
# Explicitly preserve rc: this function is also used in the reuse branch's if.
stage(){
  local name="$1" purpose="$2" log="$3" rc; shift 3
  printf '\n%s / %s\n===== %s =====\n%s\n$' "$(hostname)" "$name" "$name" "$purpose"
  printf ' %q' "$@"; printf '\n完整输出：%s\n' "$log"
  if "$@" >"$log" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then
    printf '命令失败，退出码 %s；以下为日志末尾。\n$ tail -n 20 %q\n' "$rc" "$log"
    tail -n 20 "$log"
    return "$rc"
  fi
  # Match actual short receipts, never pretty-print or summarize the state JSON.
  local filter='length($0)<=240 && /(^[A-Za-z][A-Za-z0-9_-]*=|: OK$|^Ran [0-9]+ tests|^OK$|tests passed)/ { rows[++n]=$0 } END { for(i=(n>8?n-7:1);i<=n;i++) print rows[i]; if(!n) print "（没有匹配的短读数；请查完整日志）" }'
  printf '关键结果（最多八行）：\n$ awk %q %q\n' "$filter" "$log"
  awk "$filter" "$log"
  case "$name" in
    '① 查部署条件')
      printf '%s\n' '[条件说明] control_assets / builder_tools / transport_preflight 的 PASS 分别对应管理机材料、.101 编译工具和固定运行包检查。' \
        '[条件说明] exchange_rss_preflight 检查 .1 网卡队列与 CPU 分配是否符合部署前提，不是延迟测量结果。' ;;
    '② 查四条路径的构建来源')
      printf '%s\n' '[来源说明] 文件后的 OK 表示摘要与固定清单一致；source_binary_mapping=PASS 表示源码、构建输入和运行文件的来源关系核验通过。' \
        '[来源说明] fstack_config_contract=PASS 表示 DPDK 路径的 F-Stack 配置符合约定，不表示当前已启动 DPDK。' ;;
    '③ 构建并部署平台')
      printf '%s\n' '[部署说明] 复用 B2 准备好的固定运行软件；.101 构建原生客户端并恢复网页服务，.1/.2 建立本次交易会话。' \
        '[部署说明] checkpoint 是回放起点的订单簿检查点；*_sha256 是文件内容摘要，用来核对部署材料，不是性能指标。' ;;
    '④ 启动普通交易配置')
      printf '%s\n' '[启动说明] 本步启动 .1 交易所、.2 行情接收器与交易客户端、.101 网页后台；是否就绪还要看下一步核验。' ;;
    '⑤ 查平台是否就绪'|'查已有平台')
      printf '%s\n' '[进程说明] exchange 是 .1 交易所；trader-auto / trader-manual 是 .2 自动与手动客户端；gateway 是 .101 网页后台。' \
        '[在线说明] ONLINE 表示对应进程在线；pid 是该主机上的进程编号，每次启动可能不同，不是端口号。' \
        '[文件说明] deployed_sha256=PASS 表示所列部署文件摘要核验通过；进程在线与文件一致需要一起看。' \
        '[就绪说明] restore_verdict=TRADING_LAB_READY 表示部署核验通过，不代表已经完成首笔成交或延迟测试。' ;;
  esac
}
if test "${1:-}" = --prepare-capabilities; then
  test -s "$STATE" && test ! -s "$STATE.pending" || {
    echo '缺少完整平台记录，请先完成第二章上线。' >&2; exit 2;
  }
  RUN_ID="$(sed -n 's/^RUN_ID=//p' "$STATE")"
  [[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || exit 2
  OUT="$REPO_ROOT/reports/course-runs/$RUN_ID/capabilities/$(date -u +%Y%m%dT%H%M%S.%NZ)"
  mkdir -p "$OUT"
  {
    stage '查已有平台' '核对当前会话；补齐程序不重建交易所、订单记录或普通客户端。' "$OUT/before.txt" bash "$CTL" verify "$RUN_ID"
    stage '准备后续实验程序' '从 .111 分发已编译程序，沿用第四章快照的交易会话。' "$OUT/prepare.txt" bash "$CAPABILITIES" "$RUN_ID"
    stage '查已有平台' '确认补齐软件后当前交易配置仍可用。' "$OUT/after.txt" bash "$CTL" verify "$RUN_ID"
    stage '启用开机恢复' '启用交易客户端上的持久服务；关机再开机会等待其它主机并恢复本平台。' "$OUT/autostart.txt" bash "$CTL" boot-enable "$RUN_ID"
    echo 'course_capabilities=PREPARED existing_session=PRESERVED'
    echo '[下一步] 按第五章准备 A、B 继续；准备 B 只切换测试配置。'
  } 2>&1 | tee "$OUT/result.txt"
  sha256sum "$SELF" "$CAPABILITIES" "$OUT/"*.txt >"$OUT/SHA256SUMS"
  echo "evidence=$OUT"
  exit
fi
if test -s "$STATE.pending"; then
  PENDING_RUN="$(sed -n 's/^RUN_ID=//p' "$STATE.pending")"
  [[ "$PENDING_RUN" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]]
  PENDING_OUT="$REPO_ROOT/reports/course-runs/$PENDING_RUN"
  recovery="$PENDING_OUT/raw/interrupted-cleanup-$(date -u +%Y%m%dT%H%M%S.%NZ)"
  stage '恢复中断部署' '按已保存的 RUN 停止残留进程，成功后才能重新部署。' "$recovery.txt" bash "$CTL" stop "$PENDING_RUN" 2>&1 | tee "$recovery-classroom.txt"
  mv "$STATE.pending" "$PENDING_OUT/aborted-deploy.env"
fi
if test -s "$STATE"; then
  OLD_RUN_ID="$(sed -n 's/^RUN_ID=//p' "$STATE")"
  case "$OLD_RUN_ID" in
    *-02-trading-platform)
      reuse="$REPO_ROOT/reports/course-runs/$OLD_RUN_ID/raw/reuse-$(date -u +%Y%m%dT%H%M%S.%NZ)"
      if stage '查已有平台' '先核对进程与文件，再判断是否需要升级 A/B。' "$reuse.txt" bash "$CTL" verify "$OLD_RUN_ID" --allow-legacy-market 2>&1 | tee "$reuse-classroom.txt"; then
        if curl -fsS --max-time 10 http://10.1.1.101:8088/api/state | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("market_network",{}).get("market_schema")=="udp-multicast-ab-v1" else 1)' &&
          ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 python3 - "/var/tmp/flle-trading-lab-$OLD_RUN_ID" 1 < "$REPO_ROOT/apps/flle-trading-lab/scripts/verify-feed-receiver.py"; then
          stage '准备后续实验程序' '补齐并核对后续路径测试与 LANZ 所需程序。' "$reuse-capabilities.txt" bash "$CAPABILITIES" "$OLD_RUN_ID" 2>&1 | tee "$reuse-capabilities-classroom.txt"
          stage '查已有平台' '补齐后再次核对当前交易配置。' "$reuse-after.txt" bash "$CTL" verify "$OLD_RUN_ID" 2>&1 | tee "$reuse-after-classroom.txt"
          stage '启用开机恢复' '为已有平台补齐开机恢复，不改变当前交易会话。' "$reuse-autostart.txt" bash "$CTL" boot-enable "$OLD_RUN_ID" 2>&1 | tee "$reuse-autostart-classroom.txt"
          echo "platform=ALREADY_DEPLOYED run_id=$OLD_RUN_ID"
          printf '%s\n' '[复用说明] 已有 A/B 平台通过核验，沿用当前交易会话。'; exit
        fi
        if test "${1:-}" != --upgrade-ab; then
          echo '当前平台未通过完整 A/B 接收器核验。执行本脚本并加 --upgrade-ab：停止旧会话、保留记录，部署新平台。' >&2; exit 2
        fi
        stage '升级 A/B 平台' '停止已核验的旧会话；保留原始记录，新平台从开盘重新回放。' "$reuse-upgrade.txt" bash "$CTL" stop "$OLD_RUN_ID" 2>&1 | tee "$reuse-upgrade-classroom.txt"
      fi
      if test "$(bash "$CTL" reuse-state "$OLD_RUN_ID")" != CLEAN; then
        stage '清理快照控制器' '旧平台未通过核验，按原入口清理快照残留。' "$reuse-retire.txt" bash "$CTL" retire-snapshot-controller "$OLD_RUN_ID" 2>&1 | tee "$reuse-retire-classroom.txt"
      fi
      test "$(bash "$CTL" reuse-state "$OLD_RUN_ID")" = CLEAN
      mv "$STATE" "$REPO_ROOT/reports/course-runs/$OLD_RUN_ID/retired-platform.env"
      ;;
    *-02-trading-baseline)
      legacy="$REPO_ROOT/reports/course-runs/$OLD_RUN_ID/raw/legacy-stop-$(date -u +%Y%m%dT%H%M%S.%NZ)"
      stage '停止旧版平台' '停止旧版进程，再部署完整平台。' "$legacy.txt" bash apps/flle-trading-lab/scripts/labctl.sh stop "$OLD_RUN_ID" 2>&1 | tee "$legacy-classroom.txt" ;;
    *) echo 'Unrecognized platform state; refusing to overwrite it' >&2; exit 2 ;;
  esac
fi
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-trading-platform"
OUT="$REPO_ROOT/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw" "${STATE%/*}"
# Persist identity before the first mutation so interrupted deployment is recoverable.
printf 'RUN_ID=%s\nRUN_DIR=/var/tmp/flle-trading-lab-%s\nWEB_URL=http://10.1.1.101:8088/\nPROFILE=UNIFIED_TRADING_PLATFORM\n' "$RUN_ID" "$RUN_ID" >"$OUT/run.env"
cp "$OUT/run.env" "$STATE.pending"
{
  stage '① 查部署条件' '核对主机、依赖和运行包，确认可以开始部署。' "$OUT/raw/01-preflight.txt" bash "$CTL" preflight "$RUN_ID"
  stage '② 查四条路径的构建来源' '核对固定源码、制品和启动约定，为后续路径比较保留依据。' "$OUT/raw/02-build-contract.txt" bash assets/05-kernel-bypass/four-path-build-contract-audit.sh "$OUT/raw/code-contract"
  stage '③ 构建并部署平台' '使用 B2 已准备的软件建立交易会话，并在监测 VM 构建 A/B Exchange、统一接收器与原生客户端，恢复网页服务。' "$OUT/raw/03-deploy.txt" bash "$CTL" deploy "$RUN_ID"
  stage '准备后续实验程序' '备好路径测试客户端与官方 LANZ 读取工具，后续章节按需启用。' "$OUT/raw/03-capabilities.txt" bash "$CAPABILITIES" "$RUN_ID"
  stage '④ 启动普通交易配置' '启动行情、交易客户端和网页，建立本章下单环境。' "$OUT/raw/04-baseline.txt" bash "$CTL" baseline "$RUN_ID"
  stage '⑤ 查平台是否就绪' '[平台] 对: 进程 ONLINE、部署摘要核验通过  证: 当前平台可以交给首单步骤' "$OUT/raw/05-verify.txt" bash "$CTL" verify "$RUN_ID"
  stage '启用开机恢复' '启用交易客户端上的持久服务；关机再开机会等待其它主机并恢复本平台。' "$OUT/raw/06-autostart.txt" bash "$CTL" boot-enable "$RUN_ID"
} 2>&1 | tee "$OUT/raw/restore.txt"
cp "$OUT/run.env" "$STATE.tmp.$BASHPID"; mv "$STATE.tmp.$BASHPID" "$STATE"
rm -f "$STATE.pending"
sha256sum "$SELF" "$CTL" "$OUT/raw/"*.txt "$OUT/run.env" >"$OUT/SHA256SUMS"
echo "platform=READY profile=SOFTWARE capabilities=Socket,Onload,TCPDirect,DPDK,FeedGuardian"
printf '%s\n' '[配置说明] platform=READY 表示本次部署流程完成；profile=SOFTWARE 表示当前采用普通交易配置。' \
  '[能力说明] capabilities 列出已备齐的收发路径及 FeedGuardian 行情完整性保护能力，不是同时运行的进程清单；DPDK 要切换后才接管数据口。' \
  '[下一步] 打开 http://10.1.1.101:8088/ 查看网页，再按运行 ①A～①C 确认两组组播；运行 ②才提交首笔模拟订单。'
echo "evidence=$OUT"
