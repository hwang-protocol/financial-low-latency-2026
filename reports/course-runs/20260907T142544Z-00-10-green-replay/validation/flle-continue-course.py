from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,sys,time
state=json.loads(Path("Documents/reports/run-state/full-course-replay.json").read_text())
log=Path(state["OUT"])/"classroom-pauses.jsonl"
def run(ids):
 subprocess.run([sys.executable,"/tmp/flle-course-replay.py","run",*ids],check=True)
def pause(after):
 start=datetime.now(timezone.utc).isoformat();print("CLASSROOM PAUSE",after,"120 seconds",flush=True)
 time.sleep(120)
 with log.open("a") as f:f.write(json.dumps({"after":after,"start":start,"end":datetime.now(timezone.utc).isoformat(),"seconds":120})+"\n")
mode=sys.argv[1]
if mode=="06-08":
 run([f"06-{i:02d}-1" for i in range(1,11)]+[f"07-{i:02d}-1" for i in range(1,6)]+[f"08-{i:02d}-1" for i in range(1,7)])
elif mode=="09-10":
 run([f"09-{i:02d}-1" for i in range(1,5)])
 for i in range(5,8):pause(f"09-{i-1:02d}-1");run([f"09-{i:02d}-1"])
 run(["10-01-1","10-02-1"])
 for i in range(3,6):pause(f"10-{i-1:02d}-1");run([f"10-{i:02d}-1"])
else:raise SystemExit("unknown segment")
