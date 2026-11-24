"""Exercise actual order controls in headless Chrome with local HTTP stubs.

Usage: python3 tests/manual_order_ui.py --browser /path/to/chrome --output /tmp/ui-check
No requests reach an exchange or gateway.
"""
import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
window.uiState={session:'LOCAL_TEST',replay:{status:'PLAYING',loop:1,speed:1},
 features:{transport_lab:true},data_plane_mode:'SFC',data_plane_transition:'READY',
 feed:{integrity:'HEALTHY'},health:{trader_manual:{status:'ONLINE'},trader_auto:{status:'ONLINE'},trader_onload:{status:'ONLINE'},trader_tcpdirect:{status:'ONLINE'},trader_dpdk:{status:'WAITING'}},
 instruments:{AAPL:{bids:[[2960000,100]],asks:[[2961000,100]]}},orders:[{client_order_id:2099999999,origin:'MANUAL_GUI',side:'BUY',symbol:'AAPL',quantity:10,replay_loop:1,result:'ORDER_REJECTED',reject_reason:'PX'}]};
window.calls=[]; window.replyOrder=null;
window.fetch=async (url,options={})=>{
 if(url==='/api/state')return {ok:true,json:async()=>structuredClone(window.uiState)};
 if(url==='/api/order'){
   window.calls.push(JSON.parse(options.body));
   return await new Promise(resolve=>{window.replyOrder=(body,ok=true)=>resolve({ok,json:async()=>body});});
 }
 if(String(url).endsWith('/api/lanz'))return {ok:true,json:async()=>({connected:false})};
 throw new Error('Unexpected request: '+url);
};
window.EventSource=class{addEventListener(){} close(){}};
window.setInterval=()=>0;
localStorage.clear();
"""

CHECKS = r"""
(async()=>{
 const results=[],check=(condition,label)=>{if(!condition)throw new Error(label);results.push(label);};
 const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
 try{
  await tick();
  const submit=document.getElementById('submit-order'),quantity=document.getElementById('order-quantity'),status=document.getElementById('order-submit-status');
  const sell=document.querySelector('[data-side="SELL"]'),buy=document.querySelector('[data-side="BUY"]'),socket=document.querySelector('[data-order-transport="SOCKET"]');
  check(!submit.hidden&&getComputedStyle(submit).display!=='none'&&!submit.disabled,'upper submit visible with transport console enabled');
  quantity.value='20';quantity.dispatchEvent(new Event('input'));
  check(submit.textContent.includes('20 股'),'quantity shown before submitting');
  sell.click();check(window.calls.length===0&&submit.textContent.includes('卖单')&&sell.getAttribute('aria-pressed')==='true','direction selection does not place an order');
  buy.click();submit.click();
  check(window.calls.length===1&&window.calls[0].quantity===20&&window.calls[0].side==='BUY'&&window.calls[0].transport==='SOCKET','upper submit sends exactly one 20-share Socket order');
  check(status.textContent.includes('正在提交')&&status.textContent.includes('20 股')&&submit.disabled&&socket.disabled,'immediate pending feedback and buttons locked');
  await refresh();submit.click();socket.click();
  check(window.calls.length===1&&submit.disabled&&socket.disabled,'polling and repeated clicks cannot duplicate pending request');
  quantity.value='30';quantity.dispatchEvent(new Event('input'));
  window.replyOrder({client_order_id:2100000000});await tick();
  check(status.textContent.includes('#2100000000')&&status.textContent.includes('20 股')&&!submit.disabled,'acknowledgement uses submitted quantity and unlocks controls');
  await refresh();
  check(document.getElementById('manual-result').textContent==='已发送'&&document.getElementById('manual-order-id').textContent.includes('#2100000000'),'stale polling cannot replace new receipt with previous rejected order');
  const completed={client_order_id:2100000000,origin:'MANUAL_GUI',side:'BUY',symbol:'AAPL',quantity:20,filled_quantity:20,fill_price_x10000:2961000,position_delta:20,replay_loop:1,result:'ORDER_EXECUTED'};
  handleEvent({kind:'order_complete',fields:completed});
  check(document.getElementById('manual-result').textContent==='成交'&&document.getElementById('manual-order-detail').textContent.includes('成交 20 股'),'completion event immediately displays the new fill');
  window.uiState.orders.push(completed);await refresh();
  check(document.getElementById('manual-result').textContent==='成交','polling confirms completed receipt');
  socket.click();check(window.calls.length===2&&window.calls[1].transport==='SOCKET'&&window.calls[1].quantity===30,'lower Socket button shares form and submission path');
  window.replyOrder({error:'position limit'},false);await tick();
  check(status.textContent.includes('提交失败')&&status.textContent.includes('position limit')&&!submit.disabled,'failure stays visible and permits correction');
  quantity.value='0';quantity.dispatchEvent(new Event('input'));submit.click();
  check(window.calls.length===2&&status.textContent.includes('整数股数'),'invalid quantity does not send a request');
  quantity.value='20';quantity.dispatchEvent(new Event('input'));
  window.uiState.data_plane_mode='DPDK';window.uiState.health.trader_dpdk.status='ONLINE';await refresh();
  check(!submit.hidden&&submit.disabled&&submit.title.includes('DPDK')&&socket.disabled&&!document.querySelector('[data-order-transport="DPDK"]').disabled,'DPDK mode keeps upper control visible but prevents Socket orders');
  window.uiState.data_plane_mode='SFC';window.uiState.data_plane_transition='SWITCHING';await refresh();
  check(submit.disabled&&socket.disabled,'switching blocks both Socket controls');
  window.uiState.data_plane_transition='READY';window.uiState.feed.availability='STALE';await refresh();
  const banner=document.getElementById('feed-gap-banner');
  check(submit.disabled&&socket.disabled&&!banner.hidden&&banner.querySelector('strong').textContent==='行情接收中断','stale receiver blocks orders and identifies frozen ladder');
  window.uiState.feed.availability='ACTIVE';await refresh();
  check(!submit.disabled&&!socket.disabled&&banner.hidden,'live feed clears offline warning and restores controls');
  window.uiState.data_plane_transition='READY';window.uiState.feed.integrity='GAP';await refresh();
  check(submit.disabled&&socket.disabled&&!banner.hidden&&banner.querySelector('strong').textContent==='FEED GAP','feed gap blocks both Socket controls and keeps its own diagnosis');
  window.uiState.feed.integrity='HEALTHY';await refresh();
  check(!submit.disabled&&!socket.disabled,'healthy SFC state restores both controls');
  window.uiState.features.transport_lab=false;await refresh();
  check(!submit.hidden&&!submit.disabled&&document.getElementById('transport-lab').hidden,'ordinary mode still has a working submit control');
  window.uiState.features.transport_lab=true;await refresh();
  status.textContent='通过 Kernel Socket 提交；请先选择方向和数量。';status.className='order-submit-status';
  document.getElementById('toast').className='';
  document.body.dataset.testResult='PASS';
 }catch(error){document.body.dataset.testResult='FAIL';results.push(error.stack);}
 const output=document.createElement('pre');output.id='test-results';output.hidden=true;output.textContent=JSON.stringify(results);document.body.append(output);
})();
"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    page=(ROOT/'web/index.html').read_text()
    page=page.replace('<link rel="stylesheet" href="/terminal.css">','<style>'+(ROOT/'web/terminal.css').read_text()+'</style>')
    page=page.replace('<script src="/terminal.js"></script>','<script>'+FIXTURE+'</script><script>'+(ROOT/'web/terminal.js').read_text()+'</script><script>'+CHECKS+'</script>')
    # Keep the real card at a readable width for a focused visual review.
    page=page.replace('</head>','<style>body{padding:20px}main{display:block;width:470px;padding:0;margin:0}main>.card:not(.order-card),body>header,body>.feed-gap-banner{display:none}.order-card{width:430px}</style></head>')
    source=args.output/'manual-order-ui.html';source.write_text(page)
    result=subprocess.run([args.browser,'--no-sandbox','--disable-gpu','--allow-file-access-from-files','--no-proxy-server','--virtual-time-budget=3000','--window-size=500,760','--screenshot='+str(args.output/'manual-order-ui.png'),'--dump-dom',source.as_uri()],capture_output=True,text=True,timeout=30,env=os.environ)
    (args.output/'browser-stderr.txt').write_text(result.stderr)
    (args.output/'rendered.html').write_text(result.stdout)
    match=re.search(r'<pre id="test-results" hidden="">(.*?)</pre>',result.stdout,re.S)
    checks=json.loads(html.unescape(match[1])) if match else []
    passed=result.returncode==0 and 'data-test-result="PASS"' in result.stdout and bool(checks)
    (args.output/'results.json').write_text(json.dumps({'passed':passed,'checks':checks},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':passed,'checks':checks},ensure_ascii=False,indent=2))
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    main()
