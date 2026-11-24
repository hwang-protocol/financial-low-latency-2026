import argparse
import hashlib
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('directories', nargs='+', type=Path)
args = parser.parse_args()
root = Path('/financial-low-latency')
for directory in args.directories:
    directory = directory.resolve()
    assert directory.is_relative_to(root / 'Documents/reports/course-runs')
    manifest = directory / 'ARCHIVE_SHA256SUMS'
    rows = []
    for path in sorted(directory.rglob('*')):
        if not path.is_file() or path == manifest:
            continue
        sha = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                sha.update(chunk)
        rows.append(f'{sha.hexdigest()}  {path.relative_to(root)}\n')
    manifest.write_text(''.join(rows))
    check = subprocess.run(['sha256sum', '-c', str(manifest)], cwd=root, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    print(directory.name, len(rows), 'files VERIFIED')
