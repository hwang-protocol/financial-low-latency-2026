from pathlib import Path
import difflib
import json
import re

root = Path('/financial-low-latency')
runs = root / 'Documents/reports/course-runs'
replay = json.loads((root / 'Documents/reports/run-state/00-03-fanout-replay.json').read_text())
assert all(card['status'] == 'PASS' for card in replay['cards'])
platform = '20260910T085337Z-02-trading-platform'
patches = []


def block(text, marker, value):
    start = text.index('```text\n', text.index(marker)) + 8
    end = text.index('```', start)
    return text[:start] + value.strip('\n') + '\n' + text[end:]


def short(text):
    text = re.sub(r'/financial-low-latency/Documents/reports/course-runs/[^/\s]+/raw/', '…/', text)
    text = re.sub(r'/var/tmp/\d{8}T\d{6}Z-03-[^\s\']+\.pcap', '…/capture.pcap', text)
    return re.sub(r'/var/tmp/flle-trading-lab-\d{8}T\d{6}Z-02-trading-platform/', '…/', text)


path = root / 'Documents/newDoc/03-live-trading-traffic-and-protocols.md'
old = text = path.read_text()
raw = (runs / '20260910T085538Z-03-live-market/classroom.txt').read_text()
market = raw[raw.index('10.1.1.2 / capture'):raw.index('===== 恢复检查前的行情模式 =====')]
text = block(text, '仅供展示 · 行情输出', short(market))
raw = (runs / '20260910T085544Z-03-market-paths/classroom.txt').read_text()
start = raw.index('===== 查行情组的成员端口 =====')
end = raw.index('\n', raw.index('20    233.74.125.32', start))
transports = '10.1.1.253 / verify\n' + raw[start:end] + '\n\n'
transports += raw[raw.index('Low-Latency-Ops / readback'):raw.index('===== 恢复检查前的行情模式 =====')]
text = block(text, '仅供展示 · 三模式输出', short(transports))
raw = (runs / '20260910T085551Z-03-live-order/classroom.txt').read_text()
order = raw[:raw.index('10.1.1.2 / capture')]
submit = raw.index('Low-Latency-Ops / first-trade')
order += raw[submit:raw.index('10.1.1.2 / capture', submit)]
order += raw[raw.index('Low-Latency-Ops / first-trade', submit + 1):]
text = block(text, '仅供展示 · 订单输出', short(order))
for left, right in [
    ('itch_types 中 A:94', 'itch_types 中 A:180'),
    ('本例第 5 帧', '本例第 9 帧'),
    ('窗口中的 E/F 也分别计数，未出现的类型不列出。', '本窗口只有 A/U，未出现的类型不列出。'),
    ('duplicate_delta=1712', 'duplicate_delta=1556'),
    ('55783 是本次 MANUAL', '55407 是本次 MANUAL'),
    ('order_ref=100025', 'order_ref=100022'),
    ('291.2200', '291.6300'), ('296.2200', '296.6300'),
    ('match=900025', 'match=900022'),
    ('287296～287495', '246200～246399'),
]:
    assert left in text, left
    text = text.replace(left, right)
patches.append((path, old, text))

path = root / 'Documents/newDoc/02-host-native-trading-system-baseline.md'
old = text = path.read_text()
for left, right in [('pid=8439', 'pid=16983'), ('pid=33649', 'pid=23449'),
                    ('pid=33655', 'pid=23455'), ('pid=18357', 'pid=25998'),
                    ('20260910T081653Z-02-trading-platform', platform)]:
    assert left in text, left
    text = text.replace(left, right)
runtime = (runs / '20260910T085308Z-02-onload-runtime-prep/raw/10.1.1.2-runtime.txt').read_text()
runtime = runtime[runtime.index('vm-2522-02 / verify'):]
text = block(text, 'Trader .2 的四项检查结果', '\n'.join(line.rstrip() for line in runtime.splitlines()))
raw = (runs / '20260910T085512Z-02-igmp-feed/raw/classroom.txt').read_text()
lines = [line for line in raw.splitlines() if re.match(r'\d\d:\d\d:\d\d\.', line) or
         re.match(r'\d+ packets (captured|received|dropped)', line) or line.startswith('market_mode=')]
lines = [line for line in lines if line != 'market_mode=MULTICAST']
lines.insert(-1, '===== 恢复检查前的行情模式 =====')
start = text.index('```text\n16:18:')
end = text.index('```', start + 8)
text = text[:start] + '```text\n' + '\n'.join(lines) + '\n' + text[end:]
trade = (runs / platform / 'raw/first-trade.txt').read_text()
text = block(text, '首单结果示例。', trade)
text = text.replace('`2955700` 是 `295.57`', '`2956300` 是 `295.63`')
review = (runs / '20260910T085525Z-02-readonly-review/raw/classroom.txt').read_text()
state = next(line for line in review.splitlines() if line.startswith('market_mode='))
text = re.sub(r'^market_mode=UNICAST integrity=HEALTHY next_expected=\d+ trading_gate=OPEN$', state, text, flags=re.M)
patches.append((path, old, text))

print('*** Begin Patch')
for path, old, new in patches:
    assert old != new, path
    print('*** Update File: ' + str(path.relative_to(root)))
    for line in list(difflib.unified_diff(old.splitlines(), new.splitlines(), n=3))[2:]:
        print('@@' if line.startswith('@@') else line)
print('*** End Patch')
