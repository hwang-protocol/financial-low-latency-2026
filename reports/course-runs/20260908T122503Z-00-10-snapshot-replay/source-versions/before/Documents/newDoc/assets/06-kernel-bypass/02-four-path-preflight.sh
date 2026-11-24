#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-four-path-preflight"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
ARCHIVE=artifacts/blobs/x2522/ch06-four-path/v13/flle-ch06-four-path-v13-x86_64-jammy-runtime.tgz
{
  sha_line="$(printf '%s  %s\n' \
    ed7a7b1aa05151165316db67c99910715d6c63ab9d5c7635c73c6bd4e9441573 \
    "$ARCHIVE" | sha256sum -c -)"
  printf '===== 查 v13 运行包 =====\n[归档] 对: SHA-256=ed7a7b1a…1573  证: 四路客户端和运行库没漂\n$ sha256sum -c\n%s\n' "$sha_line"
  mkdir -p "$OUT/raw/code-contract"
  bash Documents/newDoc/assets/06-kernel-bypass/four-path-build-contract-audit.sh \
    "$OUT/raw/code-contract" >"$OUT/raw/code-contract.txt"
  printf '===== 查源码到 ELF 的对账 =====\n[构建合同] 对: source / build-inputs / provenance / runtime 四项验签通过  证: 上课运行的是当前封存代码的已编译 ELF\n$ four-path-build-contract-audit.sh\nsource_binary_contract=PASS\n'
  mapfile -t pre < <(bash apps/flle-trading-lab/scripts/transport_labctl.sh preflight "$RUN_ID")
  for line in "${pre[@]}"; do
    case "$line" in
      control_assets=PASS*)
        printf '===== 查行情回放资产 =====\n[control_assets] 对: PASS 且 symbols=AAPL,NVDA  证: 纸面行情文件还在\n$ labctl preflight · control_assets\n%s\n' "$line" ;;
      builder_tools=PASS*)
        printf '===== 查 Builder 工具链 =====\n[builder_tools] 对: .101 上有 g++-11  证: 管理机构建链还在\n$ labctl preflight · builder_tools\n%s\n' "$line" ;;
      exchange_rss_preflight=PASS*)
        printf '===== 查 Exchange RSS 表 =====\n[RSS] 对: table=baseline-0-1-2-3 或 measure-all-1  证: 空闲可开工，或本课测量仍受控\n$ labctl preflight · exchange_rss\n%s\n' "$line" ;;
      transport_preflight=PASS*)
        printf '===== 查四路开工总闸 =====\n[transport_preflight] 对: PASS queue=DEQUE_CV  证: 可以进准备 D 启用路径测试\n$ labctl preflight · transport\n%s\n' "$line" ;;
      *)
        printf '%s\n' "$line" ;;
    esac
  done
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && find raw/code-contract -type f -print0 | sort -z | \
  xargs -0 sha256sum >raw/code-contract.SHA256SUMS)
(cd "$OUT" && sha256sum raw/code-contract.SHA256SUMS raw/code-contract.txt \
  raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
