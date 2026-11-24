#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/08-xdp"
EOS="$ROOT/Documents/newDoc/assets/common/eos_cli.py"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-span-live"
OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"
REMOTE="/var/tmp/$RUN_ID"
IFACE=ens64f0np0
API=http://10.1.1.101:8088
mkdir -p "$OUT/raw" "$OUT/artifacts"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["market_mode"])')"
ARMED=1

remote() { ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "$@"; }
cleanup() {
  set +e
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null
  remote "ip link set dev '$IFACE' xdp off 2>/dev/null || true; ip link set dev '$IFACE' promisc off; ip link set dev '$IFACE' down; find '$REMOTE' -type f -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"
  python3 "$EOS" --plan "$ASSET/xdp-span-restore.plan" --output "$OUT/raw/eos-restore.txt" --mode controlled-config
  set -e
}
trap 'if [ "$ARMED" = 1 ]; then cleanup; fi' EXIT INT TERM

curl -fsS "$API/api/state" >"$OUT/raw/state-before.json"
python3 "$EOS" --plan "$ASSET/xdp-span-show.plan" --output "$OUT/raw/eos-before.txt" --mode show
remote "test \"\$(readlink -f /sys/class/net/$IFACE/device)\" = /sys/devices/pci0000:03/0000:03:00.0; ! ip -details link show dev '$IFACE' | grep -q 'prog/xdp'; mkdir '$REMOTE'"
scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/flle_xdp_mold_itch.c" root@10.1.1.11:"$REMOTE/"
remote "cd '$REMOTE'; clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o"

python3 "$EOS" --plan "$ASSET/xdp-span-apply.plan" --output "$OUT/raw/eos-apply.txt" --mode controlled-config
remote "set -Eeuo pipefail; ip link set dev '$IFACE' up; ip link set dev '$IFACE' promisc on; ip link set dev '$IFACE' xdp obj '$REMOTE/flle_xdp_mold_itch.o' sec xdp; ip -details link show dev '$IFACE'; bpftool net show dev '$IFACE'" | tee "$OUT/raw/xdp-attach.txt"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST"}' "$API/api/market" >/dev/null
sleep 1

remote "timeout 12 tcpdump -ni '$IFACE' -s 0 -c 400 -w '$REMOTE/pass.pcap' 'udp dst port 42120'" 2>&1 | tee "$OUT/raw/pass-tcpdump.txt"
remote "bpftool -j map dump name counters" >"$OUT/raw/map-pass.json"
remote "bpftool map update name drop_nvda_add key 0 0 0 0 value 1 0 0 0"
remote "timeout 12 tcpdump -ni '$IFACE' -s 0 -c 400 -w '$REMOTE/drop.pcap' 'udp dst port 42120'" 2>&1 | tee "$OUT/raw/drop-tcpdump.txt"
remote "bpftool -j map dump name counters" >"$OUT/raw/map-drop.json"
remote "bpftool map update name drop_nvda_add key 0 0 0 0 value 0 0 0 0; ip link set dev '$IFACE' xdp off"
remote "timeout 12 tcpdump -ni '$IFACE' -s 0 -c 400 -w '$REMOTE/recovery.pcap' 'udp dst port 42120'" 2>&1 | tee "$OUT/raw/recovery-tcpdump.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.11:"$REMOTE/pass.pcap" "$OUT/artifacts/"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.11:"$REMOTE/drop.pcap" "$OUT/artifacts/"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.11:"$REMOTE/recovery.pcap" "$OUT/artifacts/"

python3 "$ASSET/analyze_mold_pcap.py" "$OUT/artifacts/pass.pcap" --expect-nvda present | tee "$OUT/raw/pass-decoded.txt"
python3 "$ASSET/analyze_mold_pcap.py" "$OUT/artifacts/drop.pcap" --expect-nvda absent | tee "$OUT/raw/drop-decoded.txt"
python3 "$ASSET/analyze_mold_pcap.py" "$OUT/artifacts/recovery.pcap" --expect-nvda present | tee "$OUT/raw/recovery-decoded.txt"
python3 - "$OUT/raw/map-drop.json" <<'PY' | tee "$OUT/raw/map-verdict.txt"
import json, sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))
values = {}
for row in rows:
    if "formatted" in row:
        key = row["formatted"]["key"]
        values[key] = sum(item["value"] for item in row["formatted"]["values"])
    else:
        raw_key = [int(item, 16) if isinstance(item, str) else item for item in row["key"]]
        raw_value = [int(item, 16) if isinstance(item, str) else item for item in row["value"]]
        values[int.from_bytes(bytes(raw_key), "little")] = int.from_bytes(bytes(raw_value), "little")
print("counter_sums=" + ",".join(f"{key}:{values[key]}" for key in sorted(values)))
assert values.get(2, 0) > 0 and values.get(3, 0) > 0 and values.get(6, 0) > 0
print("map_verdict=PASS")
PY

cleanup
ARMED=0
trap - EXIT INT TERM
curl -fsS "$API/api/state" >"$OUT/raw/state-after.json"
remote "! ip -details link show dev '$IFACE' | grep -q 'prog/xdp'; test \"\$(cat /sys/class/net/$IFACE/operstate)\" = down; ! ip -o addr show dev '$IFACE' | grep -q ."
printf 'ORIGINAL_MODE=%s\nINTERFACE=%s\nSPAN_SESSION=FLLEXDP\n' "$ORIGINAL_MODE" "$IFACE" >>"$OUT/run.env"
sha256sum "$ASSET/flle_xdp_mold_itch.c" "$ASSET/analyze_mold_pcap.py" "$OUT"/raw/* "$OUT"/artifacts/* "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'evidence=%s\n' "$OUT"
