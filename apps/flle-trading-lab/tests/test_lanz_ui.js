// Browser regression: call with terminal.js source and the LANZ HTML section mounted.
function runLanzUITests(source) {
  const code=source.slice(source.indexOf('function lanzClock('),source.indexOf('async function refreshLanz()'));
  const get=id=>document.getElementById(id), assert=(value,msg)=>{if(!value)throw Error(msg);};
  const ui=new Function('$','text',code+'\nreturn {renderLanz,lanzClock};')(get,(id,value)=>{const n=get(id);if(n)n.textContent=value;});
  const rows=()=>[...document.querySelectorAll('.lanz-row')].map(row=>[...row.children].map(cell=>cell.textContent));
  const events=[];
  for(let i=0;i<40;i++)for(const [kind,offset] of [['START',0],['END',2]]){
    const raw=178956311869000+i*100+offset;
    events.push({intf_name:'Ethernet2',traffic_class:1,entry_type:kind,queue_size:[64,80,84,86][i%4],
      timestamp_raw:raw,timestamp_tick_us:10,timestamp_us:raw*10});
  }
  const data={connected:true,config:{segment_size:480},events};
  ui.renderLanz(data);
  assert(!get('lanz-latest-event')&&!get('lanz-history-toggle'),'summary or collapse still present');
  assert(rows().length===80,'retained records should all be shown by default');
  const kind={START:'S 开始',END:'E 结束',UPDATE:'U 更新'};
  rows().forEach((row,i)=>{
    const e=events[events.length-1-i];
    assert(JSON.stringify(row)===JSON.stringify([kind[e.entry_type],e.intf_name,'TC1',String(e.queue_size),ui.lanzClock(e)]),'record changed: '+i);
  });
  assert(rows()[0][4]==='2026-09-16 12:51:58.729020','timestamp scale/precision');
  assert(get('lanz-history-summary').textContent.includes('上限 80 条'),'retention limit missing');
  const container=get('lanz-stream-rows'),first=container.firstElementChild;
  container.scrollTop=100; const position=container.scrollTop;
  ui.renderLanz({...data,connected:false,error:'connection refused'});
  assert(container.firstElementChild===first&&container.scrollTop===position,'refresh interrupts reading');
  assert(get('lanz-stream-status').textContent.includes('历史记录'),'disconnected history unclear');
  assert(ui.lanzClock({timestamp_us:178956311872902})==='时间单位未确认','old buggy unit silently accepted');
  const extra={...events[0],entry_type:'UPDATE',intf_name:'Ethernet3',traffic_class:5,queue_size:84};
  ui.renderLanz({...data,events:[events[0],events[0],extra]});
  assert(rows().length===3&&rows()[0][0]==='U 更新'&&rows()[0][1]==='Ethernet3'&&rows()[0][2]==='TC5','records filtered, paired or deduplicated');
  assert(rows()[1][0]==='S 开始'&&rows()[2][0]==='S 开始','unmatched START hidden');
  ui.renderLanz({...data,events:[]});
  assert(rows().length===0&&container.textContent==='还没有收到拥塞记录','reset leaves stale rows');
  ui.renderLanz(data);
  return 'PASS: all 80 raw records visible, exact values including 64/80/84/86, UTC microseconds, stable scroll, disconnect, old unit, UPDATE/other queues, duplicate and unmatched records, reset';
}
