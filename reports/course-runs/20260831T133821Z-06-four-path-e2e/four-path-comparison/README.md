# Chapter 06 four real order transports

RUN_ID: `20260831T133821Z-06-four-path-e2e`

All paths use one-share crossing IOC orders, SoupBinTCP/OUCH, single-flight submission, and a locked DEQUE_CV application handoff.
DPDK requires exclusive VFIO ownership, so it is measured in a separate fixed phase rather than interleaved with the three sfc paths.

| Transport | median round P50 send→final | median round P99 | median round P50 queue→final |
| --- | ---: | ---: | ---: |
| Kernel Socket | 44694 ns | 67813 ns | 49542 ns |
| OpenOnload | 28489 ns | 54990 ns | 33742 ns |
| TCPDirect | 30320 ns | 69032 ns | 36091 ns |
| DPDK + F-Stack TCP | 132683 ns | 280756 ns | 183529 ns |
