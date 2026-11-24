#!/usr/bin/env python3
"""Run the actual Guardian shell with offline transports and a paused feed."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[5]
HELPER = ROOT / 'Documents/newDoc/assets/common/feed-guardianctl.sh'
with tempfile.TemporaryDirectory(prefix='flle-paused-recovery-test-') as tmp:
    root = Path(tmp)
    common = root / 'Documents/newDoc/assets/common'
    common.mkdir(parents=True)
    state = root / 'Documents/reports/run-state/02-trading-baseline.env'
    state.parent.mkdir(parents=True)
    state.write_text('RUN_ID=offline-02-trading-platform\n')
    app = root / 'apps/flle-trading-lab'
    (app/'scripts').mkdir(parents=True)
    (app/'scripts/transport_labctl.sh').write_text("printf '%s\\n' '{\"mode\":\"SFC\",\"transition\":\"READY\",\"owner\":\"sfc\"}'\n")
    fakebin = root/'bin'; fakebin.mkdir()
    # Only known read-only SSH requests are answered. Anything else fails.
    ssh = fakebin/'ssh'
    ssh.write_text("""#!/usr/bin/env bash
case "$*" in
  *deployed.sha256*) printf '%064d  flle-trader\\n' 0 ;;
  *source.sha256*) find apps/flle-trading-lab -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}' ;;
  *'bash -s --'*) text="$(cat)"; case "$text" in *'ok=0'*) echo 1;; *) exit 99;; esac ;;
  *) exit 99 ;;
esac
""")
    ssh.chmod(0o755)
    curl = fakebin/'curl'
    curl.write_text('#!/bin/sh\nprintf \'%s\\n\' \''+json.dumps({'feed': {'integrity': 'HEALTHY'}, 'strategy': {'enabled': False}, 'health': {'trader_auto': {'status': 'ONLINE'}}})+"'\n")
    curl.chmod(0o755)
    (common/'flle-remote.sh').write_text('FLLE_SSH_OPTS=()\n')
    wait = common/'wait-feed-state.py'
    wait.write_text("from pathlib import Path\nPath('feed-wait-called').touch()\nprint('paused: session empty, next_expected=0')\nraise SystemExit(1)\n")
    script = root/'guardian.sh'
    script.write_text(HELPER.read_text().replace('cd /financial-low-latency', 'cd '+str(root)))
    env = dict(os.environ, PATH=str(fakebin)+':'+os.environ['PATH'])
    for profile in ['direct', 'unicast-only']:
        result = subprocess.run(['bash', str(script), profile, '--defer-feed-check'], env=env, text=True, capture_output=True, timeout=5)
        assert result.returncode == 0, result.stderr
        assert 'guardian=PROCESS_READY feed_check=DEFERRED' in result.stdout
        assert not (root/'feed-wait-called').exists(), 'paused setup waited for packets'
    # Existing callers retain packet readiness and get a useful timeout diagnostic.
    result = subprocess.run(['bash', str(script), 'direct'], env=env, text=True, capture_output=True, timeout=5)
    assert result.returncode != 0
    assert 'guardian feed check failed' in result.stderr and 'next_expected=0' in result.stderr
    assert (root/'feed-wait-called').exists()
    # Exercise the real cleanup body with fake transport functions. Restart must
    # precede the strict feed check, and all original playback settings survive.
    actions = (HELPER.parent.parent/'09-verilator/live-support/stage-actions.sh').read_text()
    # cleanup delegates to restore_reception; keep both real functions together.
    # Stop before hold so this fixture cannot invoke the live UI/API checks.
    recovery_functions = 'restore_reception(){' + actions.split('restore_reception(){', 1)[1].split('\nhold(){', 1)[0]
    (root/'raw').mkdir()
    (common/'feed-guardianctl.sh').write_text('test "$2" = --defer-feed-check\n')
    (common/'check-filter-handoff.sh').write_text('exit 0\n')
    from itertools import product
    for playback, mode in product(['PLAYING', 'PAUSED'], ['MULTICAST_A', 'MULTICAST_B', 'DUAL', 'MULTICAST', 'UNICAST']):
        harness = """set -Eeuo pipefail
OUT="$1"; COMMON="$2"; ORIGINAL_MODE="$4"; ORIGINAL_PLAYBACK="$3"; REMOTE=/offline
playing=0
remote2(){ return 1; }
post(){ if test "$1" = market; then printf '%s\\n' "$2" >"$OUT/raw/request-market.json"; fi; }
state(){ printf '%s\\n' '{"session":"before"}' >"$OUT/raw/$1.json"; }
replay(){ case "$1" in RESTART) playing=1;; PAUSE) playing=0;; esac; }
feed(){ test "$playing" = 1; }
"""+recovery_functions+"\ncleanup\ntest \"$playing\" = "+('1' if playback == 'PLAYING' else '0')+'\n'
        # The fallback preflight deliberately requires the absence of an adapter.
        harness = harness.replace('remote2(){ return 1; }', 'remote2(){ case "$*" in *"test -f"*) return 1;; *) return 0;; esac; }')
        result = subprocess.run(['bash', '-c', harness, 'test', str(root), str(common), playback, mode], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0, result.stderr
        assert json.loads((root/'raw/request-market.json').read_text())['market_mode'] == mode
print('PASS paused Guardian setup, legacy strict check diagnostics, restart-before-feed recovery and original playback')

# Use the exact remote preflight expression from the production script.
import re
exprs = re.findall(r'remote2 "(test ! -e /var/tmp/flle-market-filter.cmd[^"\n]+)"', (HELPER.parent.parent/'09-verilator/live-support/stage-actions.sh').read_text())
assert len(exprs) == 2
with tempfile.TemporaryDirectory(prefix='flle-control-preflight-') as tmp:
    control = Path(tmp)/'control.cmd'
    for expr in exprs:
        script = expr.replace('/var/tmp/flle-market-filter.cmd', str(control))
        for occupied in [False, True]:
            if occupied: control.touch()
            else: control.unlink(missing_ok=True)
            for process_exists in [False, True]:
                stub = 'pgrep(){ return '+('0' if process_exists else '1')+'; }; '
                result = subprocess.run(['bash', '-c', stub+script], capture_output=True)
                assert (result.returncode == 0) == (not occupied and not process_exists)
print('PASS both remote preflight checks reject a leftover control file or process')
