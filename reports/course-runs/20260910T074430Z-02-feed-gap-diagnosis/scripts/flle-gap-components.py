import datetime
import json
import pathlib
import socket
import time

out = pathlib.Path('/financial-low-latency/Documents/reports/course-runs/20260910T074430Z-02-feed-gap-diagnosis/raw')
keys = ['role', 'session', 'next_expected', 'last_delivered', 'first_pending', 'highest_received', 'pending', 'gap_size', 'gap_age_ms', 'integrity', 'trading_gate', 'market_receiver_ready', 'stats']
results = []
for label, host, port in [('auto', '10.1.1.2', 48121), ('manual', '10.1.1.2', 48122), ('exchange', '10.1.1.1', 48120)]:
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(b'STATE\n')
        connection.shutdown(socket.SHUT_WR)
        data = connection.makefile('rb').readline()
    state = json.loads(data)
    (out / (label + '-direct-state.json')).write_bytes(data)
    entry = {'component': label, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), **{key: state[key] for key in keys if key in state}}
    if state.get('gap_age_ms'):
        entry['approx_gap_start_utc'] = datetime.datetime.fromtimestamp(time.time() - state['gap_age_ms'] / 1000, datetime.timezone.utc).isoformat()
    results.append(entry)
(out / 'components-summary.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
