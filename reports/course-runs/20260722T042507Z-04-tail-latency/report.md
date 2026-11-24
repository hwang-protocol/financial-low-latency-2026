# Course run: raw samples and tail-latency summary

- RUN_ID: `20260722T042507Z-04-tail-latency`
- Result: `PASS_RAW_TO_TAIL_LATENCY_SUMMARY`
- Raw samples: 500; each row is retained
- Warmup and eligible counts: recorded in `derived/summary.env`
- Summary: mean, p50, p99 and max are recomputed from raw samples
- Boundary: a short teaching run demonstrates measurement mechanics; it is not a production percentile or SLA
