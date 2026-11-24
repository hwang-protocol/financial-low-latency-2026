#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-build-toolchain"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

python3 Documents/newDoc/assets/common/install-offline-packages.py 10.1.1.101 builder 2>&1 | tee "$OUT/raw/packages.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
printf '#include <iostream>\nint main(){std::cout<<"compiler_smoke=hello-cpp\\n";}\n' |
  g++-11 -x c++ -o "$tmp/smoke" -
g++-11 --version
"$tmp/smoke"
REMOTE
(cd "$OUT" && sha256sum raw/result.txt raw/packages.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
