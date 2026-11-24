"""Check actual A/B controls in Chrome using isolated API fixtures."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
from manual_order_ui import FIXTURE as ORDER_FIXTURE

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ORDER_FIXTURE.split('window.calls=[];')[0] + r'''
Object.assign(window.uiState,{market_mode:'MULTICAST_A',market_network:{market_schema:'udp-multicast-ab-v1',market_group_a:'233.74.125.32',market_port_a:31032,market_group_b:'233.74.125.33',market_port_b:31033}});
Object.assign(window.uiState.health,{exchange:{status:'ONLINE'}});
window.uiState.instruments.AAPL.last_x10000=2961000;window.uiState.instruments.NVDA={last_x10000:2056000};
window.calls=[];window.replyMarket=null;
window.fetch=async(url,options={})=>{
 if(url==='/api/state')return {ok:true,json:async()=>structuredClone(window.uiState)};
 if(url==='/api/market'){
   const body=JSON.parse(options.body);window.calls.push(body);
   return await new Promise(resolve=>{window.replyMarket=(ok=true)=>{
     if(ok)window.uiState.market_mode=body.market_mode;
     resolve({ok,json:async()=>ok?{}:{error:'fixture failure'}});
   };});
 }
 if(String(url).endsWith('/api/lanz'))return {ok:true,json:async()=>({connected:false})};
 throw new Error('Unexpected request '+url);
};
window.EventSource=class{addEventListener(){}close(){}};
window.setInterval=()=>0;localStorage.clear();
'''
CHECKS = r'''
(async()=>{
 const results=[],check=(v,label)=>{if(!v)throw new Error(label);results.push(label);};
 const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
 try{
  await tick();
  const buttons=[...document.querySelectorAll('[data-mode]')],status=document.getElementById('market-switch-status');
  check(buttons.map(b=>b.textContent).join('|')==='仅 A 路|仅 B 路|A/B 双路','three multicast choices');
  check(buttons.every(b=>!b.disabled),'new Exchange enables controls');
  check(buttons[0].classList.contains('active')&&buttons[0].getAttribute('aria-pressed')==='true'&&window.calls.length===0,'A selected from actual state without clicking');
  check(status.textContent.includes('当前：仅 A 路组播'),'initial mode explicitly displayed');
  const readyNetwork=window.uiState.market_network;window.uiState.market_network={};await refresh();
  check(buttons.every(b=>b.disabled)&&status.textContent.includes('正在读取'),'metadata pending is explicit');
  window.uiState.market_network=readyNetwork;await refresh();
  check(buttons[0].classList.contains('active')&&status.textContent.includes('当前：仅 A 路组播'),'metadata arrival selects A without a mode change');
  check(document.getElementById('market-endpoints').textContent.includes('233.74.125.33:31033'),'B endpoint visible');
  for(const mode of ['MULTICAST_B','DUAL','MULTICAST_A']){
   const b=buttons.find(b=>b.dataset.mode===mode),before=window.calls.length;
   b.click();check(window.calls.length===before+1&&window.calls.at(-1).market_mode===mode,'request '+mode);
   check(status.textContent.includes('正在切换')&&buttons.every(b=>b.disabled),'pending '+mode);
   buttons.forEach(b=>b.click());check(window.calls.length===before+1,'no duplicate pending request '+mode);
   window.replyMarket();await tick();await tick();
   check(b.getAttribute('aria-pressed')==='true'&&buttons.filter(b=>b.classList.contains('active')).length===1,'active '+mode);
   check(status.textContent.includes('已切换')&&buttons.every(b=>!b.disabled),'confirmed '+mode);
  }
  buttons[1].click();window.replyMarket(false);await tick();await tick();
  check(status.textContent.includes('切换失败')&&buttons[0].classList.contains('active'),'failure keeps actual mode');
  window.uiState.market_network={};await refresh();check(buttons.every(b=>b.disabled),'old Exchange cannot activate new controls');
  window.uiState.market_network={market_schema:'udp-multicast-ab-v1',market_group_a:'233.74.125.32',market_port_a:31032,market_group_b:'233.74.125.33',market_port_b:31033};await refresh();
  status.textContent='已切换为仅 A 路';status.className='market-switch-status';document.getElementById('toast').className='';
  check(buttons.every(b=>b.scrollWidth<=b.clientWidth),'button text fits');
  check(document.documentElement.scrollWidth===innerWidth,'no horizontal overflow');
  document.body.dataset.testResult='PASS';
 }catch(error){document.body.dataset.testResult='FAIL';results.push(error.stack);}
 const p=document.createElement('pre');p.hidden=true;p.id='test-results';p.textContent=JSON.stringify(results);document.body.append(p);
})();
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--browser',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    page=(ROOT/'web/index.html').read_text().replace('<link rel="stylesheet" href="/terminal.css">','<style>'+(ROOT/'web/terminal.css').read_text()+'</style>')
    page=page.replace('<script src="/terminal.js"></script>','<script>'+FIXTURE+'</script><script>'+(ROOT/'web/terminal.js').read_text()+'</script><script>'+CHECKS+'</script>')
    page=page.replace('</head>','<style>body{padding:16px}main{display:block;width:100%;padding:0;margin:0}main>.card:not(.market-card),.topbar,.feed-gap-banner{display:none}.market-card{width:100%;min-height:490px}</style></head>')
    records=[]
    for width in (390,460):
        src=args.output/f'market-{width}.html';src.write_text(page)
        result=subprocess.run([args.browser,'--no-sandbox','--disable-gpu','--hide-scrollbars','--allow-file-access-from-files','--virtual-time-budget=6000',f'--window-size={width},620',f'--screenshot={args.output/f"market-{width}.png"}','--dump-dom',src.as_uri()],env=os.environ,capture_output=True,text=True,timeout=30)
        (args.output/f'market-{width}-dom.html').write_text(result.stdout)
        match=re.search(r'<pre hidden="" id="test-results">(.*?)</pre>',result.stdout,re.S)
        assert result.returncode==0 and 'data-test-result="PASS"' in result.stdout,(result.stderr[-1000:],html.unescape(match[1]) if match else result.stdout[-2000:])
        records.append({'width':width,'checks':json.loads(html.unescape(match[1]))})
    (args.output/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print('market_modes_ui=PASS widths=390,460')


if __name__=='__main__':main()
