#!/usr/bin/env python3
"""Read-only classroom cache gate; never downloads or installs anything."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
m = json.loads((root / 'artifacts/course-packages-jammy-amd64.json').read_text())
for name, meta in m['files'].items():
    path = root / m['bundle'] / 'pool' / name
    h = hashlib.sha256()
    if not path.is_file():
        raise SystemExit(f'课前缓存缺失：{path}；请先在 .111 补齐。')
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    if h.hexdigest() != meta['sha256']:
        raise SystemExit(f'课前缓存校验失败：{path}')
print(f'.111 离线缓存：{len(m["files"])} 个包 / {len(m["profiles"])} 组工具，SHA-256 全部通过。')

# Exact non-APT inputs used by the current course, already catalogued in the vault.
import csv
wanted = {'nasdaq-s061226-aapl-nvda-itch5', 'nasdaq-s061226-aapl-nvda-manifest',
          'trex-v3.08-bcm57414-experiment', 'x2522-onload-v9.0.2-vm01',
          'x2522-ch05-four-path-v13-runtime',
          'posix-qos-v1-BUILD-PROVENANCE.json', 'posix-qos-v1-CONTRACT.json',
          'posix-qos-v1-flle-posix-qos-v1-x86_64-jammy.tgz',
          'arista-lanz-official-v1-binary', 'arista-lanz-official-v1-source',
          'arista-lanz-official-v1-build'}
seen=set()
with (root/'artifacts/ARTIFACTS.tsv').open() as stream:
    for row in csv.DictReader(stream, delimiter='\t'):
        if row['artifact_id'] not in wanted: continue
        path=root/'artifacts'/row['local_path'];h=hashlib.sha256()
        if not path.is_file():raise SystemExit('课前大文件缺失：'+str(path))
        with path.open('rb') as data:
            for chunk in iter(lambda:data.read(1024*1024), b''):h.update(chunk)
        if h.hexdigest()!=row['sha256']:raise SystemExit('课前大文件校验失败：'+str(path))
        seen.add(row['artifact_id'])
if seen!=wanted:raise SystemExit('大文件登记缺失：'+str(wanted-seen))
print('行情、TRex、Onload、固定交易运行包、Socket/Onload 更新包与 LANZ 读取工具：.111 本地输入全部通过。')
