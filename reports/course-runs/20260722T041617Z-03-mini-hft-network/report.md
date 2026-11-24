# Course run: Mini-HFT on the real 10GbE path

- RUN_ID: `20260722T041617Z-03-mini-hft-network`
- Result: `PASS_MINI_HFT_REAL_UDP_TCP`
- Binary SHA-256: `f129096f0b12948f4a8509a1d335c4a47784fa8a29cdc4be9ea3b845ae674a06` on both endpoints
- Flow: 8 Tick datagrams, 8 framed Order Submit, 8 ACK and 8 Execution responses
- Capture: UDP/42000 and TCP/42010 observed on  X2522
- Boundary: functional POSIX path and raw samples; no stable latency claim yet
