#!/usr/bin/env bash
# Check readiness only; keep full command output in the evidence directory.
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%S.%NZ)-05-four-path-preflight"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw/code-contract"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
cp "$0" "$OUT/source.sh"
finish(){
  local rc=$?
  trap - EXIT
  printf 'EXIT_CODE=%s\n' "$rc" >>"$OUT/run.env"
  (cd "$OUT"; find raw -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum run.env source.sh) >"$OUT/SHA256SUMS"
  printf 'evidence=%s\n' "$OUT"
  exit "$rc"
}
trap finish EXIT
ARCHIVE=artifacts/blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-x86_64-jammy-runtime.tgz
pass(){ printf '[%s/6] %s：PASS  # %s\n' "$1" "$2" "$3"; }
fail(){
  local rc=$1 title=$2 log=$3
  printf '%s：FAIL  # 检查未通过，请先处理下面的问题。\n' "$title"
  tail -n 15 "$log"
  exit "$rc"
}
value(){
  local token
  for token in $1; do
    if [[ "$token" = "$2="* ]]; then printf '%s' "${token#*=}"; return; fi
  done
  return 1
}
{
  printf '准备 C：检查程序、行情与比较条件\n# 本步只检查，不重新编译、切换网卡或下单。\n\n'
  if printf '%s  %s\n' 0e5d77fef1e4891b9f2220681c18162da6c605ea5619ea00e28022f23281dc00 "$ARCHIVE" |
    sha256sum -c - >"$OUT/raw/archive.txt" 2>&1; then
    pass 1 '运行包完整' '三个客户端及配套文件与封存版本一致。'
  else fail "$?" '运行包' "$OUT/raw/archive.txt"; fi
  if bash Documents/newDoc/assets/05-kernel-bypass/four-path-build-contract-audit.sh \
    "$OUT/raw/code-contract" >"$OUT/raw/code-contract.txt" 2>&1; then
    pass 2 '源码与程序对应' '包内程序有对应的源码和编译记录。'
  else fail "$?" '源码与程序对应关系' "$OUT/raw/code-contract.txt"; fi

  if bash apps/flle-trading-lab/scripts/transport_labctl.sh preflight "$RUN_ID" \
    >"$OUT/raw/preflight.txt" 2>&1; then :
  else fail "$?" '行情、工具或收包配置' "$OUT/raw/preflight.txt"; fi
  declare -A rows=()
  while IFS= read -r line; do
    case "$line" in
      control_assets=*|builder_tools=*|exchange_rss_preflight=*|transport_preflight=*)
        key="${line%%=*}"
        if [[ -v "rows[$key]" || "${line%% *}" != "$key=PASS" ]]; then
          fail 1 '检查结果重复或未通过' "$OUT/raw/preflight.txt"
        fi
        rows[$key]="$line" ;;
    esac
  done <"$OUT/raw/preflight.txt"
  for key in control_assets builder_tools exchange_rss_preflight transport_preflight; do
    [[ -v "rows[$key]" ]] || fail 1 "缺少检查结果 $key" "$OUT/raw/preflight.txt"
  done
  symbols="$(value "${rows[control_assets]}" symbols)" || fail 1 '行情结果缺少 symbols' "$OUT/raw/preflight.txt"
  builder_host="$(value "${rows[builder_tools]}" host)" || fail 1 '工具结果缺少 host' "$OUT/raw/preflight.txt"
  compiler="$(value "${rows[builder_tools]}" compiler)" || fail 1 '工具结果缺少 compiler' "$OUT/raw/preflight.txt"
  table="$(value "${rows[exchange_rss_preflight]}" table)" || fail 1 '收包结果缺少 table' "$OUT/raw/preflight.txt"
  queue="$(value "${rows[transport_preflight]}" queue)" || fail 1 '比较条件缺少 queue' "$OUT/raw/preflight.txt"
  [[ -n "$symbols" && -n "$builder_host" && -n "$compiler" && "$queue" = DEQUE_CV ]] || fail 1 '检查字段缺失或队列要求不符' "$OUT/raw/preflight.txt"
  pass 3 '行情可用' "$symbols 的行情文件已就绪。"
  pass 4 '编译工具可用' "$builder_host 有 $compiler，恢复普通客户端时可用。"
  case "$table" in
    baseline-0-1-2-3) receive='Exchange .1 按队列 0～3 分配；正式测量时再固定队列 1 / CPU 2。' ;;
    measure-all-1) receive='Exchange .1 已固定到队列 1 / CPU 2。' ;;
    *) fail 1 '收包配置无法识别' "$OUT/raw/preflight.txt" ;;
  esac
  pass 5 '收包配置符合要求' "$receive"
  pass 6 '比较条件已核对' "四路统一要求 $queue，由准备 D 启用。"
  printf '\n# 六项全部通过，可以进入准备 D。\n# 完整校验值、字段和原生命令输出保存在下方 evidence 目录。\n'
} 2>&1 | tee "$OUT/raw/result.txt"
