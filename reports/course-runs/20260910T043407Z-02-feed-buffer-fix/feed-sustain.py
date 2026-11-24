import json
import sys
import time
import urllib.request

start = time.monotonic()
last_print = -10.0
while time.monotonic() - start < 600:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as response:
        state = json.load(response)
    elapsed = time.monotonic() - start
    feed = state.get('feed') or {}
    sample = {'elapsed_seconds': round(elapsed, 2), 'session': state.get('session'),
              'market_mode': state.get('market_mode'), 'feed': feed}
    healthy = (feed.get('integrity') == 'HEALTHY' and feed.get('trading_gate') == 'OPEN'
               and feed.get('session') == state.get('session')
               and state.get('market_mode') == 'UNICAST')
    if not healthy or elapsed - last_print >= 10:
        print(json.dumps(sample, separators=(',', ':')), flush=True)
        last_print = elapsed
    if not healthy:
        raise SystemExit('Feed lost healthy UNICAST state during sustained replay')
    if elapsed >= 180 and int(feed.get('next_expected') or 0) >= 1000000:
        print(json.dumps(sample, separators=(',', ':')), flush=True)
        raise SystemExit(0)
    time.sleep(2)
raise SystemExit('Replay did not advance past 1000000 within 600 seconds')
