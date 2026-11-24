CURRENT_SESSION = 7
KNOWN_PAST_SESSIONS = {6}

# 到达顺序固定：本轮新消息、已知旧批次、陌生批次、本轮重复、本轮下一条。
ARRIVALS = [
    {"session": 7, "sequence": 0, "correlation": 701},
    {"session": 6, "sequence": 0, "correlation": 601},
    {"session": 99, "sequence": 0, "correlation": 901},
    {"session": 7, "sequence": 0, "correlation": 701},
    {"session": 7, "sequence": 1, "correlation": 702},
]


def classify(message, seen):
    """先判 session 再判 sequence；correlation 只随行保留，不参与判定。"""
    if message["session"] != CURRENT_SESSION:
        # 只有登记在册的批次才敢叫旧批次，其余一律先当陌生来源。
        if message["session"] in KNOWN_PAST_SESSIONS:
            return "OLD_SESSION"
        return "UNEXPECTED_SESSION"
    if message["sequence"] in seen:
        return "DUPLICATE"
    seen.add(message["sequence"])
    return "NEW"


seen = set()
print("current_session=%d known_past_sessions=%s"
      % (CURRENT_SESSION, sorted(KNOWN_PAST_SESSIONS)))
for message in ARRIVALS:
    print("session=%-3d sequence=%d correlation=%d verdict=%s"
          % (message["session"], message["sequence"],
             message["correlation"], classify(message, seen)))
print("accepted_into_seen=%s" % sorted(seen))
