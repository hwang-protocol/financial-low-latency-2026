import os,json,subprocess,re,hashlib
from pathlib import Path

def run(args):
 try:
  r=subprocess.run(args,capture_output=True,text=True,timeout=25);return {'rc':r.returncode,'out':r.stdout,'err':r.stderr}
 except (OSError,subprocess.TimeoutExpired) as e:return {'error':str(e)}
def read(p):
 try:return Path(p).read_text().strip()
 except OSError:return None
r={'hostname':read('/etc/hostname'),'boot_id':read('/proc/sys/kernel/random/boot_id'),'machine_id':read('/etc/machine-id'),'uptime':read('/proc/uptime'),'kernel':os.uname().release,'cpu_count':os.cpu_count(),'meminfo':read('/proc/meminfo'),'cmdline':read('/proc/cmdline')}
r['links']=run(['ip','-j','-d','link']);r['addresses']=run(['ip','-j','addr']);r['routes']=run(['ip','-j','route','show','table','all']);r['listeners']=run(['ss','-lntup']);r['services']=run(['systemctl','list-units','--type=service','--state=running','--no-pager','--no-legend']);r['failed']=run(['systemctl','--failed','--no-pager','--no-legend']);r['unit_files']=run(['systemctl','list-unit-files','--no-pager','--no-legend']);r['timers']=run(['systemctl','list-timers','--all','--no-pager']);r['mounts']=run(['findmnt','-rn','-o','TARGET,FSTYPE']);r['disk']=run(['df','-h','/']);r['packages']=run(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n'])
r['processes']=run(['ps','-eo','pid,comm'])
r['pci']=[]
for p in Path('/sys/bus/pci/devices').glob('*'):
 if read(p/'class') not in ('0x020000','0x028000'):continue
 r['pci'].append({'bdf':p.name,'vendor':read(p/'vendor'),'device':read(p/'device'),'driver':(p/'driver').resolve().name if (p/'driver').exists() else None,'net':[x.name for x in (p/'net').glob('*')],'iommu_group':(p/'iommu_group').resolve().name if (p/'iommu_group').exists() else None})
r['hugepages']={str(p):read(p) for p in Path('/sys/kernel/mm/hugepages').glob('*/nr_hugepages')};r['iommu_groups']=[p.name for p in Path('/sys/kernel/iommu_groups').glob('*')];r['modules']=read('/proc/modules')
r['qdisc']={p.name:run(['tc','-j','qdisc','show','dev',p.name]) for p in Path('/sys/class/net').glob('*')};r['tc_filters']={p.name:{direction:run(['tc','-j','filter','show','dev',p.name,direction]) for direction in ['ingress','egress']} for p in Path('/sys/class/net').glob('*')};r['iptables']=run(['iptables-save']);r['nft']=run(['nft','list','ruleset'])
r['config_files']={}
for folder,pat in [('/etc/netplan','*'),('/etc/modules-load.d','*'),('/etc/modprobe.d','*'),('/etc/sysctl.d','*'),('/etc/apt/sources.list.d','*'),('/etc/systemd/system','*flle*')]:
 for p in Path(folder).glob(pat):
  if p.is_file():
   content=read(p)
   r['config_files'][str(p)]='\n'.join('[REDACTED]' if re.search('password|secret|token|private.key',line,re.I) else line for line in (content or '').splitlines())
r['apt_sources']=read('/etc/apt/sources.list');r['residual_paths']={}
for folder in ['/opt/flle','/opt/trex','/run','/var/tmp','/tmp','/etc/systemd/system','/etc/cron.d']:
 p=Path(folder);r['residual_paths'][folder]=[str(x) for x in p.glob('*') if folder.startswith('/opt') or re.search(r'flle|trex|onload|p4|guardian|lanz|trading|rtl|xdp|dpdk',x.name,re.I)]
r['prewarm']=[]
for p in Path('/opt/flle/prewarm').rglob('*'):
 if not p.is_file():continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 r['prewarm'].append({'path':str(p),'size':p.stat().st_size,'sha256':h.hexdigest()})
if __import__('shutil').which('docker'):
 r['docker_images']=run(['docker','image','ls','--no-trunc','--format','{{.Repository}}:{{.Tag}} {{.ID}}']);r['docker_containers']=run(['docker','ps','-a','--no-trunc','--format','{{.ID}} {{.Names}} {{.Status}}']);r['docker_volumes']=run(['docker','volume','ls','-q']);r['docker_networks']=run(['docker','network','ls','--format','{{.Name}} {{.Driver}}'])
print(json.dumps(r))
