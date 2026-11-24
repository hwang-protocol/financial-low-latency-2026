from pathlib import Path
import json,subprocess,re,shlex
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT']/'final-platform-proof';remote='/var/tmp/flle-trading-lab-'+s['PLATFORM_RUN']
def ssh(command):return subprocess.check_output(['ssh','-o','BatchMode=yes','root@10.1.1.2',command],text=True)
pids={}
for mode,name in [('SOCKET','trader-manual'),('OPENONLOAD','trader-onload'),('TCPDIRECT','trader-tcpdirect')]:
 record=json.loads((out/mode/'recovery.json').read_text());assert record['result']=='PASS' and len(record['orders'])==2 and record['position_AAPL'][0]==record['position_AAPL'][1]
 pid=ssh('cat '+shlex.quote(remote+'/'+name+'.pid')).strip();assert pid.isdigit()
 identity=ssh('cat '+shlex.quote(remote+'/'+name+'.identity')).strip();fields=dict(x.split('=',1) for x in identity.split());assert fields['pid']==pid
 stat=ssh('cat /proc/'+pid+'/stat').rsplit(')',1)[1].split();assert stat[19]==fields['start_ticks']
 assert ssh('cat /proc/sys/kernel/random/boot_id').strip()==fields['boot_id'];pids[mode]=pid
socket=ssh("ss -tnpH state established '( dst 20.1.1.1 and dport = :43120 )'");(out/'socket-native.txt').write_text(socket);assert any('pid='+pids['SOCKET']+',' in line and '20.1.1.1:43120' in line for line in socket.splitlines())
on=ssh('onload_stackdump lots');(out/'onload-native.txt').write_text(on);blocks=re.split(r'(?=^  Onload .* pid=)',on,flags=re.M);assert any((' pid='+pids['OPENONLOAD']+' ') in b and 'Onloaded(Valid)' in b and re.search(r'rmt=20\.1\.1\.1:43120 ESTABLISHED',b) for b in blocks)
zf=remote+'/transport-runtime/flle-ch06-four-path/bin/zf_stackdump';ls=ssh(zf+' list');(out/'tcpdirect-list.txt').write_text(ls);line=next(l for l in ls.splitlines() if l.startswith('flle-tcpdirect ') and 'pid='+pids['TCPDIRECT'] in l);sid=re.search(r'\bid=(\d+)',line)[1];a=ssh(zf+' attr '+sid);d=ssh(zf+' dump '+sid);(out/'tcpdirect-attr.txt').write_text(a);(out/'tcpdirect-native.txt').write_text(d);assert 'ctpio=3' in a and 'ctpio_mode=sf-np' in a and re.search(r'rmt=20\.1\.1\.1:43120 .*ESTABLISHED',d)
status=json.loads((out/'status.json').read_text());assert status['experiment_profile']=='SOFTWARE' and status['software_clients_ready'] and (status['mode'],status['transition'],status['owner'])==('SFC','READY','sfc')
(out/'result.json').write_text(json.dumps(dict(status='PASS',platform=s['PLATFORM_RUN'],executed_orders=6,positions_unchanged=True,native_receipts=['socket','onload','tcpdirect'],pids=pids,software_status_receipts='intentionally empty; native evidence queried separately'),indent=2)+'\n');print('PASS existing 6 orders and current-process native Socket/Onload/ZF receipts')
