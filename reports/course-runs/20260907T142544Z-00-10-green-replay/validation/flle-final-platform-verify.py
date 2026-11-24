from pathlib import Path
import subprocess,json
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT']/'final-platform-proof';out.mkdir(exist_ok=True)
for name,args in [('software-profile',['bash','apps/flle-trading-lab/scripts/transport_labctl.sh','baseline',s['PLATFORM_RUN']]),('software-first-trade',['python3','apps/flle-trading-lab/tests/first_trade.py','--base-url','http://10.1.1.101:8088/'])]:
 with (out/(name+'.txt')).open('w') as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
 print(name,'PASS',flush=True)
src=Path('/tmp/flle-new-platform-proof.py').read_text();a=src.index("R=Path(");b=src.index("sys.path.insert",a)
src=src[:a]+"R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());env=dict(l.split('=',1) for l in (R/'Documents/reports/run-state/02-trading-baseline.env').read_text().splitlines() if '=' in l);out=R/s['OUT']/'final-platform-proof';out.mkdir(exist_ok=True)\n"+src[b:]
src=src.replace("['OPENONLOAD','TCPDIRECT']","['SOCKET','OPENONLOAD','TCPDIRECT']").replace("accelerated_orders=4","orders=6")
exec(compile(src,'final-route-proof','exec'))
