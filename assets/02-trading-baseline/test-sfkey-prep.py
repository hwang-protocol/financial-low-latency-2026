#!/usr/bin/env python3
"""Check the actual sfkey preparation/query snippets without contacting a VM."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sfutils_source', HERE / 'extract-sfutils-source.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
SCRIPT = (HERE / '00a-runtime-prep.sh').read_text()


def section(name):
    return SCRIPT.split('# SFKEY_' + name + '_BEGIN:', 1)[1].split('# SFKEY_' + name + '_END', 1)[0].split('\n', 1)[1]


TOOL = '''#!/bin/bash
printf '%s\\n' "$*" >>"$CALLS"
case "$*" in
  --version) echo 'sfkey firmware update utility: v8.3.3.1000';;
  '--adapter=ens64np1 --report --noevaluationupdate')
    if test "$REPORT_RC" -ne 0; then echo 'fixture: report failed' >&2; exit "$REPORT_RC"; fi
    printf '  Installed keys\\tPlus\\n';;
  '--adapter=ens64np1 --inventory --keys --noevaluationupdate')
    if test "$INVENTORY_RC" -ne 0; then echo 'fixture: inventory failed' >&2; exit "$INVENTORY_RC"; fi
    echo 'ens64np1: FIXTURE, $Onload, $Precision Time, $TCP Direct, $Low Latency, $SolarCapture Tap, $Plus';;
  *) echo 'unexpected sfkey arguments' >&2; exit 99;;
esac
'''


class SfkeyPrep(unittest.TestCase):
    def test_real_cached_source_and_corruption(self):
        payload = source.extract_source()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), source.TAR_SHA)
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            self.assertIn('sfutils-8.3.3.1000/app/sfkey/sfkey.c', archive.getnames())
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / 'broken.zip'
            broken.write_bytes(b'not the pinned archive')
            with self.assertRaisesRegex(ValueError, '摘要不符'):
                source.extract_source(broken)

    def test_install_reuse_and_failed_build_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bindir = root / 'bin'
            bindir.mkdir()
            installed = root / 'usr/sbin/sfkey'
            installed.parent.mkdir(parents=True)
            tool = root / 'fixture-sfkey'
            tool.write_text(TOOL)
            tool.chmod(0o755)
            archive = root / 'source.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                data = b'fixture license'
                member = tarfile.TarInfo('sfutils-8.3.3.1000/LICENSE')
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
            make = bindir / 'make'
            make.write_text('''#!/bin/bash
echo build >>"$BUILDS"
test "$BUILD_RC" = 0 || exit "$BUILD_RC"
test "$1" = -C
test "${*:3}" = '-j2 build-sfkey NEW_GCC=1 AWK=awk'
mkdir -p "$2/build/linux/tmp/sfkey"
cp "$FIXTURE_TOOL" "$2/build/linux/tmp/sfkey/sfkey"
''')
            make.chmod(0o755)
            snippet = section('PREP').replace('/usr/sbin/sfkey', str(installed))
            snippet = snippet.replace('/opt/flle/course-src', str(root / 'src'))
            snippet = snippet.replace('/usr/share/doc/flle-sfkey/LICENSE', str(root / 'doc/LICENSE'))
            snippet = snippet.replace(source.TAR_SHA, hashlib.sha256(archive.read_bytes()).hexdigest())
            env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                       CALLS=str(root / 'calls'), BUILDS=str(root / 'builds'), FIXTURE_TOOL=str(tool))

            def run(build_rc):
                return subprocess.run(['bash', '-Eeuo', 'pipefail', '-c',
                    'sfutils_archive="$1"\n' + snippet, 'test', str(archive)],
                    env=dict(env, BUILD_RC=str(build_rc)), text=True, capture_output=True)

            failed = run(29)
            self.assertEqual(failed.returncode, 29, failed.stderr)
            self.assertFalse(installed.exists())
            first = run(0)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual((root / 'doc/LICENSE').read_text(), 'fixture license')
            self.assertEqual((root / 'builds').read_text().splitlines(), ['build', 'build'])
            # A failing compiler cannot affect the already-installed reuse path.
            again = run(29)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual((root / 'builds').read_text().splitlines(), ['build', 'build'])

    def test_formatted_readonly_queries_and_failure_stop(self):
        for report_rc, inventory_rc in ((0, 0), (19, 0), (0, 23)):
            with self.subTest(report=report_rc, inventory=inventory_rc), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                tool = root / 'sfkey'
                tool.write_text(TOOL)
                tool.chmod(0o755)
                run = subprocess.run(['bash', '-Eeuo', 'pipefail', '-c',
                    'sfkey_bin="$1"; iface=ens64np1; sfkey_version=fixture\n' + section('QUERY'),
                    'test', str(tool)], text=True, capture_output=True,
                    env=dict(os.environ, CALLS=str(root / 'calls'), REPORT_RC=str(report_rc),
                             INVENTORY_RC=str(inventory_rc)))
                self.assertEqual(run.returncode, report_rc or inventory_rc, run.stderr)
                calls = (root / 'calls').read_text().splitlines()
                self.assertEqual(len(calls), 1 if report_rc else 2)
                self.assertTrue(all('--noevaluationupdate' in c for c in calls))
                if not report_rc and not inventory_rc:
                    for heading in ('查 sfkey 工具', '查 Plus 授权', '查已启用功能'):
                        self.assertIn('===== ' + heading + ' =====', run.stdout)
                    self.assertIn('Installed keys\tPlus', run.stdout)
                    self.assertIn('$Onload, $Precision Time, $TCP Direct, $Low Latency', run.stdout)
                    self.assertIn('[功能名称怎么读]', run.stdout)
                    self.assertIn('Precision Time   精确时间与 PTP 功能', run.stdout)
                    self.assertIn('[后续使用]', run.stdout)
                    self.assertLess(run.stdout.index('$ sfkey --adapter='), run.stdout.index('\n  Installed keys'))
                else:
                    self.assertIn('fixture:', run.stderr)
                    self.assertNotIn('[后续使用]', run.stdout)


if __name__ == '__main__':
    unittest.main()
