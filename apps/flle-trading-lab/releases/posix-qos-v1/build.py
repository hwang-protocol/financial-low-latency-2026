#!/usr/bin/env python3
"""Build the additive POSIX client from the immutable v13 source and this patch."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import os
import shutil
import subprocess
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[4]
SOURCE = REPO / 'artifacts/blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-source.tgz'
SOURCE_SHA = '1cbae2786192ac16c39b1ebbdb7a19101b99a532430903839de39a8f0fa62bc7'
RELEASE = Path(__file__).resolve().parent

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def archive(root, output):
    with output.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for p in sorted(root.rglob('*')):
                if not p.is_file(): continue
                info = tar.gettarinfo(str(p), str(Path(root.name) / p.relative_to(root)))
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                with p.open('rb') as data: tar.addfile(info, data)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', default='g++-11')
    parser.add_argument('--sysroot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sha(SOURCE) == SOURCE_SHA, 'v13 source digest mismatch'
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='flle-posix-qos-build-') as tmp:
        tmp = Path(tmp)
        with tarfile.open(SOURCE) as tar: tar.extractall(tmp, filter='data')
        src = tmp / 'flle-trading-lab-v13-source'
        subprocess.run(['patch', '-p1', '--batch', '--input', str(RELEASE / 'client.patch')], cwd=src, check=True)
        package = tmp / 'flle-posix-qos-v1'
        (package / 'bin').mkdir(parents=True)
        (package / 'source').mkdir()
        shutil.copytree(src / 'src', package / 'source/src')
        shutil.copy2(RELEASE / 'client.patch', package / 'source/client.patch')
        shutil.copy2(Path(__file__), package / 'source/build.py')
        flags = ['-std=c++17', '-O2', '-g', '-Wall', '-Wextra', '-Wpedantic', '-pthread', '-Isrc',
                 f'-ffile-prefix-map={src}=/usr/src/flle-posix-qos-v1']
        env = os.environ.copy()
        if args.sysroot:
            sysroot = args.sysroot.resolve()
            flags += [f'--sysroot={sysroot}', f'-B{sysroot}/usr/bin/',
                      f'-ffile-prefix-map={sysroot}=/usr/src/flle-build-sysroot']
            env['LD_LIBRARY_PATH'] = str(sysroot / 'usr/lib/x86_64-linux-gnu')
        command = [args.compiler, *flags, 'src/trader.cpp', 'src/posix_order_transport.cpp', '-o', str(package / 'bin/flle-trader')]
        subprocess.run(command, cwd=src, env=env, check=True)
        normalized = [x.replace(str(src), '<source>').replace(str(package), '<package>') for x in command]
        if args.sysroot: normalized = [x.replace(str(sysroot), '<sysroot>') for x in normalized]
        provenance = {'schema':'flle.posix-qos.v1', 'base_source_sha256':SOURCE_SHA,
            'patch_sha256':sha(RELEASE / 'client.patch'),
            'compiler':subprocess.check_output([args.compiler, '--version'], text=True).splitlines()[0],
            'command':normalized, 'binary_sha256':sha(package / 'bin/flle-trader'),
            'default_dscp':0, 'hardware_verification':'PENDING',
            'unchanged':'v13 Exchange, TCPDirect, DPDK and Chapters 00-04 runtime'}
        (package / 'BUILD-PROVENANCE.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False)+'\n')
        (package / 'MANIFEST.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(package)}\n' for p in sorted(package.rglob('*')) if p.is_file()))
        blob = args.output / 'flle-posix-qos-v1-x86_64-jammy.tgz'
        archive(package, blob)
        shutil.copy2(package / 'BUILD-PROVENANCE.json', args.output / 'BUILD-PROVENANCE.json')
        contract = {'archive_sha256':sha(blob), 'binary_sha256':provenance['binary_sha256'],
                    'manifest_sha256':sha(package / 'MANIFEST.sha256'), 'archive_bytes':blob.stat().st_size}
        (args.output / 'CONTRACT.json').write_text(json.dumps(contract,indent=2)+'\n')
        print(json.dumps(contract, indent=2))

if __name__ == '__main__': main()
