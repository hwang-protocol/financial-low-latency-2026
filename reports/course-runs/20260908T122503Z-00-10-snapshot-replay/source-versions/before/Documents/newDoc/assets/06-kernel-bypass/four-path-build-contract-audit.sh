#!/usr/bin/env bash
# Read-only helper for the Chapter 06 code-contract green card.
set -Eeuo pipefail
cd /financial-low-latency
RAW="${1:?usage: $0 OUTPUT_RAW_DIR}"
SOURCE="artifacts/blobs/x2522/ch06-four-path/v13/flle-ch06-four-path-v13-source.tgz"
SOURCE_SHA="1cbae2786192ac16c39b1ebbdb7a19101b99a532430903839de39a8f0fa62bc7"
BUILD_INPUTS="artifacts/blobs/x2522/ch06-four-path/v5/flle-ch06-four-path-v5-build-inputs-x86_64-jammy.tgz"
BUILD_INPUTS_SHA="6caa8e25a4228751872b8b96ed1cff260532fd73ab4fcb14f1d85cb7e7baf451"
PROVENANCE="artifacts/blobs/x2522/ch06-four-path/v13/BUILD-PROVENANCE.json"
PROVENANCE_SHA="3246b6941863d639814296b34acca57c12f8a0a7c6a5581b8d4f44c0e0544fd7"
RUNTIME="artifacts/blobs/x2522/ch06-four-path/v13/flle-ch06-four-path-v13-x86_64-jammy-runtime.tgz"
RUNTIME_SHA="ed7a7b1aa05151165316db67c99910715d6c63ab9d5c7635c73c6bd4e9441573"
TMP="$(mktemp -d /tmp/flle06-code-contract.XXXXXX)"
cleanup(){ find "$TMP" -depth -delete; }; trap cleanup EXIT
mkdir -p "$RAW"
printf '%s  %s\n%s  %s\n%s  %s\n%s  %s\n' \
  "$SOURCE_SHA" "$SOURCE" "$BUILD_INPUTS_SHA" "$BUILD_INPUTS" \
  "$PROVENANCE_SHA" "$PROVENANCE" "$RUNTIME_SHA" "$RUNTIME" | sha256sum -c -
tar -xzf "$SOURCE" -C "$TMP"
SRC="$TMP/flle-trading-lab-v13-source"
mkdir "$TMP/build-inputs"
tar -xzf "$BUILD_INPUTS" -C "$TMP/build-inputs"
(cd "$TMP/build-inputs/flle-ch06-four-path-v5-build-inputs" && sha256sum -c MANIFEST.sha256 >/dev/null)
tar -xOf "$RUNTIME" flle-ch06-four-path/etc/f-stack-x2522.ini >"$RAW/f-stack-x2522.ini"
tar -xOf "$RUNTIME" flle-ch06-four-path/provenance/BUILD-PROVENANCE.json >"$RAW/build-provenance.json"
tar -xOf "$RUNTIME" flle-ch06-four-path/MANIFEST.sha256 >"$RAW/runtime-manifest.sha256"
cmp -s "$PROVENANCE" "$RAW/build-provenance.json"

printf '===== source to binary provenance =====\n'
python3 - "$RAW/build-provenance.json" "$RAW/runtime-manifest.sha256" \
  "$SOURCE_SHA" "$BUILD_INPUTS_SHA" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    provenance = json.load(stream)
manifest = {}
with open(sys.argv[2], encoding="utf-8") as stream:
    for line in stream:
        digest, path = line.rstrip("\n").split("  ", 1)
        manifest[path] = digest
if provenance.get("schema") != "flle.ch06-four-path-build-provenance.v8":
    raise SystemExit("unexpected provenance schema")
if provenance["application_source"]["sha256"] != sys.argv[3]:
    raise SystemExit("source archive mismatch")
if provenance["build_inputs"]["sha256"] != sys.argv[4]:
    raise SystemExit("build-input archive mismatch")
if provenance["acceptance"]["bit_reproducible_application_build"] != "PASS":
    raise SystemExit("reproducible-build gate did not pass")
for path, digest in provenance["compiled_outputs"].items():
    if manifest.get(path) != digest:
        raise SystemExit(f"compiled output mismatch: {path}")
packaged_controls = dict(provenance["packaged_control_files"])
host_boundary = packaged_controls.pop("host_command_boundary", "")
if not host_boundary:
    raise SystemExit("packaged host-command boundary is missing")
for path, digest in packaged_controls.items():
    if manifest.get(path) != digest:
        raise SystemExit(f"packaged control mismatch: {path}")
inherited = provenance["inherited_runtime_files"]
for path in ("bin/zf_stackdump", "bin/dpdk-devbind.py", "etc/f-stack-x2522.ini"):
    if manifest.get(path) != inherited[path]:
        raise SystemExit(f"inherited runtime mismatch: {path}")
print("source_archive_sha256=" + sys.argv[3])
print("build_inputs_sha256=" + sys.argv[4])
print("source_binary_mapping=PASS compiled_outputs=" +
      str(len(provenance["compiled_outputs"])) + " packaged_controls=" +
      str(len(packaged_controls)) +
      " inherited_key_files=3")
PY

printf '\n===== four transport implementations from frozen source =====\n'
(cd "$SRC" && grep -En -- '::socket|::connect|send_all|recv_all' src/posix_order_transport.cpp)
(cd "$SRC" && grep -En -- 'zf_stack_alloc|zft_connect|zft_send_single|zft_zc_recv|ctpio' src/tcpdirect_order_transport.cpp)
(cd "$SRC" && grep -En -- 'ff_socket|ff_connect|ff_send|ff_recv|FSTACK_POLL' src/dpdk_trader.cpp)
(cd "$SRC" && grep -En -- 'rte_eth_stats_get|dpdk_port_stats|ipackets|rx_nombuf' src/dpdk_trader.cpp)
(cd "$SRC" && grep -En -- 'ff_setsockopt.*TCP_NODELAY|TCP_NODELAY' src/{posix_order_transport,dpdk_trader}.cpp)

printf '\n===== common handoff and launch contract =====\n'
(cd "$SRC" && grep -En -- 'OrderQueueMode::DequeCv|lock_order_queue|queue_locked' src/{trader,dpdk_trader}.cpp)
(cd "$SRC" && grep -En -- 'allocate_bounded_user_ref|user_ref_end_exclusive' \
  src/common.hpp src/trader.cpp src/dpdk_trader.cpp)
grep -En -- 'profile=latency|order-cpu 2|management-cpu 3' apps/flle-trading-lab/scripts/transport_labctl.sh
grep -En -- 'FLLE_DPDK_HELPER_CPU=3|taskset -c 2,3|file_prefix=' "$SRC/scripts/x2522-dpdk-trader-remote.sh"
grep -En -- 'BALANCED_PHASE_ORDER|exchange_ledger_gate|exchange_replay_gate|submission_identity' apps/flle-trading-lab/scripts/measure_four_transports.py

printf '\n===== packaged F-Stack tuning contract =====\n'
while IFS= read -r expected; do
  [[ -z "$expected" || "$expected" == \#* ]] && continue
  grep -Fxq "$expected" "$RAW/f-stack-x2522.ini"
  printf '%s\n' "$expected"
done <"$SRC/third_party/fstack/f-stack-x2522.audit"
echo fstack_config_contract=PASS
