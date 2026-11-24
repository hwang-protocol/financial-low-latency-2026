#!/usr/bin/env python3
"""Maintenance only: resolve complete profiles using saved, isolated APT indexes."""
from pathlib import Path
import subprocess,json,re,shlex
import sys
r=Path(sys.argv[1]).resolve()
assert (r/'apt/status').read_text() == '', 'Resolve against empty dpkg status only'
assert not (r/'SHA256SUMS').exists(), 'Use a new bundle directory; do not rewrite a sealed version'
opts=['-o',f'Dir::Etc::sourcelist={r}/apt/sources.list','-o','Dir::Etc::sourceparts=-','-o',f'Dir::State::lists={r}/apt/lists','-o',f'Dir::State::status={r}/apt/status','-o',f'Dir::Cache::archives={r}/apt/cache/archives','-o','Debug::NoLocking=1']
profiles={
 'base':['ethtool','tcpdump','iproute2','pciutils','iputils-ping','curl','jq','numactl','util-linux','python3','python3-requests','git','unzip'],
 'builder':['g++-11=11.4.0-1ubuntu1~22.04.3','make'],
 'onload-build':['build-essential','libcap-dev','python3-dev','linux-headers-5.15.0-164-generic'],
 'xdp':['clang','llvm','libbpf-dev','linux-tools-5.15.0-164-generic'],
 'ptp':['linuxptp'],
 'p4':['p4lang-p4c=1.2.4.2-3','p4lang-bmv2=1.15.0-9','p4lang-pi'],
 'bmv2':['p4lang-bmv2=1.15.0-9'],
 'verilator':['verilator=4.038-1','g++','make'],
 'observability':['/financial-low-latency/artifacts/blobs/observability/prometheus/2.31.2/prometheus_2.31.2+ds1-1ubuntu1.22.04.3_amd64.deb','/financial-low-latency/artifacts/blobs/observability/grafana/13.1.0/grafana_13.1.0_amd64.deb']}
res={};reqs={}
for name,roots in profiles.items():
 p=subprocess.run(['apt-get',*opts,'--print-uris','--download-only','--yes','--no-install-recommends','install',*roots],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (r/'metadata'/f'{name}-resolve.txt').write_text(p.stdout)
 if p.returncode:raise SystemExit(name+': '+p.stdout[-3000:])
 uris=[]
 for line in p.stdout.splitlines():
  if not line.startswith("'"):continue
  parts=shlex.split(line)
  uri,filename,size=parts[:3];digest=parts[3] if len(parts)==4 else "LOCAL"
  req={'uri':uri,'filename':filename,'size':int(size),'digest':digest}
  if filename in reqs:assert reqs[filename]==req
  reqs[filename]=req;uris.append(filename)
 res[name]={'roots':roots,'files':uris}
 print(name,len(uris),round(sum(reqs[f]['size'] for f in uris)/1e6,1),'MB',flush=True)
(r/'metadata/requests.json').write_text(json.dumps(reqs,indent=2)+'\n')
(r/'metadata/profiles-resolved.json').write_text(json.dumps(res,indent=2)+'\n')
print('TOTAL',len(reqs),sum(x['size'] for x in reqs.values())/1e6,flush=True)
