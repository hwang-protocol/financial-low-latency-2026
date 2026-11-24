# 同一 session 内的到达顺序；2 重复一次，3 在 4 之后才补到。
ARRIVALS = [0, 1, 2, 2, 4, 3]


def classify(sequence, seen, max_seen):
    """把一次到达分成 NEW / DUPLICATE / GAP / LATE，并返回新的 max_seen。"""
    if sequence in seen:
        return "DUPLICATE", max_seen
    if sequence == max_seen + 1:
        return "NEW", sequence
    # 跳号说明当时缺了中间的序号；迟到说明缺口在更高序号之后才补上。
    if sequence > max_seen + 1:
        return "GAP", sequence
    return "LATE", max_seen


seen = set()
max_seen = -1
counts = {"NEW": 0, "DUPLICATE": 0, "GAP": 0, "LATE": 0}
for sequence in ARRIVALS:
    verdict, max_seen = classify(sequence, seen, max_seen)
    seen.add(sequence)
    counts[verdict] += 1
    print("arrival=%d verdict=%-9s max_seen=%d seen=%s"
          % (sequence, verdict, max_seen, sorted(seen)))
print("counts NEW=%d DUPLICATE=%d GAP=%d LATE=%d"
      % (counts["NEW"], counts["DUPLICATE"], counts["GAP"], counts["LATE"]))
# GAP 是一次已经发生的观察事件，即使缺口后来被补上也不会退回。
print("still_missing=%s gap_events_recorded=%d"
      % (sorted(set(range(max_seen + 1)) - seen), counts["GAP"]))
