import json, pathlib, time
from urllib.request import Request, urlopen
cfg=dict(l.split('=',1) for l in pathlib.Path('Documents/reports/run-state/gui-full-reset.env').read_text().splitlines())
out=pathlib.Path(cfg['OUT'])/'raw'
base='http://10.1.1.101:8088'
def call(path, data=None):
    with urlopen(Request(base+path, data=None if data is None else json.dumps(data).encode(), headers={'Content-Type':'application/json'}), timeout=330) as r:
        return json.loads(r.read())
def save(name,data):
    (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
for transport in ('SOCKET','OPENONLOAD','TCPDIRECT'):
    result=call('/api/order',dict(symbol='AAPL',side='BUY',quantity=1,limit_price_x10000=0,transport=transport))
    save('order-'+transport+'.json',result)
    print(transport,result,flush=True)
time.sleep(1)
save('before-final-reset.json',call('/api/state'))
result=call('/api/replay',dict(action='RESTART',clear_trades=True))
save('reset-final.json',result)
print('RESET',result,flush=True)
state=call('/api/state');save('after-final.json',state)
for client in ('trader_manual','trader_onload','trader_tcpdirect'):
    assert state['client_positions'][client]=={'AAPL':0,'NVDA':0}, state['client_positions']
    assert state['client_stats'][client]['orders']==0, state['client_stats']
    assert state['client_latency'][client]['samples']==0
assert not state['orders'] and not state['fills'] and state['exchange_ledger_entries']==0
with urlopen('http://10.1.1.101:8089/api/lanz',timeout=5) as r:
    lanz=json.loads(r.read())
save('lanz-after-final.json',lanz)
assert not lanz['events'] and not any(lanz['counts'].values())
print('PASS: three routes accept orders; reset clears positions/orders/fills/latency/ledger/LANZ',flush=True)
