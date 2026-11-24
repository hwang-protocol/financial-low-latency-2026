#!/usr/bin/env bash
# Shared by the two temporary market-mode experiments.
set_mode() {
  local mode="$1"
  case "$mode" in UNICAST|MULTICAST|DUAL) ;; *) echo 'Invalid market mode' >&2; return 2;; esac
  printf '$ curl -fsS --max-time 10 -X POST -H %q -d %q %q\n' \
    'Content-Type: application/json' "{\"market_mode\":\"$mode\"}" "$API/api/market"
  curl -fsS --max-time 10 -X POST -H 'Content-Type: application/json' \
    -d "{\"market_mode\":\"$mode\"}" "$API/api/market" >"$OUT/raw/set-$mode.json" || return $?
  printf '回读确认：$ curl -fsS --max-time 10 %q\n' "$API/api/state"
  for _ in {1..30}; do
    curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/mode-state.json" || return $?
    if python3 -c 'import json,sys;sys.exit(json.load(open(sys.argv[1]))["market_mode"] != sys.argv[2])' \
      "$OUT/raw/mode-state.json" "$mode"; then printf 'market_mode=%s\n' "$mode"; return 0; fi
    sleep 0.1
  done
  echo "Market mode readback did not become $mode" >&2
  return 1
}
restore_market_mode() {
  printf '===== 恢复检查前的行情模式 =====\n'
  if ! set_mode "$ORIGINAL_MODE"; then
    echo '行情模式恢复失败，退出码125；暂停后续下单并检查网页状态。' >&2
    return 125
  fi
}
cleanup_capture() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 root@10.1.1.2 \
    "rm -f /var/tmp/$CHAPTER_RUN_ID-*.pcap"
}
cleanup_market() {
  local rc=$?
  trap - EXIT
  restore_market_mode || rc=125
  cleanup_capture || true
  exit "$rc"
}
