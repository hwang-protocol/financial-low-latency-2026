#!/usr/bin/env python3
"""Maintenance only: materialize a resolved, versioned APT request set on .111.

Input metadata/requests.json comes from an isolated APT resolution with an empty
status file. Package hashes are cross-checked against the saved repository lists.
This tool downloads files; classroom installers never invoke it.
"""
import argparse, concurrent.futures, hashlib, json, os, subprocess
from pathlib import Path


def digest(path, algo='sha256'):
    h = hashlib.new(algo)
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    root = args.bundle.resolve()
    requests = json.loads((root / 'metadata/requests.json').read_text())
    hashes = {}
    for path in (root / 'apt/lists').glob('*Packages*'):
        raw = subprocess.check_output(['/usr/lib/apt/apt-helper', 'cat-file', str(path)], text=True)
        for stanza in raw.split('\n\n'):
            fields = dict(line.split(': ', 1) for line in stanza.splitlines() if ': ' in line and not line.startswith(' '))
            if all(k in fields for k in ('MD5sum', 'SHA256', 'Size')):
                hashes[(int(fields['Size']), fields['MD5sum'])] = fields['SHA256']
    # A reused cache file must match repository metadata, not just its filename.
    by_size = {}
    for parent in [root / 'metadata', root.parents[1], Path('/var/cache/apt/archives')]:
        for path in parent.rglob('*.deb'):
            by_size.setdefault(path.stat().st_size, set()).add(path)
    def fetch(item):
        name, req = item
        dest = root / 'pool' / name
        if req['digest'] == 'LOCAL':
            src = Path(req['uri'].removeprefix('file:'))
            expected = digest(src)
        else:
            expected = hashes[(req['size'], req['digest'].split(':', 1)[1])]
        req['sha256'] = expected
        candidates = [dest, *sorted(by_size.get(req['size'], []))]
        for src in candidates:
            if src.is_file() and digest(src) == expected:
                if src != dest and not dest.exists():
                    os.link(src, dest)
                print('CACHED', name, flush=True)
                return
        if dest.exists():
            raise RuntimeError(f'Conflicting bytes at {dest}')
        partial = dest.with_suffix('.partial')
        subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                        '--retry', '3', '--connect-timeout', '20', '--max-time', '600',
                        req['uri'], '-o', str(partial)], check=True)
        if digest(partial) != expected:
            raise RuntimeError(f'Repository SHA256 mismatch: {name}')
        partial.replace(dest)
        print('FETCHED', name, flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(fetch, requests.items()))
    (root / 'metadata/resolved-files.json').write_text(json.dumps(requests, indent=2) + '\n')
    print('VERIFIED', len(requests), 'files', flush=True)

if __name__ == '__main__':
    main()
