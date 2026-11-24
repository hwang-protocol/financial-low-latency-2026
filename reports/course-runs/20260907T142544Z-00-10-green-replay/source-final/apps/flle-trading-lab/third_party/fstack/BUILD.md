# F-Stack / DPDK X2522 build contracts

The application pins F-Stack commit
`0abb713721a6a0ba95768acde052dbd3d2fdf3fe`. Its source tree contains DPDK
`24.11.6`, and the persistent management host keeps that complete source plus
a relocatable DPDK-24 development cache under:

```text
artifacts/blobs/x2522/f-stack/0abb713-dpdk-24.11.6/
```

That cache passed a clean-directory link test, but it did not become the
Chapter 06 hardware runtime. The verified four-order-path runtime uses the
same F-Stack commit patched for Ubuntu Jammy DPDK `21.11.9`; this is the
version whose packaged `net_sfc_efx` PMD completed a real X2522 order.

## Verified course runtime

The current source/build/runtime closure is:

```text
artifacts/blobs/x2522/ch06-four-path/v5/
  flle-ch06-four-path-v5-source.tgz
  flle-ch06-four-path-v5-build-inputs-x86_64-jammy.tgz
  BUILD-PROVENANCE.json
  flle-ch06-four-path-v5-x86_64-jammy-runtime.tgz
```

Their sizes and SHA-256 values are source `37242` bytes /
`138c0effa936d0dfe98a33857ca730f39414bb35b25d30f1100ac14aaf74c3ed`,
build inputs `4504944` bytes /
`6caa8e25a4228751872b8b96ed1cff260532fd73ab4fcb14f1d85cb7e7baf451`,
provenance `4413` bytes /
`d445fd6f3a3919f92967c67725c7fbcb81eb800edcb256ef0cfcbffb3d46c386`,
and runtime `23729797` bytes /
`1a3c0766dac04774f0d4ed0d3a910de409f52964fb219519ecf326e6fe8e93aa`.
The source archive is the exact Makefile, application source and F-Stack
build-contract closure used for v5. The build-input archive fixes the exact
TCPDirect and F-Stack headers and static libraries consumed by that build; it
does not claim to reproduce those vendor libraries from upstream source. The
provenance JSON records the build host, dependency inputs, commands, build-log
digest and output binary digests. Two clean builds in different absolute
directories produced identical application binaries. The JSON was hash-fixed
before live acceptance, so its `hardware_runtime=PENDING_NEW_V5_RUN` field is
deliberately unchanged; the
later formal RUN supplies that independent receipt.

The runtime contains the Socket, TCPDirect and F-Stack/DPDK traders,
`zf_stackdump`,
`dpdk-devbind.py`, the F-Stack configuration and 26 resolved non-glibc shared
libraries. Verify both the outer artifact and its inner `MANIFEST.sha256`
before use.

The packaged F-Stack configuration is checked against
`third_party/fstack/f-stack-x2522.audit`. The latency profile keeps the
F-Stack reactor on CPU 2 with `idle_sleep=0` and `pkt_tx_delay=0`, moves the
bridge and management threads to CPU 3, and verifies `TCP_NODELAY` at runtime.
Application queues remain `DEQUE_CV`; only the network reactors poll.
The v5 clients use the same timer boundary: OUCH is encoded, but Soup
framing and Transport work have not started. POSIX/F-Stack clients verify
`TCP_NODELAY` with `getsockopt`; the ZF API reports that POSIX switch as N/A.
The SFC and DPDK controllers allocate persistent, disjoint namespaces, and the
clients enforce bounded allocation rather than seeding from wall time. Their
base/span/end/next values are exposed in status JSON and checked before use.
Namespace state survives mode switches: resetting it could let a later launch
hit the Exchange idempotency ledger instead of executing a fresh order.

The DPDK-21 compatibility patch is tracked at
`third_party/fstack/dpdk-21.11-compat.patch`. It handles the ethdev capability,
bonding-name and timer API differences between the pinned F-Stack source and
DPDK 21.11. F-Stack builds serially against the distro `libdpdk.pc`, and the
application links through the top-level `Makefile` with
`FSTACK_TREE=<patched-source>`.

The live acceptance contract is stronger than a link check:

- EAL reports `Using IOMMU type 1`;
- the PCI probe reports `net_sfc_efx` for `0000:03:00.0`;
- the PMD reports the ultra-low-latency firmware variant;
- `flle-trader-dpdk` completes a SoupBinTCP/OUCH fill;
- cleanup restores `sfc`, `20.1.1.2/24` and hugepages `0`.

These conditions were reconfirmed by current-state preflight RUN
`20260901T090636Z-06-four-path-preflight` and schema-v6 formal RUN
`20260901T091419Z-06-four-path-orders`. The formal RUN used the Williams order
`S/O/D/T`, `O/T/S/D`, `T/D/O/S`, `D/S/T/O`: every path occupied every position
once, and all 12 distinct ordered predecessors occurred once on within-round
edges. The three cross-round edges repeat existing predecessors. Each cell used
one warmup to establish the path witness and 99 further warmups before timing.
The Gateway was stopped during the 16 formal cells. All 17,600 warmup plus measured
submissions had unique IDs; the 16,000 measured IDs mapped exactly to returned
samples; every cell retained the same boot/PID/start-ticks identity across its
timed window and showed a growing current-path counter; and the Exchange ledger
advanced from 2072 to 19672, exactly 17,600. This gate rejects cached replays,
stale receipts and concurrent GUI orders. The balance-preserving primary analysis
computes nearest-rank statistics inside each cell and then equally weights the
four cells. `send-to-final` p50/p99 values were Socket `38000/61608`, OpenOnload
`24847/39771`, TCPDirect `24833/41395`, and DPDK/F-Stack `28842/51783 ns`.
They describe this implementation and short run, not intrinsic rankings or a
production SLA. The older `20260901T080729Z` RUN remains historical evidence;
its four-round median and sticky receipts are not the current performance basis.

The frozen POSIX/Onload, TCPDirect and DPDK/F-Stack trader binaries are
verified and distributed rather than rebuilt by the Chapter 06 runtime cards.
That boundary is not a course-wide no-build claim: clean-snapshot Onload
preparation may compile for the running kernel, and the base Trading Lab
deployment may compile its baseline application under its own contract.

The v4 runtime remains historical: its raw and hardware receipts are valid,
but its cyclic Latin order balanced positions only. Four ordered predecessors
were repeated three times and eight were absent, while the identity gate
covered measured rows only and SFC IDs were seeded from realtime. v5 therefore
supersedes every v4 performance conclusion. The v3 runtime remains registered
only as stronger negative evidence. Its
three DPDK rounds reused `3900000100..3900001099`; rounds 2 and 3 therefore
received the Exchange's cached idempotent responses rather than performing
fresh matching, response encoding and ledger work. That invalidates v3 DPDK
performance and every v3 four-path performance comparison. v1 through v4 are
not current classroom packages.

RUN `20260901T065053Z-06-four-path-orders` is also negative evidence, not a
runtime failure: deployment copied the tests but omitted the `scripts/`
directory, so test collection failed while importing
`measure_four_transports.py`. `transport_labctl.sh` now deploys that directory;
the formal RUN's 18 passing tests close this packaging defect.

## Optional DPDK-24 development cache

The DPDK-24 cache is an optimization, not the Chapter 06 source of truth.
Verify `artifacts/SHA256SUMS` before copying it to a guest. If its OS,
architecture, compiler ISA or external libraries do not match, rebuild it
from the source archive with the following contract.

### Fixed build inputs

- OS / architecture: Ubuntu 22.04, `x86_64`
- compiler: GCC 11.4.0
- DPDK: `24.11.6`, native ISA, tests and applications disabled
- DPDK drivers: `common/sfc_efx`, `net/sfc`, and `net/bonding`
- F-Stack: serial build with `CONF_CFLAGS=-Wno-error=array-bounds`

`net/bonding` is a compile dependency because this F-Stack revision includes
`rte_eth_bond.h` unconditionally. The FLLE runtime does not create a bond; a
hardware receipt must still identify the X2522 `net_sfc` PMD.

### DPDK-24 rebuild sequence

Assume `SRC`, `DPDK_BUILD`, and `PREFIX` are new absolute directories owned by
this build. Do not reuse `/usr/local` or the distro DPDK installation.

```bash
meson setup "$DPDK_BUILD" "$SRC/dpdk" --prefix="$PREFIX" \
  -Dplatform=native -Dtests=false -Denable_kmods=false \
  -Ddisable_apps='*' \
  -Denable_drivers=common/sfc_efx,net/sfc,net/bonding
meson compile -C "$DPDK_BUILD" -j4
meson install -C "$DPDK_BUILD"

export PKG_CONFIG_PATH="$PREFIX/lib/x86_64-linux-gnu/pkgconfig"
make -C "$SRC/lib" clean
make -C "$SRC/lib" CONF_CFLAGS=-Wno-error=array-bounds
make -C "$SRC/lib" install PREFIX="$PREFIX" \
  F-STACK_CONF="$PREFIX/f-stack.conf.example"
```

Do not add `-j` to the F-Stack library build. Its `machine_includes` target
deletes and recreates a header tree without ordering it before parallel object
compilation; a parallel build can intermittently fail with missing
`x86/endian.h`.

### DPDK-24 cached outputs

| Output | SHA-256 |
|---|---|
| `lib/libfstack.a` | `7290cfaad8b8906efd8cc8d0348c3fd1c9f0cc77013ba62e10661e4ac6fc17d7` |
| `lib/x86_64-linux-gnu/librte_net_sfc.a` | `021368139c034c281c96005fc3530ae3185bf02354831e7e1c855d0f819457ef` |

The optional cache rewrites every packaged `.pc` file to use
`prefix=${pcfiledir}/../../..`. Its acceptance check extracts it into a new
directory and links `echo_client_fstack.c` from that relocated prefix. This
only proves that the DPDK-24 development cache is portable and link-complete;
it must not be cited as the runtime used by the course result.
