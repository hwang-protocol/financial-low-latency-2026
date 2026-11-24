#!/usr/bin/env python3
"""Read-only migration checks; no SSH, installs, or course execution.

Run from any directory. --full also verifies the complete local artifact vault.
Historical reports and vendored blobs keep their original paths and are not
interpreted as current Markdown instructions.
"""
import argparse
import ast
import csv
import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'''!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)|(?:src|href)=["']([^"']+)["']''')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check(full=False):
    errors = []
    counts = dict(links=0, shell=0, python=0, artifacts=0)
    docs = list(ROOT.glob('*.md'))
    for base in ('assets', 'apps', 'images', 'refs', 'artifacts'):
        docs += [p for p in (ROOT/base).rglob('*.md') if 'blobs' not in p.relative_to(ROOT).parts]
    for path in docs:
        source = path.read_text()
        for match in LINK.finditer(source):
            target = (match[1] or match[2]).split('#')[0]
            if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:|//', target):
                continue
            counts['links'] += 1
            if not (path.parent/unquote(target)).exists():
                line = source[:match.start()].count('\n') + 1
                errors.append(f'{path.relative_to(ROOT)}:{line}: missing {target}')
    for base in ('assets', 'apps', 'artifacts/tools', 'tools'):
        for path in (ROOT/base).rglob('*'):
            if path.suffix == '.sh':
                counts['shell'] += 1
                result = subprocess.run(['bash', '-n', str(path)], text=True, capture_output=True)
                if result.returncode:
                    errors.append(result.stderr)
            elif path.suffix == '.py':
                counts['python'] += 1
                try:
                    ast.parse(path.read_text(), filename=str(path))
                except (SyntaxError, UnicodeError) as exc:
                    errors.append(str(exc))
    for path in ROOT.rglob('*'):
        if path.is_symlink() and not path.exists():
            errors.append(f'broken symlink: {path.relative_to(ROOT)}')
    # Each FPGA course source must match both its package copy and its recorded origin.
    for directory, key, field in [('u250-clean', 'course_files', 'path'),
                                   ('u250-course-files', 'files', 'file')]:
        import json
        base = ROOT/'assets/09-verilator'/directory
        manifest = json.loads((base/'SOURCE-MANIFEST.json').read_text())
        for item in manifest[key]:
            origin = item['origin'].removeprefix('Documents/newDoc/')
            for path in (base/item[field], ROOT/origin):
                if not path.is_file() or digest(path) != item['sha256']:
                    errors.append(f'FPGA source mismatch: {path}')
    manifests = [(ROOT/'artifacts/GIT-BACKUP-SHA256SUMS', ROOT)]
    for tree in ('assets', 'images'):
        for manifest in (ROOT/tree).rglob('*SHA256SUMS'):
            base = ROOT if manifest.name == 'PTP-AB-SHA256SUMS' else manifest.parent
            manifests.append((manifest, base))
    if full:
        manifests.append((ROOT/'artifacts/SHA256SUMS', ROOT/'artifacts'))
    for manifest, base in manifests:
        for line in manifest.read_text().splitlines():
            expected, name = line.split(None, 1)
            path = base/name.lstrip('*')
            counts['artifacts'] += 1
            if not path.is_file() or digest(path) != expected:
                errors.append(f'{manifest.name}: missing or changed {name}')
    if full:
        with (ROOT/'artifacts/ARTIFACTS.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                if row['local_path'].startswith('REMOTE_ONLY@'):
                    continue
                path = ROOT/'artifacts'/row['local_path']
                if (not path.is_file() or str(path.stat().st_size) != row['size_bytes']
                        or digest(path) != row['sha256']):
                    errors.append(f'ARTIFACTS.tsv: missing or changed {row["local_path"]}')
    print(' '.join(f'{key}={value}' for key, value in counts.items()))
    if errors:
        raise SystemExit('\n'.join(errors))
    print('PASS local links, syntax, symlinks, FPGA source copies and artifact checksums')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='also hash the complete local vault')
    check(parser.parse_args().full)
