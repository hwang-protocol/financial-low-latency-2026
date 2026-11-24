# Chapter 06 four real order transports

RUN_ID: `20260831T133821Z-06-four-path-e2e-smoke`

All paths use one-share crossing IOC orders, SoupBinTCP/OUCH, single-flight submission, and a locked DEQUE_CV application handoff.
DPDK requires exclusive VFIO ownership, so it is measured in a separate fixed phase rather than interleaved with the three sfc paths.

| Transport | median round P50 send→final | median round P99 | median round P50 queue→final |
| --- | ---: | ---: | ---: |
| Kernel Socket | 64186 ns | 82373 ns | 109159 ns |
| OpenOnload | 41553 ns | 58070 ns | 87718 ns |
| TCPDirect | 39327 ns | 62785 ns | 78983 ns |
| DPDK + F-Stack TCP | 173821 ns | 201871 ns | 229330 ns |
