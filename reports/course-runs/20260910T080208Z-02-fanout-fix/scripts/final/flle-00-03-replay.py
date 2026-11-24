import argparse
import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path('/financial-low-latency')
STATE = ROOT / 'Documents/reports/run-state/00-03-fanout-replay.json'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(state):
    value = json.dumps(state, ensure_ascii=False, indent=2) + '\n'
    STATE.write_text(value)
    (ROOT / state['out'] / 'session.json').write_text(value)


parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['init', 'run'])
parser.add_argument('--through', default='03', choices=['00', '01', '02', '03'])
args = parser.parse_args()
if args.action == 'init':
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-00-03-fanout-replay'
    out = ROOT / 'Documents/reports/course-runs' / run_id
    for name in ['cards', 'raw', 'source']:
        (out / name).mkdir(parents=True)
    state = dict(run_id=run_id, out=str(out.relative_to(ROOT)), started=now(), cards=[],
                 authorization='User requested ch00-03 sequential replay and approved redeployment and clearing simulated trades.')
    for path in sorted((ROOT / 'Documents/newDoc').glob('0[0-3]-*.md')):
        text = path.read_text()
        (out / 'source' / path.name).write_text(text)
        matches = list(re.finditer(r'<div style="border-left:6px solid (#[a-fA-F0-9]+);[^\n]*</div>', text))
        number = 0
        for index, match in enumerate(matches):
            label = html.unescape(re.sub(r'<[^>]+>', '', match.group()))
            if match.group(1).lower() != '#15803d' or '需要运行' not in label:
                continue
            number += 1
            end = matches[index+1].start() if index+1 < len(matches) else len(text)
            blocks = re.findall(r'^```bash\n(.*?)^```', text[match.end():end], re.M | re.S)
            assert len(blocks) == 1, (path, label, len(blocks))
            code = blocks[0]
            card_id = path.name[:2] + f'-{number:02d}'
            (out / 'cards' / (card_id + '.sh')).write_text(code)
            state['cards'].append(dict(id=card_id, chapter=path.name[:2], label=label,
                                       source=str(path.relative_to(ROOT)), line=text.count('\n',0,match.start())+1,
                                       sha256=hashlib.sha256(code.encode()).hexdigest(), status='PENDING'))
    assert len(state['cards']) == 21, len(state['cards'])
    save(state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
else:
    state = json.loads(STATE.read_text())
    out = ROOT / state['out']
    for card in state['cards']:
        if card['chapter'] > args.through or card['status'] == 'PASS':
            continue
        if card['status'] != 'PENDING':
            raise SystemExit('Review failed/running card before proceeding: ' + card['id'])
        source = out / 'cards' / (card['id'] + '.sh')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == card['sha256']
        card.update(status='RUNNING', started=now())
        save(state)
        print('START', card['id'], card['label'][:90], flush=True)
        before = set((ROOT / 'Documents/reports/course-runs').iterdir())
        start = time.monotonic()
        if card['chapter'] == '00':
            command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', 'root@10.1.1.101', 'bash', '-s']
            input_data = source.read_bytes()
            card['host'] = '10.1.1.101'
        else:
            command = ['bash', str(source)]
            input_data = None
            card['host'] = '10.1.1.111'
        with (out / 'raw' / (card['id'] + '.txt')).open('wb') as log:
            result = subprocess.run(command, input=input_data, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        card.update(status='PASS' if result.returncode == 0 else 'FAIL', exit_code=result.returncode,
                    finished=now(), seconds=time.monotonic()-start,
                    result_runs=[str(path.relative_to(ROOT)) for path in sorted(set((ROOT / 'Documents/reports/course-runs').iterdir())-before)])
        save(state)
        print('END', card['id'], card['status'], 'rc='+str(result.returncode), flush=True)
        print((out / 'raw' / (card['id']+'.txt')).read_text()[-1800:], flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    print('COMPLETED_THROUGH=' + args.through, flush=True)
