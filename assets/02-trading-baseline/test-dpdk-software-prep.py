#!/usr/bin/env python3
"""Exercise software preparation and session restore locally, with the real blob."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'assets/02-trading-baseline'
SOURCE = (ASSETS / '00b-dpdk-software-prep.sh').read_text()
CONTROL = (ROOT / 'apps/flle-trading-lab/scripts/transport_labctl.sh').read_text()
BLOB = ROOT / 'artifacts/blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-x86_64-jammy-runtime.tgz'
SHA = '0e5d77fef1e4891b9f2220681c18162da6c605ea5619ea00e28022f23281dc00'


def remote_body(text):
    return text.split("<<'REMOTE'", 1)[1].split('\n', 1)[1].split('\nREMOTE', 1)[0]


class SoftwarePrep(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='flle-dpdk-prep-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'prepared' / SHA
        self.incoming = self.root / 'incoming.tgz'
        self.bindir = self.root / 'bin'
        self.bindir.mkdir()
        self.group = self.root / 'sys/kernel/iommu_groups/7'
        (self.group / 'devices/0000:03:00.0').mkdir(parents=True)
        device = self.root / 'sys/bus/pci/devices/0000:03:00.0'
        device.mkdir(parents=True)
        (device / 'iommu_group').symlink_to(self.group)
        driver = self.root / 'drivers/sfc'
        driver.mkdir(parents=True)
        (device / 'driver').symlink_to(driver)
        flag = self.root / 'sys/module/vfio/parameters/enable_unsafe_noiommu_mode'
        flag.parent.mkdir(parents=True)
        flag.write_text('N\n')
        lspci = self.bindir / 'lspci'
        lspci.write_text('#!/bin/sh\necho "Subsystem: XtremeScale X2522-25G [1924:8028]"\n')
        lspci.chmod(0o755)
        self.script = remote_body(SOURCE).replace('/sys/', str(self.root / 'sys') + '/')
        self.script = self.script.replace('/run/lock/flle-prepared-runtime.lock', str(self.root / 'lock'))
        self.env = dict(os.environ, PATH=str(self.bindir) + ':' + os.environ['PATH'])

    def prepare(self, copy_source=True):
        if copy_source:
            shutil.copyfile(BLOB, self.incoming)
        return subprocess.run(['bash', '-s', '--', str(self.incoming), str(self.cache), SHA],
                              input=self.script, text=True, capture_output=True, env=self.env)

    def test_real_install_reuse_and_session_restore(self):
        self.assertEqual(hashlib.sha256(BLOB.read_bytes()).hexdigest(), SHA)
        first = self.prepare()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        binary = self.cache / 'flle-ch05-four-path/bin/flle-trader-dpdk'
        before = binary.stat().st_mtime_ns
        again = self.prepare(copy_source=False)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(binary.stat().st_mtime_ns, before)
        for text in ('查网卡型号', '查已安装软件的版本', '查客户端已包含两套库', '查隔离与驱动状态',
                     'DPDK: 21.11.9', 'F-Stack: 0abb713', '查运行程序文件', '[文件检查] 两个程序均存在且可执行。',
                     'ff_init', 'rte_eal_init', 'net_sfc_efx', '[准备完成]'):
            self.assertIn(text, first.stdout)
        function = CONTROL.split('install_runtime_on_host() {', 1)[1].split('\n}\n', 1)[0]
        self.assertNotIn('SCP', function)
        self.assertNotIn('tar -x', function)
        run = self.root / 'session'
        run.mkdir()
        runtime = run / 'transport-runtime/flle-ch05-four-path'
        result = subprocess.run(['bash', '-s', '--', str(run), str(runtime), SHA, str(self.cache)],
                                input=remote_body(function), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(hashlib.sha256((runtime / 'bin/flle-trader-dpdk').read_bytes()).digest(),
                         hashlib.sha256(binary.read_bytes()).digest())
        self.assertFalse((runtime / 'bin/flle-trader-dpdk').is_symlink())
        self.assertEqual(hashlib.sha256((run / 'transport-runtime.tgz').read_bytes()).hexdigest(), SHA)

    def test_missing_iommu_stops_before_install(self):
        (self.root / 'sys/bus/pci/devices/0000:03:00.0/iommu_group').unlink()
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('先执行准备 B1', result.stderr)
        self.assertFalse(self.cache.exists())

    def test_unsafe_mode_and_shared_group_stop_before_install(self):
        flag = self.root / 'sys/module/vfio/parameters/enable_unsafe_noiommu_mode'
        flag.write_text('Y\n')
        unsafe = self.prepare()
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertIn('VFIO 安全模式未就绪', unsafe.stderr)
        self.assertFalse(self.cache.exists())
        flag.write_text('N\n')
        (self.group / 'devices/0000:04:00.0').mkdir()
        shared = self.prepare()
        self.assertNotEqual(shared.returncode, 0)
        self.assertIn('隔离组不符合本课配置', shared.stderr)
        self.assertFalse(self.cache.exists())

    def test_wrapper_preserves_failure_and_checks_both_hosts_on_success(self):
        # Only the orchestration is exercised here; SSH is a labelled fixture.
        blob = self.root / BLOB.relative_to(ROOT)
        blob.parent.mkdir(parents=True)
        blob.symlink_to(BLOB)
        ssh = self.bindir / 'ssh'
        ssh.write_text('''#!/bin/bash
printf '%s\\n' "$*" >>"$FIXTURE_CALLS"
if [[ "$*" == *"test -d"* ]]; then exit 0; fi
cat >/dev/null
echo 'fixture-host / verify'
echo 'FIXTURE remote query'
exit "$FIXTURE_RC"
''')
        ssh.chmod(0o755)
        script = SOURCE.replace('cd /qyt-fll', 'cd ' + str(self.root))
        script = script.replace('/run/lock/flle-ch02-dpdk-software.lock', str(self.root / 'outer-lock'))
        for rc in (37, 0):
            with self.subTest(rc=rc):
                calls = self.root / ('calls-' + str(rc))
                env = dict(self.env, FIXTURE_CALLS=str(calls), FIXTURE_RC=str(rc))
                run = script.replace('RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-dpdk-software-prep"',
                                     'RUN_ID=fixture-' + str(rc))
                result = subprocess.run(['bash', '-s'], input=run, text=True, capture_output=True, env=env)
                self.assertEqual(result.returncode, rc, result.stdout + result.stderr)
                out = self.root / ('reports/course-runs/fixture-' + str(rc))
                self.assertIn('EXIT_CODE=' + str(rc), (out / 'run.env').read_text())
                checked = subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=out, capture_output=True)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual('root@10.1.1.2' in calls.read_text(), rc == 0)
                self.assertIn('evidence=', result.stdout)

    def test_corrupt_source_and_cached_binary_are_rejected(self):
        self.incoming.write_bytes(b'broken archive')
        broken = self.prepare(copy_source=False)
        self.assertNotEqual(broken.returncode, 0)
        self.assertFalse(self.cache.exists())
        good = self.prepare()
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        binary = self.cache / 'flle-ch05-four-path/bin/flle-trader-dpdk'
        with binary.open('ab') as stream:
            stream.write(b'corrupt')
        bad_cache = self.prepare(copy_source=False)
        self.assertNotEqual(bad_cache.returncode, 0)
        self.assertNotIn('[准备完成]', bad_cache.stdout)

    def test_missing_library_does_not_publish_ready_cache(self):
        ldd = self.bindir / 'ldd'
        ldd.write_text('#!/bin/sh\necho "libfixture.so => not found"\n')
        ldd.chmod(0o755)
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.cache.exists())
        self.assertEqual(list(self.cache.parent.glob('.install-*')), [])

    def test_restore_preflight_requires_prepared_software(self):
        function = CONTROL.split('verify_prepared_runtime_on_host() {', 1)[1].split('\n}\n', 1)[0]
        result = subprocess.run(['bash', '-s', '--', str(self.cache), SHA],
                                input=remote_body(function), text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('准备 B2', result.stderr)
        deploy = CONTROL.split('\n  deploy)\n', 1)[1]
        self.assertLess(deploy.index('verify_prepared_runtime_on_host'), deploy.index('"$BASE_CTL" deploy-data'))


if __name__ == '__main__':
    unittest.main()
