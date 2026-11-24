#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-tcpdirect-build-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
{
# ~~~~~检出固定 TCPDirect 9.0.2，在 .1 编一次~~~~~
COMMIT=0abc996ae4709e49dedd3e65da1eb134dea0632d
TMP="$(mktemp -d /tmp/flle06-tcpdirect.XXXXXX)"
cleanup(){ find "$TMP" -depth -delete; }
trap cleanup EXIT
git -c advice.detachedHead=false clone --depth 1 --branch tcpdirect-9.0.2 \
  https://github.com/Xilinx-CNS/tcpdirect.git "$TMP/repo"
git -C "$TMP/repo" rev-parse HEAD
test "$(git -C "$TMP/repo" rev-parse HEAD)" = "$COMMIT"
git -C "$TMP/repo" archive --format=tar --prefix=tcpdirect-0abc996/ "$COMMIT" |
  gzip -n >"$TMP/source.tgz"
sha256sum "$TMP/source.tgz"
test "$(sha256sum "$TMP/source.tgz" | cut -d' ' -f1)" = db5142a6e74f71584d46c42a512fb6bc2eb703ecda507c932e3d817c8c84f622
remote="/var/tmp/$RUN_ID.tgz"; scp -o BatchMode=yes -o StrictHostKeyChecking=yes "$TMP/source.tgz" root@10.1.1.1:"$remote"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 bash -s -- "$remote" <<'REMOTE'
set -Eeuo pipefail
archive="$1"; work="${archive%.tgz}.src"
cleanup(){ test ! -e "$work" || find "$work" -depth -delete; find /var/tmp -maxdepth 1 -type f -name "${archive##*/}" -delete; }
trap cleanup EXIT
mkdir "$work"; tar -xzf "$archive" -C "$work"
src="$work/tcpdirect-0abc996"
sed -i '/ZF_GIT_VERSION_INFO :=/,+1 s/HEAD)/HEAD 2>\/dev\/null)/; /ZF_GIT_BRANCH_INFO/s/HEAD)/HEAD 2>\/dev\/null)/' "$src/src/lib/zf/Makefile.inc"
make -C "$src" -j"$(nproc)" ONLOAD_TREE=/opt/flle/course-src/onload-9f330e7 \
  ZF_GIT_VERSION_INFO='0abc996 2025-06-13' ZF_GIT_BRANCH_INFO=tcpdirect-9.0.2
binary="$src/build/gnu_x86_64/bin/zf_apps/static/zftcppingpong"
install -D -m 0755 "$binary" /opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong
sha256sum /opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong
file /opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong
REMOTE
# ~~~~~同一份 zftcppingpong 装到两端~~~~~
scp -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1:/opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong "$TMP/zftcppingpong"
for host in 10.1.1.1 10.1.1.2; do
  scp -o BatchMode=yes -o StrictHostKeyChecking=yes "$TMP/zftcppingpong" root@"$host":/var/tmp/"$RUN_ID.binary"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" 'install -D -m 0755 /var/tmp/'"$RUN_ID"'.binary /opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong; find /var/tmp -maxdepth 1 -type f -name '"$RUN_ID"'.binary -delete; hostname; sha256sum /opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong; file /opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong'
done
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
