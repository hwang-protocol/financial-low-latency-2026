# B0 BCM57414 RDMA / vIOMMU Read-only Discovery Run State

- `RUN_ID`: `20260721T065513Z`
- `PURPOSE`: current `.11` guest vIOMMU and BCM57414 hardware-RoCE prerequisite discovery
- `PROFILE_ID`: `b0-rdma-discovery`
- `STARTED_AT_UTC`: `2026-07-21T06:55:13Z`
- `RESULT_DIR`: `reports/20260721T065513Z-b0-rdma-discovery`
- `STATUS`: `COMPLETED`
- `AUTHORIZATION`: root greenlight limited to new B0 read-only discovery
- `RECOVERY_POINT`: no device/config mutation authorized; exact RUN staging only
- `FINISHED_AT_UTC`: `2026-07-21T07:04:55Z`
- `FINAL_CONCLUSION`: `DISCOVERY_COMPLETE/PREPARATION_REQUIRED`
- `MUTATION_RESULT`: `NONE`
- `FINAL_HEALTH`: `READ_ONLY_BASELINE_CLEAN`
- `REMOTE_STAGING`: `REMOVED`

Both BCM57414 functions and the current-kernel `bnxt_re` module file were
enumerated, but `bnxt_re` is unloaded and RDMA device/provider/verbs objects
are absent. No hardware rejection was exercised. Detailed state and strict
negative boundaries are in
`reports/20260721T065513Z-b0-rdma-discovery/run-state.md` and
`reports/20260721T065513Z-b0-rdma-discovery/report.md`.
