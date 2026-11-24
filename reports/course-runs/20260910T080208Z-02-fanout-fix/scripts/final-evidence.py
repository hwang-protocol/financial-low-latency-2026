"""Summarize completed observations without replacing their raw receipts."""
import hashlib
import json
from pathlib import Path
import re


root = Path('/financial-low-latency')
runs = root / 'Documents/reports/course-runs'
state = root / 'Documents/reports/run-state'
maintenance = runs / '20260910T080208Z-02-fanout-fix'
diagnosis = runs / '20260910T074430Z-02-feed-gap-diagnosis'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


soak = read(state / '02-full-source-soak.json')
normal = read(state / '02-normal-speed-check.json')
resets = read(state / '02-reset-lock-check.json')
replay = read(state / '00-03-fanout-replay.json')
assert soak['status'] == normal['status'] == resets['status'] == 'PASS'
assert soak['restored'] and soak['old_gap_sequence_covered'] and normal['seconds'] >= 600
assert normal['prior'] == soak['run_id']
assert len(replay['cards']) == 21 and all(card['status'] == 'PASS' for card in replay['cards'])
assert 'Ran 200 tests' in (maintenance / 'raw/local-full-200-final.txt').read_text()
assert (maintenance / 'raw/local-full-200-final.txt').read_text().rstrip().endswith('OK')
assert 'ITERATIONS=100 TESTS=300 PASS' in (maintenance / 'raw/builder-integrity-repeat.txt').read_text()
sample_path = runs / soak['run_id'] / 'raw/samples.jsonl'
max_pending = {'auto': 0, 'manual': 0}
with sample_path.open() as source:
    count = 0
    for line in source:
        sample = json.loads(line)
        count += 1
        for role in max_pending:
            client = sample[role]
            assert client['integrity'] == 'HEALTHY' and client['gaps'] == 0
            assert not client['resync_required'] and client['bad_packets'] == 0
            max_pending[role] = max(max_pending[role], client['pending'])
assert count == soak['samples'] and not any(max_pending.values())
memory = {}
for path in sorted((runs / soak['run_id'] / 'raw').glob('sample-*-host.txt')):
    host = read(path)
    for process in host['processes']:
        command = process['command']
        if '/flle-feed-receiver ' in command:
            role = 'receiver'
        elif '/flle-trader ' in command and '--feed-socket ' in command:
            role = re.search(r'--role (\w+)', command)[1]
        else:
            continue
        rss = int(next(line for line in process['memory'] if line.startswith('VmRSS:')).split()[1])
        item = memory.setdefault(role, {'min_rss_kib': rss, 'max_rss_kib': rss, 'pids': []})
        item['min_rss_kib'] = min(item['min_rss_kib'], rss)
        item['max_rss_kib'] = max(item['max_rss_kib'], rss)
        if process['pid'] not in item['pids']:
            item['pids'].append(process['pid'])
receiver = read(runs / soak['run_id'] / 'raw/after-gateway.json')['feed_receiver']
assert receiver['overflow_disconnects'] == receiver['discarded_queue_packets'] == 0
result = dict(
    date='2026-09-10', status='BOUNDED_LIVE_PASS',
    authorization='User approved deployment, clearing simulated trades, and sequential chapters 0 through 3.',
    platform_run='20260910T085337Z-02-trading-platform',
    diagnosis=dict(run=diagnosis.name, old_platform='20260910T043800Z-02-trading-platform',
                   highest_received=11541278, auto_received=11540147, manual_received=11541278,
                   receiver_slow_drops=1131, live_counter_samples=3,
                   udp_socket_drops=[0, 0], udp_in_errors=0, udp_rcvbuf_errors=0,
                   gap_next_expected=7641279, trigger='UNKNOWN; external configuration or scheduling pause not excluded',
                   old_receiver_sha256='ca172ec5300468d3cec02f769594d48ed7520beb9b820645674dd997084de404'),
    fixed_local_reproduction=read(maintenance / 'raw/local-fanout-reproduction.json'),
    old_local_reproduction=read(diagnosis / 'raw/local-fanout-reproduction.json'),
    fixed_local_large_burst=read(maintenance / 'raw/local-10000-packet-burst.json'),
    tests=dict(local_total=200, local_passed=200, builder_total=200, builder_passed=191,
               builder_docs_only_skipped=9, builder_integrity_iterations=100, builder_integrity_tests=300,
               ch02_igmp=9, ch02_classroom=5, ch02_preparation=3, ch02_iommu='PASS',
               ch03_classroom=17, ch03_order_selection=3),
    sequential=dict(run=replay['run_id'], cards=[{key:card[key] for key in
         ['id','chapter','host','sha256','status','exit_code','seconds','result_runs']} for card in replay['cards']]),
    resets=resets, accelerated_soak=soak, normal_observation=normal,
    soak_memory_samples=memory, receiver_after_soak=receiver,
    final_readonly=read(maintenance / 'raw/final-readonly.json'),
    final_trade=(maintenance / 'raw/final-first-trade.txt').read_text(),
    document_audit=read(maintenance / 'raw/document-audit.json'),
    browser=read(maintenance / 'raw/browser-final/results.json'),
    failed_or_interrupted_runs=[
        dict(run='20260910T081937Z-02-full-source-soak',status='INTERRUPTED',samples=1135,
             seconds=1176.864016753,reason='Observer exited 143; sender unknown; COMPLETE not recorded; restored speed 1.'),
        dict(run='20260910T084145Z-02-full-source-soak',status='FAIL',reason='Reset lock fd 9 inherited by daemons; fixed and twice revalidated.'),
        dict(run='20260910T084525Z-00-03-fanout-replay',status='FAIL',reason='New test queried management before listener readiness; fixture fixed and 100 rounds revalidated.')],
    limits=['Complete source was replayed at 30x in UNICAST, not 6.5 hours wall time at 1x.',
            'Sequential replay reused the prepared environment; no new snapshot restoration or cold installation was performed.',
            'Normal-speed observation is 600 seconds; finite tests do not prove zero future faults.',
            'Hardware/network loss and sustained overload still inhibit trading and require consistent resynchronization.',
            'No new chapter 4-10 device or performance validation; no Git history writes.'])
assert result['final_readonly']['status'] == 'PASS'
assert 'verdict=FIRST_TRADE_PASS' in result['final_trade']
assert 'history=CLIENT_AND_EXCHANGE strategy_unchanged=true' in result['final_trade']
result['archive_sha256'] = {str(path.relative_to(root)): digest(path) for path in
    [maintenance/'ARCHIVE_SHA256SUMS', diagnosis/'SHA256SUMS', maintenance/'final-source.tgz',
     runs/soak['run_id']/'ARCHIVE_SHA256SUMS', runs/normal['run_id']/'ARCHIVE_SHA256SUMS',
     runs/replay['run_id']/'ARCHIVE_SHA256SUMS', runs/resets['run_id']/'ARCHIVE_SHA256SUMS']}
result['sealed_run_archives'] = {}
for line in (maintenance/'raw/closed-run-archives.txt').read_text().splitlines():
    name = line.split()[0]
    manifest = runs/name/'ARCHIVE_SHA256SUMS'
    assert manifest.is_file(), name
    result['sealed_run_archives'][name] = digest(manifest)
result['final_documents_sha256'] = {str(path.relative_to(root)): digest(path)
    for path in sorted((root/'Documents/newDoc').glob('0[0-3]-*.md'))}
print(json.dumps(result, ensure_ascii=False, indent=2))
