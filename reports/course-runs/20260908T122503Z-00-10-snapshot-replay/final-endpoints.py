from pathlib import Path
import json,subprocess,re,datetime
root=Path('/financial-low-latency');state=json.loads((root/'Documents/reports/run-state/full-course-replay.json').read_text());out=root/state['OUT']/'final-audit';out.mkdir(exist_ok=True)
remote=r'''set -Eeuo pipefail
ss -ltnpH '( sport = :48606 )'
printf '\nUDP_ENDPOINTS\n'
ss -lunpH '( sport = :31032 or sport = :42121 )'
printf '\nMEMBERSHIP\n'
ip maddr show dev ens64np1
printf '\nRECEIVER\n'
pgrep -af '[f]lle-feed-receiver'
printf '\nUNIX_SOCKET\n'
ss -xlnpH
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','root@10.1.1.2','bash','-s'],input=remote,text=True,capture_output=True,check=True);(out/'endpoints-2.txt').write_text(p.stdout)
text=p.stdout;tcp,rest=text.split('\nUDP_ENDPOINTS\n');assert len(tcp.strip().splitlines())==1 and '10.1.1.2:48606' in tcp
udp,rest=rest.split('\nMEMBERSHIP\n');rows=udp.strip().splitlines();assert len(rows)==2 and all('flle-feed-recei' in r for r in rows)
pids={re.search(r'pid=(\d+)',r).group(1) for r in rows};assert len(pids)==1
member,rest=rest.split('\nRECEIVER\n');matches=[l.split() for l in member.splitlines() if 'inet  233.74.125.32' in l];assert len(matches)==1;tokens=matches[0];assert 'users' not in tokens or tokens[tokens.index('users')+1]=='1'
assert state['PLATFORM_RUN']+'/feed.sock' in rest
local=subprocess.run(['ss','-ltnpH','( sport = :48606 )'],text=True,capture_output=True,check=True);assert not local.stdout.strip();(out/'endpoints-111.txt').write_text('TCP48606 listener absent\n')
plan=out/'igmp.plan';plan.write_text('show ip igmp snooping\nshow igmp snooping querier\nshow ip igmp snooping groups\n')
subprocess.run(['python3','Documents/newDoc/assets/common/eos_cli.py','--mode','show','--plan',str(plan),'--output',str(out/'igmp.txt')],stdout=subprocess.DEVNULL,check=True)
t=(out/'igmp.txt').read_text();v=t.split('Vlan 20 :',1)[1].split('$ show',1)[0];assert re.search(r'IGMP snooping pruning active\s*:\s*True',v) and re.search(r'Flooding traffic to VLAN\s*:\s*False',v)
assert re.search(r'^20\s+20\.1\.1\.254\s+v2\s+Switch\s*$',t,re.M)
assert re.search(r'^20\s+233\.74\.125\.32\s+Dynamic\s+-\s+Et2\s*$',t,re.M)
(out/'endpoint-result.json').write_text(json.dumps(dict(status='PASS',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),controller='10.1.1.2:48606',controller_absent_on_111=True,receiver_pids=list(pids),udp_ports=[31032,42121],membership_users=1,switch_dynamic_ports=['Et2']),indent=2)+'\n')
print('PASS controller .2 only; shared UDP owner; one membership; EOS Et2 only')
