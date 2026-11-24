# Course run: preallocation, SPSC and CPU path

- RUN_ID: `20260722T043838Z-05-software-design`
- Result: `PASS_LOW_LATENCY_SOFTWARE_DESIGN`
- Input: 200000 wire-v1 AAPL Tick messages in every comparison
- Allocation: per-message allocation and preallocated pool produced the same checksum
- Queue: mutex queue and SPSC ring produced the same ordered checksum
- CPU path: X2522 queues, IRQs and effective CPUs captured read-only
- Affinity: unbound and CPU 5 pinned runs produced the same checksum
- Boundary: correctness and path changes are hard gates; timing values are observations, not promised improvements
