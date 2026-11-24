"use strict";

const app = { state:null, selected:"AAPL", side:"BUY", stream:null, lastManualOrder:null };
const $ = (id) => document.getElementById(id);
const text = (id, value) => { const node=$(id); if (node) node.textContent=value ?? "—"; };
const TRANSPORTS = {
  SOCKET:{component:"trader_manual",key:"socket",label:"Kernel Socket",wire:"POSIX_SOCKET",mode:"SFC"},
  OPENONLOAD:{component:"trader_onload",key:"onload",label:"OpenOnload",wire:"OPENONLOAD",mode:"SFC"},
  TCPDIRECT:{component:"trader_tcpdirect",key:"tcpdirect",label:"TCPDirect",wire:"TCPDIRECT_ZF",mode:"SFC"},
  DPDK:{component:"trader_dpdk",key:"dpdk",label:"DPDK + TCP",wire:"DPDK_FSTACK",mode:"DPDK"},
};

function price(value) {
  const number=Number(value||0)/10000;
  return number ? number.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:4}) : "—";
}
function money(value) {
  const number=Number(value||0)/10000;
  return `${number<0?"−":""}$${Math.abs(number).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
}
function duration(ns) {
  const value=Number(ns||0); if (!value) return "—";
  if (value>=1e6) return `${(value/1e6).toFixed(3)} ms`;
  if (value>=1e3) return `${(value/1e3).toFixed(3)} µs`;
  return `${Math.round(value)} ns`;
}
function remaining(ns) {
  let seconds=Math.max(0,Math.ceil(Number(ns||0)/1e9));
  const hours=Math.floor(seconds/3600); seconds%=3600;
  const minutes=Math.floor(seconds/60); seconds%=60;
  if (hours) return `${hours}小时${minutes}分`;
  if (minutes) return `${minutes}分${seconds}秒`;
  return `${seconds}秒`;
}
function toast(message,error=false) {
  const node=$("toast"); node.textContent=message; node.className=error?"show error":"show";
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>{node.className="";},3200);
}
function loadManualOrder() { try{return JSON.parse(localStorage.getItem("flle-last-manual-order")||"null");}catch(_){return null;} }
function saveManualOrder(order) {
  if (!order) return;
  const same=String(order.client_order_id||"")===String(app.lastManualOrder?.client_order_id||"");
  app.lastManualOrder=same?{...app.lastManualOrder,...order}:{...order};
  try{localStorage.setItem("flle-last-manual-order",JSON.stringify(app.lastManualOrder));}catch(_){}
}
function clearManualOrder() {
  app.lastManualOrder=null; localStorage.removeItem("flle-last-manual-order");
  text("manual-result","尚未下单"); $("manual-result").className="";
  text("manual-order-id","—"); text("manual-order-detail","成交结果会固定显示在这里，不会一闪而过。");
}
async function request(path,options={}) {
  const response=await fetch(path,{cache:"no-store",headers:{"Content-Type":"application/json",...(options.headers||{})},...options});
  const body=await response.json(); if(!response.ok) throw new Error(body.error||`HTTP ${response.status}`); return body;
}
function selectedInstrument(){return app.state?.instruments?.[app.selected]||{};}
function selectedBook(){return app.state?.trader_books?.[app.selected]||selectedInstrument();}
function changeBps(state,symbol){const points=state.chart?.[symbol]||[];return points.length<2||!Number(points[0][1])?0:(Number(points.at(-1)[1])-Number(points[0][1]))*10000/Number(points[0][1]);}
function sourceClock(timestampNs) {
  let seconds=Math.floor(Number(timestampNs||0)/1e9); const hours=Math.floor(seconds/3600); seconds%=3600;
  const minutes=Math.floor(seconds/60); seconds%=60;
  return [hours,minutes,seconds].map(value=>String(value).padStart(2,"0")).join(":");
}
function svgNode(name,attributes={}) {
  const node=document.createElementNS("http://www.w3.org/2000/svg",name);
  Object.entries(attributes).forEach(([key,value])=>node.setAttribute(key,String(value))); return node;
}
function renderTrend(state) {
  const raw=state.chart?.[app.selected]||[], points=raw.map(point=>[Number(point[0]),Number(point[1])]).filter(point=>point[0]>0&&point[1]>0);
  const svg=$("price-chart"),empty=$("chart-empty"); svg.replaceChildren(); text("trend-symbol",app.selected); text("trend-samples",`${points.length} 个采样`);
  if(points.length<2){empty.hidden=false;text("trend-price",price(points.at(-1)?.[1]));text("trend-change","等待形成走势");$("trend-change").className="";text("trend-start","开始 —");text("trend-end","当前 —");return;}
  empty.hidden=true; const bounds=svg.getBoundingClientRect(),width=Math.max(420,Math.round(bounds.width||800)),height=Math.max(260,Math.round(bounds.height||260)),left=72,right=20,top=18,bottom=34,plotWidth=width-left-right,plotHeight=height-top-bottom;svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
  const first=points[0],last=points.at(-1),delta=last[1]-first[1],change=delta*10000/first[1],negative=delta<0;
  let low=Math.min(...points.map(point=>point[1])),high=Math.max(...points.map(point=>point[1])); const padding=Math.max(1,(high-low)*0.08);low-=padding;high+=padding;
  const timeSpan=Math.max(1,last[0]-first[0]),priceSpan=Math.max(1,high-low),xy=point=>[left+(point[0]-first[0])*plotWidth/timeSpan,top+(high-point[1])*plotHeight/priceSpan];
  for(let index=0;index<4;index+=1){const y=top+plotHeight*index/3,value=high-priceSpan*index/3;svg.appendChild(svgNode("line",{x1:left,y1:y,x2:width-right,y2:y,class:"chart-grid"}));const label=svgNode("text",{x:left-10,y:y+4,class:"chart-axis","text-anchor":"end"});label.textContent=price(value);svg.appendChild(label);}
  const coordinates=points.map(point=>xy(point)),line=coordinates.map(([x,y],index)=>`${index?"L":"M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  svg.appendChild(svgNode("path",{d:`${line} L${coordinates.at(-1)[0].toFixed(2)},${(top+plotHeight).toFixed(2)} L${coordinates[0][0].toFixed(2)},${(top+plotHeight).toFixed(2)} Z`,class:"chart-area"}));
  svg.appendChild(svgNode("path",{d:line,class:`chart-line${negative?" negative":""}`})); const [lastX,lastY]=coordinates.at(-1);svg.appendChild(svgNode("circle",{cx:lastX,cy:lastY,r:5,class:`chart-dot${negative?" negative":""}`}));
  text("trend-price",price(last[1]));text("trend-change",`${change>=0?"+":""}${change.toFixed(2)} bps`);$("trend-change").className=negative?"negative":"";
  text("trend-start",`开始 ${sourceClock(first[0])}`);text("trend-end",`当前 ${sourceClock(last[0])}`);
}

function setSelected(symbol){app.selected=symbol;$("order-symbol").value=symbol;render(app.state);}
function renderWatchlist(state){
  const watch=$("watchlist"); watch.replaceChildren();
  ["AAPL","NVDA"].forEach(symbol=>{
    const quote=state.instruments?.[symbol]||{}, change=changeBps(state,symbol), button=document.createElement("button");
    button.className=`watch-row ${symbol===app.selected?"active":""}`;
    button.innerHTML=`<strong>${symbol}</strong><span class="watch-price">${price(quote.last_x10000)}</span><small>NASDAQ</small><span class="change ${change<0?"negative":""}">${change>=0?"+":""}${change.toFixed(2)} bps</span>`;
    button.addEventListener("click",()=>setSelected(symbol)); watch.appendChild(button);
  });
}
function renderBook(){
  const book=selectedBook(), asks=Array.isArray(book.asks)?[...book.asks].reverse():[], bids=Array.isArray(book.bids)?book.bids:[];
  const maxQty=Math.max(1,...asks.map(row=>Number(row[1])),...bids.map(row=>Number(row[1])));
  const side=(target,levels,isAsk)=>{const node=$(target);node.replaceChildren();levels.forEach((row,index)=>{const item=document.createElement("div"),qty=Number(row[1]);item.className="book-row";item.innerHTML=`<i class="depth" style="width:${Math.max(3,qty/maxQty*100)}%"></i><span>L${isAsk?levels.length-index:index+1}</span><span class="price">${price(row[0])}</span><span>${qty.toLocaleString()}</span>`;node.appendChild(item);});};
  side("ask-book",asks,true);side("bid-book",bids,false);
  if(bids[0]&&book.asks?.[0]){const bid=Number(bids[0][0]),ask=Number(book.asks[0][0]);text("spread",`${price(ask-bid)} USD`);text("mid-price",`中间价 ${price((ask+bid)/2)}`);}
}
function renderReplay(state){
  const replay=state.replay||{}, progress=Math.max(0,Math.min(1,Number(replay.progress||0)));
  const names={PLAYING:"播放中",PAUSED:"已暂停",COMPLETE:"本轮完成",WAITING:"等待中"};
  text("replay-status",names[replay.status]||replay.status||"等待中"); text("replay-loop",`第 ${replay.loop||0} 轮`);
  text("wall-clock",`${replay.market_date||"2026-06-12"} ${String(replay.source_clock||"09:30:00.000").slice(0,18)}`);
  text("replay-progress-text",`${(progress*100).toFixed(2)}%`); $("replay-progress-fill").style.width=`${progress*100}%`;
  text("replay-window",`${String(replay.first_source_clock||"09:30:00").slice(0,8)} → ${String(replay.last_source_clock||"16:00:00").slice(0,8)}`);
  text("replay-remaining",replay.status==="COMPLETE"?"本轮完成，即将清空并重播":`预计剩余 ${remaining(replay.estimated_remaining_wall_ns)}`);
  $("replay-toggle").textContent=replay.status==="PAUSED"?"继续":"暂停";
  if(document.activeElement!==$("replay-speed")) $("replay-speed").value=String(replay.speed||1);
}
function renderReceipt(state){
  if(app.lastManualOrder&&Number(app.lastManualOrder.replay_loop||0)!==Number(state.replay?.loop||0)) clearManualOrder();
  const recent=[...(state.orders||[])].reverse().find(order=>order.origin==="MANUAL_GUI");
  if(recent) saveManualOrder(recent); const order=app.lastManualOrder; if(!order)return;
  const result=order.result||order.state||"QUEUED", labels={ORDER_EXECUTED:"成交",ORDER_REJECTED:"未成交",QUEUED:"已发送"};
  text("manual-result",labels[result]||result);$("manual-result").className=result==="ORDER_EXECUTED"?"executed":result==="ORDER_REJECTED"?"rejected":"queued";
  text("manual-order-id",`#${order.client_order_id||"—"} · ${order.side==="BUY"?"买入":"卖出"} ${order.quantity||"—"} ${order.symbol||"—"} @ ${order.limit_price_x10000?price(order.limit_price_x10000):"对手价"}`);
  const delta=Number(order.position_delta||0),deltaText=`${delta>0?"+":""}${delta}`;
  const route=Object.values(TRANSPORTS).find(item=>item.wire===order.order_transport||item.label===order.transport)?.label||order.transport||"Kernel Socket";
  text("manual-order-detail",result==="ORDER_EXECUTED"?`${route} · 成交 ${order.filled_quantity||order.quantity} 股 @ ${price(order.fill_price_x10000)} · 持仓 ${deltaText} · RTT ${duration(order.order_rtt_ns)}`:result==="ORDER_REJECTED"?`${route} · 未成交 · ${order.reject_reason==="PX"?"限价未穿过当前盘口":order.reject_reason||"被拒绝"} · RTT ${duration(order.order_rtt_ns)}`:`已进入 ${route} C++ 下单链路，等待交易所结果`);
}
function renderBlotter(state){
  const history=[...(state.orders||[])],manual=history.filter(order=>order.origin==="MANUAL_GUI").slice(-7),automatic=history.filter(order=>order.origin==="AUTO_STRATEGY").slice(-7);
  const node=$("blotter"),orders=[...manual,...automatic].sort((left,right)=>Number(right.event_ns||0)-Number(left.event_ns||0));node.replaceChildren();
  if(!orders.length){const empty=document.createElement("div");empty.className="blotter-empty";empty.textContent="本轮还没有订单";node.appendChild(empty);return;}
  orders.forEach(order=>{const row=document.createElement("div"),side=order.side||"—",result=order.result||order.state||"—",route=Object.values(TRANSPORTS).find(item=>item.wire===order.order_transport)?.label;row.className="blotter-row";row.innerHTML=`<span>${String(order.source_clock||"—").slice(0,12)}</span><span>${order.origin==="MANUAL_GUI"?(route||"手动"):"自动"}</span><span>${order.symbol||"—"}</span><span class="${side.toLowerCase()}">${side==="BUY"?"买":"卖"}</span><span>${order.filled_quantity??order.quantity??"—"}</span><span>${price(order.fill_price_x10000||order.limit_price_x10000)}</span><span class="${result==="ORDER_EXECUTED"?"filled":result==="ORDER_REJECTED"?"rejected":""}">${result==="ORDER_EXECUTED"?"成交":result==="ORDER_REJECTED"?"未成交":"等待"}</span><span>${duration(order.order_rtt_ns)}</span>`;node.appendChild(row);});
}
function feedIntegrity(state){
  const feed=state.feed||{};
  if(feed.integrity) return feed.integrity;
  return (Number(feed.pending||0)>0 || Number(feed.gaps||0)>0) ? "GAP" : "HEALTHY";
}
function renderFeedGap(state){
  const gap=feedIntegrity(state)==="GAP", banner=$("feed-gap-banner"), feed=state.feed||{};
  if(banner) banner.hidden=!gap;
  document.body.classList.toggle("feed-gap", gap);
  if(gap) text("feed-gap-detail", `行情序号中断 · next_expected=${feed.next_expected||"—"} · pending=${feed.pending||0} · gap_size=${feed.gap_size||0} · 已持续 ${feed.gap_age_ms||0} ms。订单簿冻结，交易已停单。`);
}
function renderHealth(state){
  const exchange=state.health?.exchange?.status||"WAITING",auto=state.health?.trader_auto?.status||"WAITING",manual=state.health?.trader_manual?.status||"WAITING";text("exchange-health",exchange);
  $("node-exchange").classList.toggle("online",exchange==="ONLINE");$("node-trader").classList.toggle("online",auto==="ONLINE"&&manual==="ONLINE");$("node-gateway").classList.add("online");
}
function renderTransportLab(state){
  const enabled=Boolean(state.features?.transport_lab),lab=$("transport-lab");lab.hidden=!enabled;$("submit-order").hidden=enabled;if(!enabled)return;
  const mode=String(state.data_plane_mode||"SFC").startsWith("DPDK")?"DPDK":"SFC",transition=String(state.data_plane_transition||"READY");
  const switchButton=$("x2522-mode-switch"),target=mode==="DPDK"?"SFC":"DPDK";
  text("x2522-mode",`${mode} ACTIVE`);text("x2522-owner",state.data_plane_owner||(mode==="DPDK"?"vfio-pci":"sfc"));text("x2522-transition",transition);text("x2522-rule-text",mode==="DPDK"?"DPDK 独占 X2522；三条 sfc 路径已停流":"三条 sfc 路径可用；DPDK 等待独占切换");text("x2522-mode-switch",target==="DPDK"?"切到 DPDK 独占":"交还并切回 SFC");switchButton.dataset.targetMode=target;switchButton.disabled=transition!=="READY";
  const canTrade=feedIntegrity(state)==="HEALTHY"&&Boolean(selectedBook().bids?.[0]&&selectedBook().asks?.[0])&&["PLAYING","PAUSED"].includes(state.replay?.status);
  Object.entries(TRANSPORTS).forEach(([,config])=>{
    const health=state.health?.[config.component]?.status||"WAITING",card=$(`transport-card-${config.key}`),button=card.querySelector(".transport-submit"),available=config.mode===mode&&health==="ONLINE"&&transition==="READY";
    text(`transport-status-${config.key}`,health);card.classList.toggle("online",health==="ONLINE");card.classList.toggle("available",available);card.classList.toggle("unavailable",config.mode!==mode);button.disabled=!(available&&canTrade);
    const latency=state.client_latency?.[config.component]||{};text(`transport-rtt-${config.key}`,duration(latency.p50_ns));text(`compare-rtt-${config.key}`,duration(latency.p50_ns));text(`transport-samples-${config.key}`,latency.samples||0);
    const receipt=state.hardware_receipts?.[config.key],receiptNode=$(`transport-receipt-${config.key}`);receiptNode.classList.toggle("pending",!receipt?.verified);receiptNode.textContent=receipt?.verified?(receipt.summary||"当前机器硬件路径已验真"):"收据待采集";
  });
  const latest=[...(state.orders||[])].reverse().find(order=>order.origin==="MANUAL_GUI"&&order.order_transport),last=Object.values(TRANSPORTS).find(item=>item.wire===latest?.order_transport);text("x2522-last-route",`最后下单通道：${last?.label||"—"}${latest?.order_rtt_ns?` · ${duration(latest.order_rtt_ns)}`:""}`);
}
function render(state){
  if(state?.gui_reset_ns && state.gui_reset_ns!==app.state?.gui_reset_ns) clearManualOrder();
  if(!state)return;app.state=state;text("session",`SESSION ${state.session||"—"}`);text("market-mode",state.market_mode||"—");
  renderReplay(state);renderWatchlist(state);renderTrend(state);const quote=selectedInstrument(),book=selectedBook();text("selected-symbol",app.selected);text("book-symbol",app.selected);text("hero-price",price(quote.last_x10000));
  const bid=book.bids?.[0],ask=book.asks?.[0];text("best-bid",price(bid?.[0]));text("bid-size",bid?`${bid[1]} 股`:"—");text("best-ask",price(ask?.[0]));text("ask-size",ask?`${ask[1]} 股`:"—");
  const feedHealthy=feedIntegrity(state)==="HEALTHY";
  $("submit-order").disabled=!feedHealthy||!(bid&&ask)||!["PLAYING","PAUSED"].includes(state.replay?.status);
  renderFeedGap(state);
  document.querySelectorAll("[data-mode]").forEach(button=>button.classList.toggle("active",button.dataset.mode===state.market_mode));renderBook();
  const strategy=state.strategy||{},threshold=Math.round(Number(strategy.imbalance_threshold||0)*100),cooldown=Number(strategy.cooldown_ms||0)/1000;
  $("strategy-toggle").classList.toggle("off",!strategy.enabled);text("strategy-state",strategy.enabled?"已开启":"已关闭");
  const cooldownLabel=Number.isInteger(cooldown)?String(cooldown):cooldown.toFixed(1);
  text("strategy-rule",`五档失衡 ≥ ${threshold}% → ${strategy.quantity||0} 股 IOC`);text("strategy-guard",`同标的冷却 ${cooldownLabel} 秒 · AUTO 仓位上限 ±${strategy.max_position||0}`);
  text("position-aapl",state.positions?.AAPL??0);text("position-nvda",state.positions?.NVDA??0);text("pnl",money(state.pnl_x10000));
  const latency=state.latency||{};text("latency-p50",duration(latency.p50_ns));text("latency-p99",duration(latency.p99_ns));text("latency-max",duration(latency.max_ns));text("latency-samples",latency.samples||0);
  text("exchange-ledger-count",state.exchange_ledger_entries||0);text("fill-count",state.stats?.fills||0);text("order-count",state.stats?.orders||0);renderReceipt(state);renderBlotter(state);renderHealth(state);renderTransportLab(state);
}
function handleEvent(event){
  const fields=event.fields||{};
  if(event.kind==="replay_started"||event.kind==="paper_reset") clearManualOrder();
  if(event.kind==="order_queued"&&fields.origin==="MANUAL_GUI") saveManualOrder({...fields,state:"QUEUED",replay_loop:app.state?.replay?.loop||0});
  if(event.kind==="order_complete"&&fields.origin==="MANUAL_GUI"){saveManualOrder(fields);renderReceipt(app.state||{orders:[],replay:{loop:app.lastManualOrder?.replay_loop}});}
}
async function refresh(){try{render(await request("/api/state"));}catch(error){toast(error.message,true);}}
function connectStream(){app.stream?.close();const stream=new EventSource(`/api/stream?after=${app.state?.gateway_sequence||0}`);app.stream=stream;stream.onopen=()=>{$("stream-dot").className="ok";text("stream-label","实时连接");};stream.addEventListener("trading",message=>handleEvent(JSON.parse(message.data)));stream.onerror=()=>{$("stream-dot").className="bad";text("stream-label","正在重连");};}

document.querySelectorAll("[data-mode]").forEach(button=>button.addEventListener("click",async()=>{try{await request("/api/market",{method:"POST",body:JSON.stringify({market_mode:button.dataset.mode})});toast(`行情已切换为${button.textContent}`);await refresh();}catch(error){toast(error.message,true);}}));
document.querySelectorAll("[data-side]").forEach(button=>button.addEventListener("click",()=>{app.side=button.dataset.side;document.querySelectorAll("[data-side]").forEach(item=>item.classList.toggle("active",item===button));text("submit-order",`发送${app.side==="BUY"?"买入":"卖出"}订单`);$("submit-order").style.background=app.side==="BUY"?"var(--green)":"var(--red)";}));
$("order-symbol").addEventListener("change",()=>setSelected($("order-symbol").value));
async function submitOrder(transport="SOCKET"){try{const raw=$("order-price").value.trim(),route=TRANSPORTS[transport],result=await request("/api/order",{method:"POST",body:JSON.stringify({symbol:$("order-symbol").value,side:app.side,quantity:Number($("order-quantity").value),limit_price_x10000:raw?Math.round(Number(raw)*10000):0,transport})});saveManualOrder({client_order_id:result.client_order_id,origin:"MANUAL_GUI",order_transport:route.wire,transport:route.label,symbol:$("order-symbol").value,side:app.side,quantity:Number($("order-quantity").value),limit_price_x10000:raw?Math.round(Number(raw)*10000):0,state:"QUEUED",replay_loop:app.state?.replay?.loop||0});renderReceipt(app.state||{orders:[],replay:{loop:app.lastManualOrder.replay_loop}});toast(`订单 #${result.client_order_id} 已进入 ${route.label} 链路`);}catch(error){toast(error.message,true);}}
$("submit-order").addEventListener("click",()=>submitOrder("SOCKET"));
document.querySelectorAll("[data-order-transport]").forEach(button=>button.addEventListener("click",()=>submitOrder(button.dataset.orderTransport)));
$("x2522-mode-switch").addEventListener("click",async()=>{const button=$("x2522-mode-switch"),mode=button.dataset.targetMode;if(!["SFC","DPDK"].includes(mode))return;const warning=mode==="DPDK"?"切到 DPDK 会停止三条 sfc 客户端，并由 VFIO 暂时接管 X2522。继续吗？":"将停止 DPDK、交还 X2522，并恢复三条 sfc 客户端。继续吗？";if(!window.confirm(warning))return;button.disabled=true;text("x2522-transition","SWITCHING");try{await request("/api/data-plane",{method:"POST",body:JSON.stringify({mode})});toast(mode==="DPDK"?"X2522 已交给 DPDK":"X2522 已交还 sfc");await refresh();}catch(error){toast(error.message,true);await refresh();}});
$("strategy-toggle").addEventListener("click",async()=>{try{await request("/api/strategy",{method:"POST",body:JSON.stringify({enabled:!app.state.strategy.enabled})});await refresh();}catch(error){toast(error.message,true);}});
$("replay-toggle").addEventListener("click",async()=>{try{const action=app.state?.replay?.status==="PAUSED"?"RESUME":"PAUSE";await request("/api/replay",{method:"POST",body:JSON.stringify({action})});await refresh();}catch(error){toast(error.message,true);}});
$("replay-restart").addEventListener("click",async()=>{const button=$("replay-restart");button.disabled=true;try{toast("正在清空各通道交易并重新开始，请稍候");await request("/api/replay",{method:"POST",body:JSON.stringify({action:"RESTART",clear_trades:true})});clearManualOrder();await refresh();await refreshLanz();toast("已重新开始，交易、统计、图表和交换机队列事件已重置");}catch(error){toast(error.message,true);}finally{button.disabled=false;}});
$("replay-speed").addEventListener("change",async()=>{try{const speed=Number($("replay-speed").value);await request("/api/replay",{method:"POST",body:JSON.stringify({action:"SPEED",speed})});toast(`播放速度已设为 ${speed}×`);}catch(error){toast(error.message,true);}});

function lanzClock(microseconds) {
  const value=Number(microseconds||0);
  if(!value) return "—";
  if(value>=1577836800000000 && value<4102444800000000){
    return new Date(value/1000).toISOString().replace("T"," ").replace("Z","Z");
  }
  return `${value} µs`;
}
function renderLanz(data) {
  const connected=Boolean(data&&data.connected);
  text("lanz-stream-status", connected ? "已连上 7150:50001" : (data&&data.error ? `未连上：${data.error}` : "接收器未连接"));
  $("lanz-stream-status").className = connected ? "lanz-ok" : "";
  const counts=data&&data.counts||{};
  text("lanz-count-start", counts.START||0);
  text("lanz-count-update", counts.UPDATE||0);
  text("lanz-count-end", counts.END||0);
  text("lanz-segment-size", data&&data.config&&data.config.segment_size ? `${data.config.segment_size} B` : "—");
  const node=$("lanz-stream-rows");
  if(!node) return;
  const events=[...(data&&data.events||[])].slice().reverse();
  node.replaceChildren();
  if(!events.length){
    const empty=document.createElement("div");
    empty.className="lanz-empty";
    empty.textContent="还没有收到拥塞事件";
    node.appendChild(empty);
    return;
  }
  events.slice(0,12).forEach(event=>{
    const row=document.createElement("div");
    const kind=event.entry_type||"—";
    row.className="lanz-row";
    row.innerHTML=`<span class="${kind.toLowerCase()}">${kind==="START"?"S 开始":kind==="END"?"E 结束":kind==="UPDATE"?"U 更新":kind}</span><span>${event.intf_name||"—"}</span><span>${event.traffic_class??"—"}</span><span>${event.queue_size??"—"}</span><span>${lanzClock(event.timestamp_us)}</span>`;
    node.appendChild(row);
  });
}
async function refreshLanz() {
  try {
    const response=await fetch(`${location.protocol}//${location.hostname}:8089/api/lanz`,{cache:"no-store"});
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    renderLanz(await response.json());
  } catch(_) {
    renderLanz(null);
  }
}

(async()=>{app.lastManualOrder=loadManualOrder();await refresh();connectStream();setInterval(refresh,1000);await refreshLanz();setInterval(refreshLanz,500);})();
window.addEventListener("beforeunload",()=>app.stream?.close());
