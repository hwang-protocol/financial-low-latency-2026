#!/usr/bin/env python3
"""Maintenance only: seal fetched packages and exact per-profile dependencies."""
import hashlib, json, subprocess, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[2]
requests = json.loads((root / 'metadata/resolved-files.json').read_text())
profiles = json.loads((root / 'metadata/profiles-resolved.json').read_text())
files = {}
by_package = {}
for name, req in requests.items():
    path = root / 'pool' / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == req['sha256']
    control = subprocess.check_output(['dpkg-deb', '-f', str(path)], text=True).rstrip() + '\n'
    fields = dict(line.split(': ', 1) for line in control.splitlines() if ': ' in line and not line.startswith(' '))
    control += f'Filename: pool/{name}\nSize: {req["size"]}\nSHA256: {req["sha256"]}\n\n'
    files[name] = dict(package=fields['Package'], version=fields['Version'],
                       architecture=fields['Architecture'], sha256=req['sha256'],
                       size=req['size'], source=req['uri'], control=control)
    by_package[fields['Package']] = files[name]
for name, profile in profiles.items():
    roots = []
    for spec in profile['roots']:
        if spec.startswith('/'):
            pkg = subprocess.check_output(['dpkg-deb', '-f', spec, 'Package'], text=True).strip()
        else:
            pkg = spec.split('=')[0]
        roots.append(pkg + '=' + by_package[pkg]['version'])
    profile['roots'] = roots
    if name in ('onload-build', 'xdp'):
        profile['kernel'] = '5.15.0-164-generic'
manifest = dict(schema=1, bundle=str(root.relative_to(repo)), os='ubuntu:22.04',
                architecture='amd64', trust='APT_METADATA_SHA256_CHECKED; local Grafana uses existing vault SHA',
                profiles=profiles, files=files)
(repo / 'artifacts/course-packages-jammy-amd64.json').write_text(json.dumps(manifest, indent=2) + '\n')
(root / 'Packages').write_text(''.join(meta['control'] for meta in files.values()))
(root / 'SHA256SUMS').write_text(''.join(meta['sha256'] + '  pool/' + name + '\n' for name, meta in sorted(files.items())))
print('SEALED', len(files), 'files', len(profiles), 'profiles')
