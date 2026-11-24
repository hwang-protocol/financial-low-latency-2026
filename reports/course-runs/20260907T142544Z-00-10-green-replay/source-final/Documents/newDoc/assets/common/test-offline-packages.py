#!/usr/bin/env python3
"""Check the preserved package closure with no network and an empty dpkg status."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
M = json.loads((ROOT / 'artifacts/course-packages-jammy-amd64.json').read_text())
BUNDLE = ROOT / M['bundle']


class OfflineClosure(unittest.TestCase):
    def test_all_payload_hashes(self):
        for name, meta in M['files'].items():
            with self.subTest(package=name):
                self.assertEqual(hashlib.sha256((BUNDLE / 'pool' / name).read_bytes()).hexdigest(), meta['sha256'])

    def resolve(self, profile, omit=None):
        with tempfile.TemporaryDirectory(prefix='flle-apt-closure-') as temp:
            r = Path(temp)
            (r / 'status').touch()
            (r / 'lists/partial').mkdir(parents=True)
            (r / 'source.list').write_text(f'deb [trusted=yes] file:{r} ./\n')
            (r / 'Packages').write_text(''.join(M['files'][name]['control'] for name in profile['files']
                                               if M['files'][name]['package'] != omit))
            opts = ['-o', 'Dir::Etc::sourcelist=' + str(r / 'source.list'),
                    '-o', 'Dir::Etc::sourceparts=-', '-o', 'Dir::State::lists=' + str(r / 'lists'),
                    '-o', 'Dir::State::status=' + str(r / 'status'), '-o', 'Debug::NoLocking=1',
                    '-o', 'APT::Sandbox::User=root', '-o', 'Acquire::Languages=none']
            subprocess.run(['unshare', '--net', 'apt-get', *opts, 'update'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            return subprocess.run(['unshare', '--net', 'apt-get', *opts, '-s', '--no-remove',
                                   '--no-install-recommends', 'install', *profile['roots']],
                                  text=True, capture_output=True)

    def test_all_profiles_resolve_from_empty_status_without_network(self):
        for name, profile in M['profiles'].items():
            with self.subTest(profile=name):
                result = self.resolve(profile)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_transitive_dependency_is_rejected(self):
        result = self.resolve(M['profiles']['xdp'], omit='libllvm14')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('libllvm14', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
