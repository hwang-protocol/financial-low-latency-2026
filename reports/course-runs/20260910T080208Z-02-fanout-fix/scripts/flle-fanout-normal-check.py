import datetime
import json
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen

root = Path('/financial-low-latency')
soak_state = root/'Documents/reports/run-state/02-full-source-soak.json'
while True:
    previous = json.loads(soak_state.read_text())
    if previous['status'] != 'RUNNING':
        assert previous['status'] == 'PASS', previous
        break
    time.sleep(10)
run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-02-normal-speed-check'
out = root/'Documents/reports/course-runs'/run_id
(out/'raw').mkdir(parents=True)
summary = dict(run_id=run_id, status='RUNNING', prior=previous['run_id'], samples=0,
               duration_target_seconds=600, started=datetime.datetime.now(datetime.timezone.utc).isoformat())
state_path = root/'Documents/reports/run-state/02-normal-speed-check.json'
state_path.write_text(json.dumps(summary,indent=2)+'\n')


def direct(host, port):
    with socket.create_connection((host,port),timeout=5) as connection:
        connection.sendall(b'STATE\n'); connection.shutdown(socket.SHUT_WR)
        with connection.makefile('rb') as stream:
            return json.loads(stream.readline())


def gateway():
    with urlopen('http://10.1.1.101:8088/api/state',timeout=10) as reply:
        return json.load(reply)


def save(name, value):
    (out/'raw'/name).write_text(json.dumps(value,indent=2)+'\n')


start=time.monotonic()
try:
    print('NORMAL_STARTED',run_id,flush=True)
    save('start-gateway.json', gateway())
    with (out/'raw/samples.jsonl').open('w') as log:
        while True:
            elapsed=time.monotonic()-start
            exchange=direct('10.1.1.1',48120)
            auto=direct('10.1.1.2',48121)
            manual=direct('10.1.1.2',48122)
            log.write(json.dumps(dict(seconds=elapsed,exchange=exchange,auto=auto,manual=manual))+'\n'); log.flush()
            assert exchange['replay_speed']==1, exchange['replay_speed']
            assert exchange['market_mode']=='UNICAST',exchange['market_mode']
            for state in [auto,manual]:
                assert state['integrity']=='HEALTHY' and state['pending']==0 and state['gaps']==0,state
                assert state['trading_gate']=='OPEN' and not state['resync_required'],state
            summary['samples']+=1
            if summary['samples']%10==1:
                value=gateway(); save('gateway-%04d.json'%int(elapsed),value)
                receiver=value['feed_receiver']
                assert receiver['overflow_disconnects']==0 and receiver['discarded_queue_packets']==0,receiver
                print('NORMAL',round(elapsed),'seconds','seq='+str(auto['last_delivered']),
                      'integrity='+auto['integrity']+'/'+manual['integrity'],flush=True)
            if elapsed>=600:break
            time.sleep(3)
    summary.update(status='PASS',seconds=time.monotonic()-start,session=auto['session'],
                   final_sequence=auto['last_delivered'],speed=1)
    save('end-gateway.json',gateway())
except BaseException as error:
    summary.update(status='FAIL',error=repr(error));raise
finally:
    summary['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    state_path.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
