#!/usr/bin/env python3
"""Reject a comparison spanning a replay restart before subtracting counters."""
import json
from pathlib import Path
import sys


def duplicate_count(before, current):
    def identity(state):
        session = state.get('session')
        feed = state.get('feed') or {}
        loop = (state.get('replay') or {}).get('loop')
        if not session or feed.get('session') != session or loop is None:
            raise ValueError('行情会话尚未同步，请等行情正常后重新运行本步。')
        return session, loop
    if identity(before) != identity(current):
        raise ValueError('三窗比较跨过回放换轮或重新开始，去重计数已不属于同一 Session；本次结果无效，请重新运行本步。')
    value = current['feed']['duplicates']
    if not isinstance(value, int) or value < 0:
        raise ValueError('去重计数无效，请检查行情状态。')
    return value


if __name__ == '__main__':
    try:
        print(duplicate_count(*(json.loads(Path(p).read_text()) for p in sys.argv[1:3])))
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
