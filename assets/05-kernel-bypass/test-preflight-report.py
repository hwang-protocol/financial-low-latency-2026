#!/usr/bin/env python3
"""Exercise concise preflight reports with mocked commands, never remote hosts."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'assets/05-kernel-bypass/02-four-path-preflight.sh'
MOCKS = r'''
python3(){
  if [[ "$1" = *posix-qos-package.py ]]; then
    if [[ "$SCENARIO" = qos-archive-failure ]]; then echo 'POSIX archive mismatch'; return 4; fi
    echo 'posix_qos_archive=PASS'; return 0
  fi
  command python3 "$@"
}
sha256sum(){
  if [[ "$*" = '-c -' ]]; then
    command cat >/dev/null
    if [[ "$SCENARIO" = archive-failure ]]; then echo 'archive hash mismatch'; return 2; fi
    echo 'archive: OK'
  else command sha256sum "$@"; fi
}
bash(){
  if [[ "$1" = *four-path-build-contract-audit.sh ]]; then
    if [[ "$SCENARIO" = contract-failure ]]; then echo 'contract mismatch'; return 3; fi
    echo 'source_binary_contract=PASS'
    echo 'preserved audit details' >"$2/check.txt"
    return
  fi
  if [[ "$1" = *transport_labctl.sh ]]; then
    echo 'control_assets=PASS symbols=AAPL,NVDA replay_bytes=561727241'
    if [[ "$SCENARIO" = native-failure ]]; then echo 'native preflight failed' >&2; return 7; fi
    if [[ "$SCENARIO" = duplicate-row ]]; then echo 'control_assets=PASS symbols=AAPL,NVDA'; fi
    if [[ "$SCENARIO" != missing-row ]]; then
      if [[ "$SCENARIO" = failed-row ]]; then echo 'builder_tools=FAIL host=10.1.1.101 compiler=g++-11'
      elif [[ "$SCENARIO" = missing-field ]]; then echo 'builder_tools=PASS host=10.1.1.101'
      else echo 'builder_tools=PASS host=10.1.1.101 compiler=g++-11'; fi
    fi
    case "$SCENARIO" in
      baseline) echo 'exchange_rss_preflight=PASS table=baseline-0-1-2-3';;
      unknown-rss) echo 'exchange_rss_preflight=PASS table=unknown';;
      *) echo 'exchange_rss_preflight=PASS table=measure-all-1';;
    esac
    echo 'transport_preflight=PASS queue=DEQUE_CV'
    echo 'extra native diagnostics are retained'
    return 0
  fi
  command bash "$@"
}
'''

results = []
scenarios = {'baseline': 0, 'measurement': 0, 'archive-failure': 2,
             'qos-archive-failure': 4, 'contract-failure': 3, 'native-failure': 7, 'missing-row': 1,
             'duplicate-row': 1, 'failed-row': 1, 'unknown-rss': 1, 'missing-field': 1}
with tempfile.TemporaryDirectory(prefix='flle-preflight-test-') as temporary:
    base = Path(temporary)
    mocks = base / 'mocks.sh'
    mocks.write_text(MOCKS)
    for scenario, expected in scenarios.items():
        work = base / scenario
        work.mkdir()
        script = work / 'check.sh'
        script.write_text(SCRIPT.read_text().replace('cd /qyt-fll',
                                                     'cd ' + shlex.quote(str(work)), 1))
        env = dict(os.environ, BASH_ENV=str(mocks), SCENARIO=scenario)
        run = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                             env=env, timeout=10)
        assert run.returncode == expected, (scenario, run.returncode, run.stdout, run.stderr)
        reports = list((work / 'reports/course-runs').iterdir())
        assert len(reports) == 1
        report = reports[0]
        output = (report / 'raw/result.txt').read_text()
        assert ('六项全部通过' in output) == (expected == 0)
        if expected == 0:
            for number in range(1, 7):
                assert output.count(f'[{number}/6]') == 1
            assert 'extra native diagnostics' not in output
            assert 'extra native diagnostics' in (report / 'raw/preflight.txt').read_text()
            assert ('当前为普通配置' in output) == (scenario == 'baseline')
        else:
            assert '：FAIL' in output
        assert f'EXIT_CODE={expected}' in (report / 'run.env').read_text()
        for line in (report / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split(None, 1)
            assert hashlib.sha256((report / name).read_bytes()).hexdigest() == digest
        results.append({'scenario': scenario, 'exit_code': expected, 'status': 'PASS'})
print(json.dumps(results, ensure_ascii=False, indent=2))
