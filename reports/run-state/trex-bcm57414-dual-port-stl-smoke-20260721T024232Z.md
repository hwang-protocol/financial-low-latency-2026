# TRex v3.08 BCM57414 Dual-Port STL Smoke Run State

- `RUN_ID`: `20260721T024232Z`
- `PURPOSE`: TRex v3.08 BCM57414 dual-port STL/UDP functional smoke
- `PROFILE_ID`: `trex-v3.08-bcm57414-dual-uio-stlflowstats-512x2`
- `STARTED_AT_UTC`: `2026-07-21T02:42:32Z`
- `FINISHED_AT_UTC`: `2026-07-21T03:11:19Z`
- `RESULT_DIR`: `reports/20260721T024232Z-trex-bcm57414-dual-port-stl-smoke/`
- `STATUS`: `COMPLETED`
- `RESULT`: `BLOCKED_AT_STLFLOWSTATS_RULE_INSTALL`
- `ACCEPTANCE`: `NOT_PASSED`
- `TRAFFIC`: `NOT_TESTED`; `client.add_streams(STLFlowStats(pg_id=100))` failed before `start_traffic`
- `PMD_LINK`: `PASS`; TRex loaded real `net_bnxt`, enumerated two ports, and observed both at 10 Gb/s full-duplex / UP
- `FINAL_HEALTH`: `PASS`; recovery rc=0 and independent final-health rc=0
- `MANAGEMENT_PROTECTION`: `PASS`; `ens33/0000:02:01.0/10.1.1.11` and default route via `10.1.1.254` unchanged
- `DATA_FINAL`: `0000:03:00.0 → ens64f0np0` and `0000:03:00.1 → ens64f1np1`, both `bnxt_en`, down, zero address, no master/XDP
- `RUNTIME_FINAL`: hugepages=0; no UIO module, TRex/Scapy/testpmd process, 4500/4501/4507 listener, deadman, workdir, hugepage or DPDK runtime temp
- `ARTIFACT_TRUST`: untrusted experiment-only v3.08 bytes; archive SHA-256 `d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f`
- `PIT`: `PIT-20260721-71`, `PIT-20260721-72`, `PIT-20260721-73`
- `NEXT`: any plain STL stream without `STLFlowStats` must use a new RUN/profile and independent counters; do not revise this RUN into a traffic PASS
