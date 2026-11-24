"""Run classroom stages with recorded, real pauses between independent entries."""
from pathlib import Path
from datetime import datetime, timezone
import json, subprocess, sys, time
out=Path(__file__).resolve().parent
chapter=sys.argv[1]
ids={'09':['09-04-1','09-05-1','09-06-1','09-07-1'],
     '10':['10-02-1','10-03-1','10-04-1','10-05-1']}[chapter]
record=out/('pauses-'+chapter+'.json');pauses=[]
for index,cid in enumerate(ids):
    subprocess.run([sys.executable,str(out/'replay.py'),'run',cid],check=True)
    if index<len(ids)-1:
        item={'after':cid,'started':datetime.now(timezone.utc).isoformat(),'requested_seconds':120}
        pauses.append(item);record.write_text(json.dumps(pauses,indent=2)+'\n')
        print('CLASSROOM_PAUSE_START',cid,'120 seconds',flush=True)
        start=time.monotonic();time.sleep(120)
        item.update(ended=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start)
        record.write_text(json.dumps(pauses,indent=2)+'\n')
        print('CLASSROOM_PAUSE_END',cid,item['elapsed_seconds'],flush=True)
