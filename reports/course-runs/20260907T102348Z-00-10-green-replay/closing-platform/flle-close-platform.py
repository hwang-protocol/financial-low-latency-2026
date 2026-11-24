from pathlib import Path
import sys,json,subprocess,time,urllib.request
root=Path('/financial-low-latency');s=json.loads((root/'Documents/reports/run-state/full-course-replay.json').read_text());out=root/s['OUT']/'closing-platform';out.mkdir(exist_ok=True);run=s['PLATFORM_RUN']
ctl=str(root/'apps/flle-trading-lab/scripts/transport_labctl.sh')
# Platform already switched; keep original receipt.
sys.path.insert(0,str(root/'apps/flle-trading-lab/tests'))
from first_trade import request,wait_state
base='http://10.1.1.101:8088'
# Replay already restarted; wait for live readiness.
state=wait_state(base,lambda d:d.get('feed',{}).get('integrity')=='HEALTHY' and d.get('trader_books',{}).get('AAPL',{}).get('asks'))
orders=[]
for transport in ('SOCKET','OPENONLOAD','TCPDIRECT'):
 for side in ('BUY','SELL'):
  state=request(base,'/api/state');book=state['trader_books']['AAPL'];price=book['asks'][0][0]+50000 if side=='BUY' else max(1,book['bids'][0][0]-50000)
  try:
   reply=request(base,'/api/order',dict(symbol='AAPL',side=side,quantity=1,limit_price_x10000=price,transport=transport))
  except urllib.error.HTTPError as exc:
   print(exc.read().decode(),flush=True);raise
  oid=reply['client_order_id']
  state=wait_state(base,lambda d:any(o.get('client_order_id')==oid and o.get('result') for o in d['orders']))
  order=next(o for o in state['orders'] if o.get('client_order_id')==oid);orders.append(order)
  (out/'orders.json').write_text(json.dumps(orders,ensure_ascii=False,indent=2)+'\n')
  assert order['result']=='ORDER_EXECUTED' and order['filled_quantity']==1,order
  print(transport,side,oid,'ORDER_EXECUTED',flush=True)
for transport in ('OPENONLOAD','TCPDIRECT'):
 with (out/(transport+'-attest.json')).open('w') as log:
  subprocess.run(['bash',ctl,'attest',run,transport,str(out/(transport+'-native'))],stdout=log,stderr=subprocess.STDOUT,check=True)
state=request(base,'/api/state');lab=request(base,'/api/transport-lab')
(out/'state.json').write_text(json.dumps(state,indent=2));(out/'transport-lab.json').write_text(json.dumps(lab,indent=2))
assert state['data_plane_mode']=='SFC' and state['data_plane_transition']=='READY'
assert state['feed']['integrity']=='HEALTHY'
for name in ('trader_manual','trader_onload','trader_tcpdirect'):assert lab['clients'][name]['health']['status']=='ONLINE'
print('PASS ordinary trading profile, all three routes traded, native acceleration receipts verified',flush=True)
