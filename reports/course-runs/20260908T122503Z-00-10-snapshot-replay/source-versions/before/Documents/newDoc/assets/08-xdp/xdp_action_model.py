packets = [
    ("A", 37, "AAPL    ", 1, 36, "COUNT_AAPL+XDP_PASS"),
    ("A", 8095, "NVDA    ", 1, 36, "COUNT_NVDA+XDP_DROP"),
    ("F", 8095, "NVDA    ", 1, 40, "COUNT_OTHER_ITCH+XDP_PASS"),
    ("D", 0, "-", 1, 19, "COUNT_OTHER_ITCH+XDP_PASS"),
    ("HEARTBEAT", 0, "-", 0, 0, "COUNT_HEARTBEAT+XDP_PASS"),
    ("A", 8095, "NVDA    ", 1, 20, "COUNT_OTHER_ITCH+XDP_PASS"),
]
for kind, locate, stock, count, length, action in packets:
    print("type=%-9s locate=%-5s stock=%-8s count=%d length=%-2s action=%s" %
          (kind, locate, stock, count, length, action))
