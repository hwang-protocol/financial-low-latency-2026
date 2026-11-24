#!/usr/bin/env python3
"""Install a pinned classroom tool profile from the preserved .111 artifact vault."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'artifacts/course-packages-jammy-amd64.json'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=10',
       '-o', 'ServerAliveCountMax=3']


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def remote(host, argv, **kwargs):
    return subprocess.run([*SSH, 'root@' + host, shlex.join(argv)], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', choices=['10.1.1.1', '10.1.1.2', '10.1.1.11', '10.1.1.101'])
    parser.add_argument('profile')
    args = parser.parse_args()
    if not MANIFEST.is_file():
        raise SystemExit('课前缓存清单缺失；先在 .111 完成备包，不转公网下载。')
    manifest = json.loads(MANIFEST.read_text())
    profile = manifest['profiles'][args.profile]
    bundle = ROOT / manifest['bundle']
    files = {name: manifest['files'][name] for name in profile['files']}
    for name, meta in files.items():
        path = bundle / 'pool' / name
        if not path.is_file() or sha256(path) != meta['sha256']:
            raise SystemExit(f'.111 缓存缺失或损坏：{path}；请课前补齐，不转公网下载。')
    print(f'离线工具：{args.profile}；.111 缓存校验 {len(files)} 个包通过。', flush=True)
    request = {'kernel': profile.get('kernel'), 'roots': profile['roots'],
               'files': {name: meta['sha256'] for name, meta in files.items()}}
    # One writer on .111; remote APT has its own dpkg lock as well.
    with Path('/var/tmp/flle-offline-install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = remote(args.host, ['python3', '-c', INVENTORY, json.dumps(request)],
                           text=True, stdout=subprocess.PIPE)
        state = json.loads(inventory.stdout)
        if state['ready']:
            print(f'{args.host} 工具版本已齐全；无需安装，公网下载 0 字节。', flush=True)
            return
        stage = remote(args.host, ['mktemp', '-d', '/var/tmp/flle-offline-XXXXXX'],
                       text=True, stdout=subprocess.PIPE).stdout.strip()
        try:
            with tempfile.TemporaryDirectory(prefix='flle-offline-payload-') as temp:
                tmp = Path(temp)
                (tmp / 'request.json').write_text(json.dumps(request))
                (tmp / 'install.py').write_text(INSTALL)
                (tmp / 'Packages').write_text(''.join(files[n]['control'] for n in files))
                payload = tmp / 'payload.tar'
                with tarfile.open(payload, 'w') as archive:
                    for name in state['missing']:
                        archive.add(bundle / 'pool' / name, arcname='pool/' + name, recursive=False)
                    for name in ('request.json', 'install.py', 'Packages'):
                        archive.add(tmp / name, arcname=name, recursive=False)
                print(f'通过管理网分发 {len(state["missing"])} 个包，{payload.stat().st_size / 1e6:.1f} MB。', flush=True)
                with payload.open('rb') as stream:
                    remote(args.host, ['tar', '-xf', '-', '-C', stage], stdin=stream)
            remote(args.host, ['flock', '-w', '120', '/run/lock/flle-offline-apt.lock',
                               'python3', stage + '/install.py', stage])
        finally:
            remote(args.host, ['rm', '-rf', '--', stage])


INVENTORY = r'''
import hashlib,json,pathlib,subprocess,sys
request=json.loads(sys.argv[1])
release=dict(line.split('=',1) for line in pathlib.Path('/etc/os-release').read_text().splitlines() if '=' in line)
assert release['ID'].strip('"')=='ubuntu' and release['VERSION_ID'].strip('"')=='22.04', '需要 Ubuntu 22.04'
assert subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()=='amd64'
if request['kernel']:
 assert subprocess.check_output(['uname','-r'],text=True).strip()==request['kernel'], '内核与课前缓存不一致'
ready=True
for spec in request['roots']:
 name,version=spec.split('=',1)
 p=subprocess.run(['dpkg-query','-W','-f=${Status}\t${Version}',name],text=True,capture_output=True)
 if p.returncode or p.stdout!='install ok installed\t'+version:ready=False
missing=[]
for name,expected in request['files'].items():
 path=pathlib.Path('/opt/flle/offline-packages/pool')/name
 if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:missing.append(name)
print(json.dumps({'ready':ready,'missing':missing}))
'''

INSTALL = r'''
import hashlib,json,os,pathlib,shutil,subprocess,sys
stage=pathlib.Path(sys.argv[1]);request=json.loads((stage/'request.json').read_text())
pool=pathlib.Path('/opt/flle/offline-packages/pool');pool.mkdir(parents=True,exist_ok=True)
for name,expected in request['files'].items():
 incoming=stage/'pool'/name
 path=incoming if incoming.is_file() else pool/name
 assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==expected, '缓存损坏：'+name
 if incoming.is_file():os.replace(incoming,pool/name)
(stage/'pool').mkdir(exist_ok=True)
archives=stage/'archives';archives.mkdir();(archives/'partial').mkdir()
for name in request['files']:
 for dest in (stage/'pool'/name,archives/name):
  try:os.link(pool/name,dest)
  except OSError:shutil.copyfile(pool/name,dest)
(stage/'lists/partial').mkdir(parents=True)
(stage/'source.list').write_text('deb [trusted=yes] file:'+str(stage)+' ./\n')
# The repository is local only and each payload was checked against the tracked
# .111 manifest. No remote sources, no package downloads, no package removals.
opts=['-o','Dir::Etc::sourcelist='+str(stage/'source.list'),'-o','Dir::Etc::sourceparts=-',
 '-o','Dir::State::lists='+str(stage/'lists'),'-o','Dir::Cache::archives='+str(archives),
 '-o','APT::Get::List-Cleanup=0','-o','Acquire::Languages=none','-o','DPkg::Lock::Timeout=120',
 '-o','APT::Sandbox::User=root']
env=dict(os.environ,DEBIAN_FRONTEND='noninteractive',NEEDRESTART_MODE='l')
subprocess.run(['apt-get',*opts,'update'],check=True,env=env)
subprocess.run(['apt-get',*opts,'--no-download','--no-remove','--no-install-recommends','-y','install',*request['roots']],check=True,env=env)
subprocess.run(['apt-get',*opts,'check'],check=True,env=env)
for spec in request['roots']:
 name,version=spec.split('=',1)
 actual=subprocess.check_output(['dpkg-query','-W','-f=${Status}\t${Version}',name],text=True)
 assert actual=='install ok installed\t'+version, '安装版本不符：'+spec
print('离线安装完成；全部来自 .111 缓存，公网下载 0 字节。',flush=True)
'''

if __name__ == '__main__':
    main()
