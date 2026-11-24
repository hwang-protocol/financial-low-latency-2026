import datetime
import hashlib
import pathlib
import subprocess

root = pathlib.Path('/financial-low-latency')
run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-02-fanout-fix'
out = root / 'Documents/reports/course-runs' / run_id
(out / 'raw').mkdir(parents=True)
(out / 'run.env').write_text(f'RUN_ID={run_id}\nPHASE=BUILD_TEST\nBASE_RUN_ID=20260910T043800Z-02-trading-platform\n')
(root / 'Documents/reports/run-state/02-fanout-fix.env').write_text(f'RUN_ID={run_id}\nPHASE=BUILD_TEST\n')
remote = '/var/tmp/flle-fanout-build-' + run_id
ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', 'root@10.1.1.101']
subprocess.run(ssh + ['mkdir', '-p', remote], check=True)
archive = subprocess.check_output(['tar', '-czf', '-', '-C', str(root / 'apps/flle-trading-lab'),
                                   'Makefile', 'src', 'tests', 'flle_trading', 'scripts', 'web'])
(out / 'source.tgz').write_bytes(archive)
subprocess.run(ssh + ['tar', '-xzf', '-', '-C', remote], input=archive, check=True)
print('RUN_ID=' + run_id, flush=True)
print('REMOTE=' + remote, flush=True)
with (out / 'raw/build-test.txt').open('wb') as log:
    result = subprocess.run(ssh + [f'cd {remote}\nmake test tools'], stdout=log, stderr=subprocess.STDOUT)
print('BUILD_TEST_RC=' + str(result.returncode), flush=True)
print((out / 'raw/build-test.txt').read_text()[-10000:], flush=True)
raise SystemExit(result.returncode)
