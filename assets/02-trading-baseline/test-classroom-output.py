#!/usr/bin/env python3
"""Run the actual classroom wrappers against local fixtures; never contact a VM."""
import os
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path('assets/02-trading-baseline')
CTL = Path('apps/flle-trading-lab/scripts/transport_labctl.sh')
TRADE = Path('apps/flle-trading-lab/tests/first_trade.py')
CAPS = CTL.with_name('prepare-course-capabilities.sh')
AUDIT = Path('assets/05-kernel-bypass/four-path-build-contract-audit.sh')


def put(root, path, text):
    dest = root / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    return dest


def wrapper(root, name):
    put(root, CAPS, '''#!/bin/bash
printf 'capabilities\\n' >>"$CALLS"
if test "${FAILED_STAGE:-}" = capabilities; then echo 'fixture failure' >&2; exit 37; fi
echo course_capabilities=PREPARED
''')
    return put(root, ASSETS / name, (ROOT / ASSETS / name).read_text()
               .replace('/qyt-fll', str(root))
               .replace('/run/lock/flle-platform-deploy.lock', str(root / 'deploy.lock')))


class ClassroomOutput(unittest.TestCase):
    def test_retry_interrupted_build_cleans_pending_run_before_new_deployment(self):
        for cleanup_rc in (0, 47):
            with self.subTest(cleanup_rc=cleanup_rc), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                old_run = '20000101T000000Z-02-trading-platform'
                state = Path('reports/run-state/02-trading-baseline.env')
                pending = put(root, Path(str(state)+'.pending'), f'RUN_ID={old_run}\n')
                old_out = Path('reports/course-runs')/old_run
                original = put(root, old_out/'raw/03-deploy.txt', 'original build failure\n')
                fixture = '''#!/bin/bash
printf '%s\\n' "$1" >>"$CALLS"
if test "$1" = stop; then exit "$CLEANUP_RC"; fi
echo "step=$1"
'''
                put(root, CTL, fixture)
                put(root, AUDIT, 'echo audit >>"$CALLS"\necho audit=PASS\n')
                script = wrapper(root, '01-restore-trading-lab.sh')
                result = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                    env=dict(os.environ, CALLS=str(root/'calls'), CLEANUP_RC=str(cleanup_rc)))
                self.assertEqual(result.returncode, cleanup_rc, result.stdout+result.stderr)
                calls = (root/'calls').read_text().splitlines()
                self.assertEqual(original.read_text(), 'original build failure\n')
                if cleanup_rc:
                    self.assertEqual(calls, ['stop'])
                    self.assertTrue(pending.exists())
                    self.assertFalse((root/state).exists())
                    self.assertNotIn('platform=READY', result.stdout)
                else:
                    self.assertEqual(calls, ['stop', 'preflight', 'audit', 'deploy',
                                             'capabilities', 'baseline', 'verify', 'boot-enable'])
                    self.assertFalse(pending.exists())
                    self.assertEqual((root/old_out/'aborted-deploy.env').read_text(), f'RUN_ID={old_run}\n')
                    self.assertNotIn(old_run, (root/state).read_text())
                    self.assertIn('platform=READY', result.stdout)

    def test_default_entry_reuses_snapshot_and_stops_if_topup_fails(self):
        for failed in ('', 'capabilities'):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                run = '20000101T000000Z-02-trading-platform'
                state = Path('reports/run-state/02-trading-baseline.env')
                original = f'RUN_ID={run}\nPROFILE=UNIFIED_TRADING_PLATFORM\n'
                put(root, state, original)
                evidence = put(root, Path('reports/course-runs')/run/'raw/old.txt', 'keep orders\n')
                put(root, CTL, '#!/bin/bash\nprintf "%s\\n" "$1" >>"$CALLS"\necho platform=VERIFIED\n')
                put(root, CTL.with_name('verify-feed-receiver.py'), '# fixture verifier\n')
                put(root, Path('bin/curl'), '#!/bin/bash\necho \'{"market_network":{"market_schema":"udp-multicast-ab-v1"}}\'\n').chmod(0o755)
                put(root, Path('bin/ssh'), '#!/bin/bash\ncat >/dev/null\nexit 0\n').chmod(0o755)
                result = subprocess.run(['bash', str(wrapper(root, '01-restore-trading-lab.sh'))],
                    capture_output=True, text=True,
                    env=dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'],
                             CALLS=str(root/'calls'), FAILED_STAGE=failed))
                self.assertEqual(result.returncode, 37 if failed else 0, result.stdout+result.stderr)
                self.assertEqual((root/state).read_text(), original)
                self.assertEqual(evidence.read_text(), 'keep orders\n')
                self.assertEqual((root/'calls').read_text().splitlines(),
                                 ['verify', 'capabilities'] + ([] if failed else ['verify', 'boot-enable']))
                self.assertEqual('ALREADY_DEPLOYED' in result.stdout, not bool(failed))
                self.assertFalse(Path(str(root/state)+'.pending').exists())

    def test_snapshot_topup_preserves_run_and_never_redeploys(self):
        for failed in ('', 'capabilities'):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                run_id = '20000101T000000Z-02-trading-platform'
                state = Path('reports/run-state/02-trading-baseline.env')
                original = f'RUN_ID={run_id}\nPROFILE=UNIFIED_TRADING_PLATFORM\n'
                put(root, state, original)
                put(root, CTL, '#!/bin/bash\nprintf "%s\\n" "$1" >>"$CALLS"\necho platform=VERIFIED\n')
                result = subprocess.run(
                    ['bash', str(wrapper(root, '01-restore-trading-lab.sh')), '--prepare-capabilities'],
                    capture_output=True, text=True,
                    env=dict(os.environ, CALLS=str(root/'calls'), FAILED_STAGE=failed))
                self.assertEqual(result.returncode, 37 if failed else 0, result.stdout+result.stderr)
                self.assertEqual((root/state).read_text(), original)
                self.assertEqual((root/'calls').read_text().splitlines(),
                                 ['verify', 'capabilities'] + ([] if failed else ['verify', 'boot-enable']))
                self.assertNotIn('platform=READY', result.stdout)
                self.assertEqual('existing_session=PRESERVED' in result.stdout, not bool(failed))

    def test_old_market_requires_upgrade_and_preserves_old_records(self):
        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                old_run = '20000101T000000Z-02-trading-platform'
                state = Path('reports/run-state/02-trading-baseline.env')
                old_text = f'RUN_ID={old_run}\nWEB_URL=http://unused.invalid/\n'
                put(root, state, old_text)
                old = Path('reports/course-runs') / old_run
                evidence = put(root, old / 'raw/old-output.txt', 'original record\n')
                put(root, CTL, '''#!/bin/bash
printf '%s\\n' "$*" >>"$CALLS"
if test "$1" = reuse-state; then echo CLEAN; else echo "step=$1"; fi
''')
                put(root, AUDIT, 'echo audit=PASS\n')
                curl = put(root, Path('bin/curl'), '#!/bin/bash\necho \'{"market_mode":"UNICAST"}\'\n')
                curl.chmod(0o755)
                script = wrapper(root, '01-restore-trading-lab.sh')
                result = subprocess.run(['bash', str(script)] + (['--upgrade-ab'] if upgrade else []),
                    capture_output=True, text=True,
                    env=dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'], CALLS=str(root/'calls')))
                self.assertEqual(result.returncode, 0 if upgrade else 2, result.stdout + result.stderr)
                calls = (root/'calls').read_text().splitlines()
                self.assertEqual(calls[0], f'verify {old_run} --allow-legacy-market')
                self.assertEqual(evidence.read_text(), 'original record\n')
                if upgrade:
                    self.assertEqual(calls[1], f'stop {old_run}')
                    self.assertEqual([x.split()[0] for x in calls],
                                     ['verify', 'stop', 'reuse-state', 'reuse-state', 'preflight', 'deploy', 'capabilities', 'baseline', 'verify', 'boot-enable'])
                    self.assertEqual((root/old/'retired-platform.env').read_text(), old_text)
                    self.assertNotEqual((root/state).read_text(), old_text)
                    self.assertIn('platform=READY', result.stdout)
                else:
                    self.assertEqual(len(calls), 1)
                    self.assertEqual((root/state).read_text(), old_text)
                    self.assertIn('--upgrade-ab', result.stderr)

    def test_snapshot_restore_retires_stale_pointer_before_fresh_build(self):
        for residual in (False, True):
            with self.subTest(residual=residual), tempfile.TemporaryDirectory() as td:
                root=Path(td); old_run='20000101T000000Z-02-trading-platform'
                state=Path('reports/run-state/02-trading-baseline.env')
                put(root,state,f'RUN_ID={old_run}\n')
                put(root,Path('reports/course-runs')/old_run/'raw/old.txt','saved evidence\n')
                put(root,CTL,'''#!/bin/bash
printf '%s\\n' "$1" >>"$CALLS"
case "$1" in
 verify) test "$2" != 20000101T000000Z-02-trading-platform || exit 1;;
 reuse-state) if test "$RESIDUAL" = 1 && test ! -f "$CALLS.retired"; then echo DIRTY; else echo CLEAN; fi;;
 retire-snapshot-controller) touch "$CALLS.retired";;
esac
''')
                put(root,AUDIT,'echo audit=PASS\n')
                script=wrapper(root,'01-restore-trading-lab.sh')
                result=subprocess.run(['bash',str(script)],capture_output=True,text=True,
                    env=dict(os.environ,CALLS=str(root/'calls'),RESIDUAL=str(int(residual))))
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                calls=(root/'calls').read_text().splitlines()
                self.assertEqual(calls.count('retire-snapshot-controller'),int(residual))
                self.assertEqual(calls[-6:],['preflight','deploy','capabilities','baseline','verify','boot-enable'])
                self.assertIn('platform=READY',result.stdout)
                self.assertNotIn('ALREADY_DEPLOYED',result.stdout)
                self.assertFalse(Path(str(root/state)+'.pending').exists())

    def test_ab_exchange_cannot_hide_a_legacy_receiver_on_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);old_run='20000101T000000Z-02-trading-platform'
            state=Path('reports/run-state/02-trading-baseline.env')
            put(root,state,f'RUN_ID={old_run}\n')
            put(root,Path('reports/course-runs')/old_run/'raw/old.txt','old\n')
            put(root,CTL,'echo verified-processes\n')
            put(root,CTL.with_name('verify-feed-receiver.py'),'# supplied via stdin\n')
            put(root,Path('bin/curl'),'''#!/bin/bash
echo '{"market_network":{"market_schema":"udp-multicast-ab-v1"}}'
''').chmod(0o755)
            put(root,Path('bin/ssh'),'#!/bin/bash\necho receiver-mismatch >&2\nexit 1\n').chmod(0o755)
            result=subprocess.run(['bash',str(wrapper(root,'01-restore-trading-lab.sh'))],capture_output=True,text=True,
                env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH']))
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertNotIn('ALREADY_DEPLOYED',result.stdout)
            self.assertIn('--upgrade-ab',result.stderr)
            self.assertEqual((root/state).read_text(),f'RUN_ID={old_run}\n')

    def test_deploy_success_and_every_failed_stage(self):
        for failed in ('', 'preflight', 'audit', 'deploy', 'capabilities', 'baseline', 'verify', 'boot-enable'):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                fixture = '''#!/bin/bash
printf '%s\\n' "$1" >>"$CALLS"
printf 'step=%s\\n' "$1"
printf '{"large_state":"fixture-only"}\\n'
if test "$1" = "$FAILED_STAGE"; then echo 'fixture failure' >&2; exit 37; fi
'''
                put(root, CTL, fixture)
                curl = put(root, Path('bin/curl'), '''#!/bin/bash
echo '{"market_network":{"market_schema":"udp-multicast-ab-v1"}}'
''')
                curl.chmod(0o755)
                put(root, Path('bin/ssh'), '#!/bin/bash\nexit 0\n').chmod(0o755)
                put(root, CTL.with_name('verify-feed-receiver.py'), '# fixture verifier\n')
                put(root, AUDIT, fixture.replace('"$1"', 'audit'))
                script = wrapper(root, '01-restore-trading-lab.sh')
                result = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                    env=dict(os.environ, CALLS=str(root/'calls'), FAILED_STAGE=failed))
                self.assertEqual(result.returncode, 37 if failed else 0, result.stderr)
                expected = ['preflight', 'audit', 'deploy', 'capabilities', 'baseline', 'verify', 'boot-enable']
                if failed:
                    expected = expected[:expected.index(failed)+1]
                    self.assertIn('fixture failure', result.stdout)
                    self.assertNotIn('platform=READY', result.stdout)
                    self.assertNotIn('[配置说明]', result.stdout)
                    self.assertNotIn('[下一步]', result.stdout)
                else:
                    self.assertNotIn('{"large_state"', result.stdout)
                    self.assertIn('platform=READY', result.stdout)
                    for label in ('条件', '来源', '部署', '启动', '进程', '在线', '文件', '就绪', '配置', '能力'):
                        self.assertIn('[' + label + '说明]', result.stdout)
                    self.assertIn('不是同时运行的进程清单', result.stdout)
                    self.assertIn('运行 ②才提交首笔模拟订单', result.stdout)
                self.assertEqual((root/'calls').read_text().splitlines(), expected)
                out = next((root/'reports/course-runs').iterdir())
                raw = out/'raw'
                self.assertIn('large_state', (raw/'01-preflight.txt').read_text())
                self.assertIn('===== ① 查部署条件 =====', (raw/'restore.txt').read_text())
                state = root/'reports/run-state/02-trading-baseline.env'
                self.assertEqual(state.exists(), not bool(failed))
                self.assertEqual(Path(str(state)+'.pending').exists(), bool(failed))
                if not failed:
                    subprocess.run(['sha256sum', '--quiet', '-c', str(out/'SHA256SUMS')], check=True)
                    # Existing-platform path calls only verify and also hides JSON.
                    again = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                        env=dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'], CALLS=str(root/'calls'), FAILED_STAGE=''))
                    self.assertEqual(again.returncode, 0, again.stderr)
                    self.assertIn('ALREADY_DEPLOYED', again.stdout)
                    self.assertNotIn('{"large_state"', again.stdout)
                    self.assertIn('[在线说明]', again.stdout)
                    self.assertIn('[复用说明]', again.stdout)
                    self.assertNotIn('[配置说明]', again.stdout)
                    self.assertNotIn('profile=SOFTWARE', again.stdout)
                    self.assertEqual((root/'calls').read_text().splitlines(), expected+['verify', 'capabilities', 'verify', 'boot-enable'])

    def test_first_trade_keeps_failure_and_does_not_trade_after_bad_gate(self):
        for gate_rc, trade_rc in ((0, 0), (23, 0), (0, 42)):
            with self.subTest(gate_rc=gate_rc, trade_rc=trade_rc), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                put(root, CTL, 'echo "trader-manual=ONLINE"\necho \'{"state":"fixture-only"}\'\nexit "$GATE_RC"\n')
                put(root, TRADE, 'import os\nfrom pathlib import Path\nPath(os.environ["CALLED"]).touch()\nprint("result=fixture-only")\nraise SystemExit(int(os.environ["TRADE_RC"]))\n')
                put(root, Path('assets/02-trading-baseline/format_first_trade.py'),
                    (ROOT / ASSETS / 'format_first_trade.py').read_text())
                put(root, Path('reports/run-state/02-trading-baseline.env'),
                    'RUN_ID=LOCAL-FIXTURE\nWEB_URL=http://unused.invalid/\n')
                script = wrapper(root, '02-first-trade.sh')
                result = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                    env=dict(os.environ, GATE_RC=str(gate_rc), TRADE_RC=str(trade_rc), CALLED=str(root/'called')))
                self.assertEqual(result.returncode, gate_rc or trade_rc, result.stderr)
                self.assertEqual((root/'called').exists(), gate_rc == 0)
                raw = root/'reports/course-runs/LOCAL-FIXTURE/raw'
                self.assertIn('===== ①', (raw/'first-trade-classroom.txt').read_text())
                self.assertIn('fixture-only', (raw/'verify-before-trade.txt').read_text())
                if not gate_rc:
                    self.assertLess(result.stdout.index('$ python3'), result.stdout.index('result=fixture-only'))
                    self.assertNotIn('{"state"', result.stdout)
                    self.assertIn('[平台说明]', result.stdout)
                    self.assertNotIn('awk', result.stdout)
                if gate_rc or trade_rc:
                    self.assertNotIn('evidence=', result.stdout)
                else:
                    subprocess.run(['sha256sum', '--quiet', '-c', str(raw.parent/'FIRST_TRADE_SHA256SUMS')], check=True)

    def test_stage_no_matching_fields_is_not_a_business_failure(self):
        source = (ROOT/ASSETS/'01-restore-trading-lab.sh').read_text()
        function = source[source.index('stage(){'):source.index('\nif test -s "$STATE.pending"')]
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run(['bash', '-Eeuo', 'pipefail', '-c', function +
                '\nstage sample purpose "$1/raw.txt" printf "plain text\\n"', 'test', td], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('没有匹配的短读数', result.stdout)
            self.assertEqual((Path(td)/'raw.txt').read_text(), 'plain text\n')

    def test_runtime_prep_filters_install_logs_and_preserves_errors(self):
        for package_rc, remote_rc in ((0, 0), (19, 0), (0, 23)):
            with self.subTest(package_rc=package_rc, remote_rc=remote_rc), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                bindir = root/'bin'
                bindir.mkdir()
                for name, content in {
                    'scp': 'exit 0',
                    'ssh': 'cat >/dev/null; printf "build noise\\n%.0s" {1..100}; printf "fixture-host / verify\\n===== 查主机名 =====\\nfixture-host\\n"; exit "$REMOTE_RC"',
                }.items():
                    f = put(bindir, Path(name), '#!/bin/bash\n'+content+'\n')
                    f.chmod(0o755)
                put(root, Path('assets/common/install-offline-packages.py'),
                    'import os\nprint("package=fixture-only")\nraise SystemExit(int(os.environ["PACKAGE_RC"]))\n')
                put(root, ASSETS / 'extract-sfutils-source.py',
                    'import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text("fixture-only")\n')
                archive = put(root, Path('artifacts/blobs/x2522/onload/v9.0.2/onload-9f330e7-vm-2522-01.tgz'), 'fixture-only')
                script = wrapper(root, '00a-runtime-prep.sh')
                script.write_text(script.read_text()
                    .replace('/run/lock/flle-platform-runtime-prep.lock', str(root/'runtime.lock'))
                    .replace('998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2', hashlib.sha256(archive.read_bytes()).hexdigest()))
                result = subprocess.run(['bash', str(script)], capture_output=True, text=True,
                    env=dict(os.environ, PATH=str(bindir)+':'+os.environ['PATH'], PACKAGE_RC=str(package_rc), REMOTE_RC=str(remote_rc)))
                self.assertEqual(result.returncode, package_rc or remote_rc, result.stderr)
                out = next((root/'reports/course-runs').iterdir())
                self.assertIn('===== 查安装归档 =====', (out/'raw/result.txt').read_text())
                if not package_rc and not remote_rc:
                    self.assertIn('build noise', (out/'raw/10.1.1.1-runtime.txt').read_text())
                    self.assertNotIn('build noise', result.stdout)
                    self.assertIn('===== 查主机名 =====', result.stdout)
                    subprocess.run(['sha256sum', '--quiet', '-c', 'SHA256SUMS'], cwd=out, check=True)
                else:
                    self.assertNotIn('evidence=', result.stdout)

    def test_first_trade_document_uses_single_entry(self):
        chapter = (ROOT/'02-host-native-trading-system-baseline.md').read_text()
        script = (ROOT/ASSETS/'02-first-trade.sh').read_text()
        entry = f'cd /qyt-fll && bash {ASSETS}/02-first-trade.sh\n'
        blocks = re.findall(r'```bash\n(.*?)```', chapter, re.S)
        # The chapter may inline the verified script or call that same asset once.
        self.assertEqual(sum(block in (script, entry) for block in blocks), 1)


if __name__ == '__main__':
    unittest.main()
