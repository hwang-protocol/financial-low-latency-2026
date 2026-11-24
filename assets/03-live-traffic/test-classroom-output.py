#!/usr/bin/env python3
"""Replay archived evidence with isolated command fixtures; no live operations."""
from pathlib import Path
from ab_pcap_fixture import build
import json, shutil, subprocess, os, re, hashlib
ROOT=Path('/qyt-fll'); BASE=Path('/tmp/ch03-output-check'); BASE.mkdir(exist_ok=True)
assets=ROOT/'assets/03-live-traffic'
history={'01':'20260908T124834Z-03-live-market','02':'20260908T124946Z-03-market-paths','03':'20260908T125046Z-03-live-order'}
MOCK=r'''#!/usr/bin/python3
import os,sys,json,shutil
from pathlib import Path
cmd=Path(sys.argv[0]).name; args=sys.argv[1:]; box=Path(os.environ['CHECK_BOX']); raw=Path(os.environ['CHECK_RAW']); fail=os.environ.get('CHECK_FAIL','')
def cp(src,dst):
    Path(dst).parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst)
def state(): return json.loads((box/'mode.json').read_text())
if cmd=='hostname': print('jiaozhu-dgx-spark')
elif cmd=='date': print('offline-replay')
elif cmd=='sleep': pass
elif cmd=='curl':
    d=state()
    with (box/'http.txt').open('a') as f: f.write(json.dumps(args)+'\n')
    if '-X' in args:
        mode=json.loads(args[args.index('-d')+1])['market_mode']
        if fail in ('restore','capture-restore','decode-restore') and d.get('captured') and mode=='UNICAST': sys.exit(22)
        if fail=='post-once' and not d.get('post_failed'):
            d['post_failed']=True; (box/'mode.json').write_text(json.dumps(d)); sys.exit(22)
        if not (fail=='readback' and d.get('captured') and mode=='UNICAST'): d['market_mode']=mode
        if mode=='DUAL': d['dual_posts']=d.get('dual_posts',0)+1
        if fail=='mode': sys.exit(22)
        (box/'mode.json').write_text(json.dumps(d)); print('{}')
    else:
        if fail=='initial-state' or (fail=='restore-get' and d.get('captured') and d['market_mode']=='UNICAST'): sys.exit(28)
        print(json.dumps({'market_network':{'market_schema':'udp-multicast-ab-v1'},'market_mode':d['market_mode'],'session':('next' if fail=='session' and d.get('captured') else 'current'),'replay':{'loop':2 if fail=='session' and d.get('captured') else 1},'feed':{'session':('next' if fail=='session' and d.get('captured') else 'current'),'duplicates':921 if d.get('dual_posts',0)>1 else 0,'pending':0,'gaps':0}}))
elif cmd=='ssh':
    text=' '.join(args)
    if 'tcpdump' in text:
        d=state(); d['captured']=True; (box/'mode.json').write_text(json.dumps(d))
        with (box/'captures.txt').open('a') as f: f.write(d['market_mode']+'\n')
        if fail in ('capture','capture-restore'): print('capture failure fixture',file=sys.stderr); sys.exit(42)
        name=d['market_mode']+'-tcpdump.txt' if os.environ['CHECK_STEP']=='02' else 'tcpdump.txt'
        print((raw/name).read_text(),end=''); sys.exit(124 if os.environ['CHECK_STEP']=='03' else 0)
    elif 'ip maddr' in text: print((raw/'membership.txt').read_text(),end='')
    elif 'ss -ntpH' in text:
        sessions=(raw/'sessions.txt').read_text()
        if os.environ['CHECK_STEP']=='03' and not (box/'trade-submitted').exists():
            # MANUAL connects lazily. Before its first order only AUTO appears.
            manual_pid=next(line.split('=')[1] for line in sessions.splitlines() if line.startswith('manual_pid='))
            sessions='\n'.join(line for line in sessions.splitlines() if not ('20.1.1.1:43120' in line and 'pid='+manual_pid in line))+'\n'
        print(sessions,end='')
    else:
        with (box/'cleanup.txt').open('a') as f:f.write(text+'\n')
elif cmd=='scp':
    dst=args[-1]; name=Path(dst).name
    cp(raw/name,dst)
elif cmd=='python3':
    if args and args[0].endswith('eos_cli.py'):
        dst=args[args.index('--output')+1]; cp(raw/'switch-igmp.txt',dst)
        if fail=='igmp':
            p=Path(dst); p.write_text(p.read_text().replace('Et2','Et11'))
    elif args and args[0].endswith('first_trade.py'):
        if fail=='trade': print('first trade failure fixture',file=sys.stderr); sys.exit(43)
        (box/'trade-submitted').write_text('completed\n')
        print((raw/'first-trade.txt').read_text(),end='')
    elif args and '/inspect_' in args[0] and fail in ('decode','decode-restore'):
        print('decoder failure fixture',file=sys.stderr); sys.exit(44)
    else: os.execv('/usr/bin/python3',['python3']+args)
else: raise RuntimeError(cmd)
'''
results=[]
for step,run in history.items():
 for fail in ['', 'capture', 'decode']+(['restore','readback','restore-get','capture-restore','decode-restore','initial-state','post-once'] if step!='03' else ['trade'])+(['igmp','mode','session'] if step=='02' else ['verify'] if step=='01' else []):
  case=step+'-'+(fail or 'success'); box=BASE/case
  if box.exists(): shutil.rmtree(box)
  box.mkdir(); repo=box/'repo'; dest=repo/'assets/03-live-traffic'; dest.parent.mkdir(parents=True)
  shutil.copytree(assets,dest)
  igmp=repo/'assets/02-trading-baseline'; igmp.mkdir()
  shutil.copy2(ROOT/'assets/02-trading-baseline/inspect-igmp.py',igmp)
  runstate=repo/'reports/run-state'; runstate.mkdir(parents=True)
  (runstate/'02-trading-baseline.env').write_text('RUN_ID=fixture-platform\nRUN_DIR=/fixture-platform\nWEB_URL=http://10.1.1.101:8088\n')
  lab=repo/'apps/flle-trading-lab/scripts'; lab.mkdir(parents=True)
  (lab/'transport_labctl.sh').write_text('exit 45\n' if fail=='verify' else 'echo fixture verify\n')
  (lab/'labctl.sh').write_text('echo unexpected legacy verify >&2; exit 97\n')
  test=repo/'apps/flle-trading-lab/tests'; test.mkdir(); (test/'first_trade.py').write_text('# offline placeholder\n')
  # Only sandbox paths are rewritten. No production state or remote actions are reachable.
  script=next(dest.glob(step+'-*.sh'))
  source=script.read_text()
  assert len(source.splitlines())<=50 or step=='02',(step,'green card exceeds 50 lines')
  if step=='02': assert 'bash assets/03-live-traffic/02-compare-market-transports.sh' in (ROOT/'03-live-trading-traffic-and-protocols.md').read_text()
  assert not any('source ' in line and 'market-mode.sh' in line for line in source.splitlines())
  # A pasted green card must run without any retired Bash library.
  shutil.rmtree(dest/'archive',ignore_errors=True)
  assert not (dest/'market-mode.sh').exists()
  script.write_text(source.replace(str(ROOT),str(repo)))
  bindir=box/'bin'; bindir.mkdir()
  for cmd in ['date','hostname','sleep','curl','ssh','scp','python3']:
   p=bindir/cmd;p.write_text(MOCK);p.chmod(0o755)
  (box/'mode.json').write_text('{"market_mode":"UNICAST"}')
  fixture_raw=box/'fixture-raw'; shutil.copytree(ROOT/'reports'/run/'raw',fixture_raw)
  if step=='02': build(fixture_raw)
  env=dict(os.environ,PATH=str(bindir)+':'+os.environ['PATH'],CHECK_BOX=str(box),CHECK_RAW=str(fixture_raw),CHECK_STEP=step,CHECK_FAIL=fail)
  r=subprocess.run(['bash',str(script)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
  (box/'stdout.txt').write_text(r.stdout)
  expected={'':0,'capture':42,'decode':44,'restore':125,'readback':125,'restore-get':125,'capture-restore':125,'decode-restore':125,'initial-state':1,'post-once':22,'trade':43,'igmp':0,'mode':125,'verify':45,'session':1}[fail]
  if step=='03' and fail=='capture': expected=1
  assert r.returncode==expected,(case,r.returncode,r.stdout[-2000:])
  out=next((repo/'reports/course-runs').iterdir())
  assert (out/'classroom.txt').read_text()==r.stdout,(case,'log differs')
  if not fail:
   if step!='02': assert (out/'raw/decoded.txt').read_bytes()==(ROOT/'reports'/run/'raw/decoded.txt').read_bytes(),case
   else: assert 'dual_sequence_overlap=60' in (out/'raw/decoded.txt').read_text()
   if step=='02':
    for mode, value in [('MULTICAST_A','仅 A 路组播 233.74.125.32:31032'),('MULTICAST_B','仅 B 路组播 233.74.125.33:31033'),('DUAL','A 路 233.74.125.32:31032 与 B 路 233.74.125.33:31033 均有包')]:
     assert f'===== 查 {mode} 的原始目的地址 =====\n[报文] 对: {value}  证:' in r.stdout,case
   # New manifests (including classroom output) verify after logging has finished.
   for f in ['SHA256SUMS','CLASSROOM_SHA256SUMS']:
    v=subprocess.run(['sha256sum','-c',str(out/f)],stdout=subprocess.DEVNULL); assert v.returncode==0
   (BASE/(step+'-stdout.txt')).write_text(r.stdout.replace(str(repo),str(ROOT)))
  if fail=='session': assert '跨过回放换轮' in r.stdout and len((box/'captures.txt').read_text().splitlines())==1
  if fail=='igmp': assert len((box/'captures.txt').read_text().splitlines())==3
  if fail in ('restore','readback'): assert r.returncode==125
  if step!='03' and fail not in ('verify','initial-state'):
   assert '恢复检查前的行情模式' in r.stdout,case
   assert '/var/tmp/offline-replay-03-' in (box/'cleanup.txt').read_text(),case
   if fail in ('','capture','decode','post-once','igmp','session'):
    assert json.loads((box/'mode.json').read_text())['market_mode']=='UNICAST',case
   if expected==125: assert '退出码125' in r.stdout,case
  if fail in ('verify','initial-state'):
   assert not (box/'captures.txt').exists(),case
   if (box/'http.txt').exists():
    assert not any('-X' in json.loads(line) for line in (box/'http.txt').read_text().splitlines()),case
  if step=='03': assert not (box/'http.txt').exists(),case
  results.append({'case':case,'exit_code':r.returncode,'expected':expected,'classroom_log_exact':True})
print(json.dumps(results,ensure_ascii=False,indent=2))
(BASE/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
