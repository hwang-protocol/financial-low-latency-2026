#!/usr/bin/env python3
"""Exercise the deployed course webpage in real Chromium via its CDP pipe."""
import argparse,base64,json,os,pathlib,select,signal,subprocess,time
parser=argparse.ArgumentParser();parser.add_argument('action',choices=['inspect','gap','restart','switch-roundtrip','lanz']);parser.add_argument('--label',required=True);args=parser.parse_args()
out=pathlib.Path(__file__).resolve().parent/'browser'/args.label;out.mkdir(parents=True,exist_ok=True)
chrome='/root/.cache/puppeteer/chrome-headless-shell/linux-131.0.6778.204/chrome-headless-shell-linux64/chrome-headless-shell'
r,w=os.pipe();rr,ww=os.pipe()
def child(): os.dup2(r,3);os.dup2(ww,4)
env=os.environ.copy();env['LD_LIBRARY_PATH']='/tmp/flle-svg-preview-libs/root/usr/lib/x86_64-linux-gnu';env['FONTCONFIG_FILE']='/tmp/flle-svg-preview-libs/fonts.conf'
stderr=(out/'chrome.log').open('w')
p=subprocess.Popen([chrome,'--no-sandbox','--disable-gpu','--remote-debugging-pipe','--window-size=1600,1100','about:blank'],pass_fds=(r,w,ww),preexec_fn=child,env=env,stdout=subprocess.DEVNULL,stderr=stderr,start_new_session=True)
os.close(r);os.close(ww);buf=b'';seq=0;session=None
receipt={'action':args.action,'label':args.label,'observations':[]}
def call(method,params=None):
 global seq,buf
 seq+=1;msg={'id':seq,'method':method,'params':params or {}}
 if session:msg['sessionId']=session
 os.write(w,json.dumps(msg).encode()+b'\0');deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  while b'\0' in buf:
   raw,buf=buf.split(b'\0',1)
   if not raw:continue
   reply=json.loads(raw)
   if reply.get('id')==seq:
    if 'error' in reply:raise RuntimeError(reply)
    return reply.get('result',{})
  if select.select([rr],[],[],.25)[0]:
   data=os.read(rr,65536)
   if not data:raise RuntimeError('CDP closed')
   buf+=data
 raise RuntimeError('CDP timeout '+method)
def evaluate(js):
 reply=call('Runtime.evaluate',{'expression':js,'returnByValue':True,'awaitPromise':True})
 if 'exceptionDetails' in reply:raise RuntimeError(reply)
 return reply['result'].get('value')
def state():return evaluate('(async()=>await (await fetch("/api/state",{cache:"no-store"})).json())()')
def snapshot(name):
 data=evaluate('''(()=>({title:document.title,gapVisible:!document.getElementById('feed-gap-banner').hidden,gapText:document.getElementById('feed-gap-detail').textContent,manualDisabled:document.getElementById('submit-order').disabled,transportDisabled:[...document.querySelectorAll('.transport-submit')].map(b=>({disabled:b.disabled,text:b.textContent})),mode:document.getElementById('x2522-mode').textContent,transition:document.getElementById('x2522-transition').textContent,switchDisabled:document.getElementById('x2522-mode-switch').disabled,overflow:document.documentElement.scrollWidth>innerWidth,bodyText:document.body.innerText}))()''')
 data['api']=state();(out/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 (out/(name+'.png')).write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
 receipt['observations'].append({'name':name,'session':data['api']['session'],'feed':data['api']['feed']['integrity'],'gate':data['api']['feed']['trading_gate'],'mode':data['mode']})
 return data
try:
 target=call('Target.createTarget',{'url':'about:blank'})['targetId'];session=call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
 call('Page.enable');call('Runtime.enable');call('Page.navigate',{'url':'http://10.1.1.101:8088/'})
 for _ in range(80):
  if evaluate('Boolean(document.getElementById("replay-restart") && typeof app!=="undefined" && app.state?.session)'):break
  time.sleep(.25)
 else:raise RuntimeError('Webpage state did not load')
 time.sleep(1)
 before=snapshot('before')
 if args.action=='gap':
  assert before['gapVisible'] and before['manualDisabled']
  assert all(b['disabled'] for b in before['transportDisabled'])
  assert before['api']['feed']['integrity']=='GAP' and before['api']['replay']['status']=='PAUSED'
 elif args.action=='restart':
  evaluate('document.getElementById("replay-restart").click(); true')
  for _ in range(150):
   s=state()
   if s['session']!=before['api']['session'] and s['feed']['integrity']=='HEALTHY' and s['feed']['trading_gate']=='OPEN' and s['replay']['status']=='PLAYING' and evaluate('!document.getElementById("replay-restart").disabled && app.state.session === '+json.dumps(s['session'])+' && document.getElementById("feed-gap-banner").hidden && !document.getElementById("submit-order").disabled'):break
   time.sleep(.4)
  else:raise RuntimeError('Restart did not restore new healthy session')
  time.sleep(1);after=snapshot('after');assert not after['gapVisible'];assert not after['manualDisabled'];assert after['api']['strategy']['enabled'] is False
 elif args.action=='switch-roundtrip':
  assert before['api']['data_plane_mode']=='SFC'
  evaluate('window.auditConfirm=[];window.confirm=(text)=>{window.auditConfirm.push(text);return true};true')
  for targetmode in ['DPDK','SFC']:
   locked=evaluate('document.getElementById("x2522-mode-switch").click();renderTransportLab(app.state);({locked:document.getElementById("x2522-mode-switch").disabled,baselineLocked:document.getElementById("x2522-baseline").disabled,localLock:Boolean(app.switchingPlane),renderedTransition:app.state.data_plane_transition})')
   assert locked['locked'] and locked['baselineLocked'] and locked['localLock'],locked
   receipt.setdefault('locks',[]).append({'target':targetmode,**locked})
   for _ in range(240):
    s=state()
    if s['data_plane_mode']==targetmode and s['data_plane_transition']=='READY' and evaluate('!document.getElementById("x2522-mode-switch").disabled'):break
    time.sleep(.5)
   else:raise RuntimeError('Mode transition timed out '+targetmode)
   snap=snapshot(targetmode);assert '未完成' not in snap['transition']
  receipt['confirmations']=evaluate('window.auditConfirm')
 elif args.action=='lanz':
  data=evaluate('''(async()=>{const api=await(await fetch('http://10.1.1.101:8089/api/lanz')).json();const rows=[...document.querySelectorAll('.lanz-row')].map(x=>[...x.children].map(c=>c.textContent));const expected=[...api.events].reverse().map(e=>[({START:'S 开始',END:'E 结束',UPDATE:'U 更新'})[e.entry_type]||e.entry_type,e.intf_name,'TC'+e.traffic_class,String(e.queue_size),new Date(Math.floor(e.timestamp_us/1000)).toISOString().slice(0,19).replace('T',' ')+'.'+String(e.timestamp_us%1000000).padStart(6,'0')]);return {rows,expected,api,all_match:JSON.stringify(rows)===JSON.stringify(expected),removed_summary:!document.querySelector('#lanz-latest-event'),retention:document.querySelector('#lanz-history-summary').textContent};})()''')
  assert len(data['rows'])>0 and data['all_match'] and data['removed_summary'];assert all(e['timestamp_tick_us']==10 for e in data['api']['events'])
  (out/'lanz.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
  evaluate('document.getElementById("lanz-stream-card").scrollIntoView()');snapshot('lanz')
 receipt['result']='PASS'
except Exception as error:
 receipt.update(result='FAIL',error=str(error));raise
finally:
 (out/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5);os.close(w);os.close(rr);stderr.close()
 print(json.dumps(receipt,ensure_ascii=False))
