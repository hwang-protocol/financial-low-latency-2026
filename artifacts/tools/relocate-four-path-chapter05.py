#!/usr/bin/env python3
"""Relocate the four-path vault without rebuilding any application or library.

Usage: relocate-four-path-chapter05.py OLD_DIRECTORY NEW_DIRECTORY RECEIPT.json
Historical archives retain their bytes. Only the current runtime and build-input
archive roots, current provenance, and runtime manifest are repackaged.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


def digest(path):
    with path.open('rb') as stream:
        value=hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
        return value.hexdigest()


def payloads(path):
    with tarfile.open(path) as archive:
        return {m.name.split('/', 1)[1]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                for m in archive if m.isfile()}


def pack(tree, destination):
    # No wall-clock timestamp or build-directory name enters the gzip stream.
    with tempfile.TemporaryFile() as raw:
        subprocess.run(['tar', '--sort=name', '--mtime=@0', '--owner=0', '--group=0',
                        '--numeric-owner', '-cf', '-', '-C', str(tree.parent), tree.name],
                       stdout=raw, check=True)
        raw.seek(0)
        with destination.open('wb') as output, gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as compressed:
            shutil.copyfileobj(raw, compressed)


def unpack(path, parent):
    subprocess.run(['tar', '-xzf', str(path), '-C', str(parent)], check=True)
    roots=list(parent.iterdir())
    if len(roots)!=1 or not roots[0].is_dir():
        raise ValueError('expected one archive root')
    return roots[0]


def relocate(old, new, receipt):
    if new.exists():
        raise ValueError('destination already exists; refusing to overwrite')
    original_files={str(p.relative_to(old)):digest(p) for p in old.rglob('*') if p.is_file()}
    new.mkdir(parents=True)
    for name in original_files:
        destination=new/name.replace('ch06-four-path','ch05-four-path')
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(old/name,destination)
    inputs=new/'v5/flle-ch05-four-path-v5-build-inputs-x86_64-jammy.tgz'
    old_inputs=old/'v5/flle-ch06-four-path-v5-build-inputs-x86_64-jammy.tgz'
    with tempfile.TemporaryDirectory(prefix='flle05-repack-') as temporary:
        work=Path(temporary); tree=unpack(inputs,work)
        renamed=tree.with_name(tree.name.replace('ch06-four-path','ch05-four-path')); tree.rename(renamed)
        pack(renamed,inputs)
    assert payloads(inputs)==payloads(old_inputs), 'dependency payload changed'
    provenance_path=new/'v13/BUILD-PROVENANCE.json'
    old_provenance=json.loads(provenance_path.read_text())
    provenance=json.loads(json.dumps(old_provenance).replace('ch06-four-path','ch05-four-path'))
    provenance['build_inputs']['sha256']=digest(inputs)
    old_runtime=old/'v13/flle-ch06-four-path-v13-x86_64-jammy-runtime.tgz'
    provenance['chapter_path_relocation']={
        'date':'2026-09-12','from':'ch06-four-path','to':'ch05-four-path',
        'original_provenance_sha256':digest(old/'v13/BUILD-PROVENANCE.json'),
        'original_runtime_sha256':digest(old_runtime),
        'original_build_inputs_sha256':digest(old_inputs),
        'scope':'Archive roots and metadata only; every application, library, header, configuration and wrapper payload is byte-identical. Original build logs remain unchanged.'}
    provenance_path.write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    runtime=new/'v13/flle-ch05-four-path-v13-x86_64-jammy-runtime.tgz'
    with tempfile.TemporaryDirectory(prefix='flle05-runtime-') as temporary:
        tree=unpack(runtime,Path(temporary)); renamed=tree.with_name('flle-ch05-four-path');tree.rename(renamed)
        shutil.copyfile(provenance_path,renamed/'provenance/BUILD-PROVENANCE.json')
        manifest=renamed/'MANIFEST.sha256'; lines=[]
        for line in manifest.read_text().splitlines():
            _,name=line.split('  ',1); lines.append(f'{digest(renamed/name)}  {name}')
        manifest.write_text('\n'.join(lines)+'\n');pack(renamed,runtime)
    before=payloads(old_runtime);after=payloads(runtime)
    assert before.keys()==after.keys()
    changes=[name for name in before if before[name]!=after[name]]
    assert set(changes)=={'provenance/BUILD-PROVENANCE.json','MANIFEST.sha256'},changes
    for name,expected in provenance['compiled_outputs'].items():assert after[name]==expected
    mapping=[{'old':str(old/name),'new':str(new/name.replace('ch06-four-path','ch05-four-path')),
              'old_sha256':sha,'new_sha256':digest(new/name.replace('ch06-four-path','ch05-four-path'))}
             for name,sha in original_files.items()]
    result={'date':'2026-09-12','files':mapping,'original_provenance':old_provenance,
            'runtime_changed_members':changes,'unchanged_runtime_payloads':len(before)-len(changes),
            'unchanged_compiled_outputs':len(provenance['compiled_outputs']),
            'dependency_payload_equality':'PASS','runtime_payload_equality':'PASS'}
    receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['files','original_provenance']},ensure_ascii=False))


if __name__=='__main__':
    relocate(*(Path(arg).resolve() for arg in sys.argv[1:]))
