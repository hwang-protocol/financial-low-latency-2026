# Mini-HFT Market Day Evidence Report

- RUN_ID: 20260722T070500Z-12-final-report
- Functional: Tick → decision → ACK/Execution
- Profiles: Kernel / Onload; other bypass modes qualified separately
- Pressure: calm / burst; TRex TX, NIC RX and LANZ reconciled
- Time: clock domain and PTP boundary stated
- Observability: raw sample, metric, log and dashboard receipt
- Recovery: drivers, addresses, XDP, hugepages and switch checked
- Claim boundary: correlation is not per-packet causality
