"use strict";

const app = { state:null, selected:"AAPL", side:"BUY", stream:null, lastManualOrder:null, submittingOrder:false, pendingManualReceipt:null, switchingMarket:false, switchingPlane:null, planeError:"" };
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
  app.lastManualOrder=null;app.pendingManualReceipt=null; localStorage.removeItem("flle-last-manual-order");
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
  const history=[...(state.orders||[])].reverse();
  const recent=app.pendingManualReceipt!==null?history.find(order=>String(order.client_order_id)===String(app.pendingManualReceipt)):history.find(order=>order.origin==="MANUAL_GUI");
  if(recent) app.pendingManualReceipt=null;
  if(recent) saveManualOrder(recent); const order=app.lastManualOrder; if(!order)return;
  const result=order.result||order.state||"QUEUED", labels={ORDER_EXECUTED:"成交",ORDER_REJECTED:"未成交",QUEUED:"已发送"};
  text("manual-result",labels[result]||result);$("manual-result").className=result==="ORDER_EXECUTED"?"executed":result==="ORDER_REJECTED"?"rejected":"queued";
  text("manual-order-id",`#${order.client_order_id||"—"} · ${order.side==="BUY"?"买入":"卖出"} ${order.quantity||"—"} ${order.symbol||"—"} @ ${order.limit_price_x10000?price(order.limit_price_x10000):"对手价"}`);
  const delta=Number(order.position_delta||0),deltaText=`${delta>0?"+":""}${delta}`;
  const route=Object.values(TRANSPORTS).find(item=>item.wire===order.order_transport||item.label===order.transport)?.label||order.transport||"Kernel Socket";
  text("manual-order-detail",result==="ORDER_EXECUTED"?`${route} · 成交 ${order.filled_quantity||order.quantity} 股 @ ${price(order.fill_price_x10000)} · 持仓 ${deltaText} · RTT ${duration(order.order_rtt_ns)}`:result==="ORDER_REJECTED"?`${route} · 未成交 · ${order.reject_reason==="PX"?(order.side==="BUY"?"买入限价低于交易所当时的卖一价":"卖出限价高于交易所当时的买一价"):order.reject_reason||"被拒绝"} · RTT ${duration(order.order_rtt_ns)}`:`已进入 ${route} C++ 下单链路，等待交易所结果`);
}
function renderBlotter(state){
  const history=[...(state.orders||[])],manual=history.filter(order=>order.origin==="MANUAL_GUI").slice(-7),automatic=history.filter(order=>order.origin==="AUTO_STRATEGY").slice(-7);
  const node=$("blotter"),orders=[...manual,...automatic].sort((left,right)=>Number(right.event_ns||0)-Number(left.event_ns||0));node.replaceChildren();
  if(!orders.length){const empty=document.createElement("div");empty.className="blotter-empty";empty.textContent="本轮还没有订单";node.appendChild(empty);return;}
  orders.forEach(order=>{const row=document.createElement("div"),side=order.side||"—",result=order.result||order.state||"—",route=Object.values(TRANSPORTS).find(item=>item.wire===order.order_transport)?.label;row.className="blotter-row";row.innerHTML=`<span>${String(order.source_clock||"—").slice(0,12)}</span><span>${order.origin==="MANUAL_GUI"?(route||"手动"):"自动"}</span><span>${order.symbol||"—"}</span><span class="${side.toLowerCase()}">${side==="BUY"?"买":"卖"}</span><span>${order.filled_quantity??order.quantity??"—"}</span><span>${price(order.fill_price_x10000||order.limit_price_x10000)}</span><span class="${result==="ORDER_EXECUTED"?"filled":result==="ORDER_REJECTED"?"rejected":""}">${result==="ORDER_EXECUTED"?"成交":result==="ORDER_REJECTED"?"未成交":"等待"}</span><span>${duration(order.order_rtt_ns)}</span>`;node.appendChild(row);});
}
function feedIntegrity(state){
  const feed=state.feed||{};
  if(feed.availability==="STALE") return "STALE";
  if(feed.integrity) return feed.integrity;
  return (Number(feed.pending||0)>0 || Number(feed.gaps||0)>0) ? "GAP" : "HEALTHY";
}
function renderFeedGap(state){
  const gap=feedIntegrity(state)==="GAP", stale=feedIntegrity(state)==="STALE", banner=$("feed-gap-banner"), feed=state.feed||{};
  if(banner){banner.hidden=!(gap||stale);const title=banner.querySelector("strong");if(title)title.textContent=stale?"行情接收中断":"FEED GAP";}
  document.body.classList.toggle("feed-gap", gap||stale);
  if(stale) text("feed-gap-detail", "行情接收器或建簿程序已离线，当前五档是最后收到的快照，暂不能下单。请执行本实验的恢复或收尾步骤。");
  if(gap) text("feed-gap-detail", `行情序号中断 · next_expected=${feed.next_expected||"—"} · pending=${feed.pending||0} · gap_size=${feed.gap_size||0} · 已持续 ${feed.gap_age_ms||0} ms。订单簿冻结，交易已停单。${feed.resync_required?" 缓存已受限，需重新同步；重新开始并清空交易会重建回放起点。":""}`);
}
function renderHealth(state){
  const exchange=state.health?.exchange?.status||"WAITING",auto=state.health?.trader_auto?.status||"WAITING",manual=state.health?.trader_manual?.status||"WAITING";text("exchange-health",exchange);
  $("node-exchange").classList.toggle("online",exchange==="ONLINE");$("node-trader").classList.toggle("online",state.experiment_profile==="SOFTWARE"?auto==="ONLINE"&&manual==="ONLINE":Object.values(TRANSPORTS).some(config=>state.health?.[config.component]?.status==="ONLINE"));$("node-gateway").classList.add("online");
}
function orderUnavailable(state,transport="SOCKET"){
  if(!state) return "正在连接交易系统";
  if(feedIntegrity(state)!=="HEALTHY") return "行情尚未同步，暂不能提交";
  if(!(selectedBook().bids?.[0]&&selectedBook().asks?.[0])) return "等待买卖盘口";
  if(!["PLAYING","PAUSED"].includes(state.replay?.status)) return "等待行情回放就绪";
  if(state.features?.transport_lab){
    if(state.data_plane_transition!=="READY") return "正在切换通道，请稍候";
    const mode=String(state.data_plane_mode||"SFC").startsWith("DPDK")?"DPDK":"SFC";
    if(TRANSPORTS[transport].mode!==mode) return transport==="SOCKET"?"当前为 DPDK 模式，请使用下方 DPDK 下单按钮":"该通道当前不可用";
  }
  if(state.health?.[TRANSPORTS[transport].component]?.status!=="ONLINE") return `${TRANSPORTS[transport].label} 尚未就绪`;
  return "";
}
function renderOrderSubmit(){
  const button=$("submit-order"),reason=orderUnavailable(app.state);
  button.hidden=false;
  button.disabled=app.submittingOrder||Boolean(reason);
  button.title=reason||"通过 Kernel Socket 提交订单";
  text("submit-order",app.submittingOrder?"正在提交…":`提交${app.side==="BUY"?"买单":"卖单"} · ${$("order-symbol").value} ${$("order-quantity").value||"—"} 股`);
  button.style.background=app.side==="BUY"?"var(--green)":"var(--red)";
}
function renderTransportLab(state){
  const enabled=Boolean(state.features?.transport_lab),lab=$("transport-lab");lab.hidden=!enabled;if(!enabled)return;
  const mode=String(state.data_plane_mode||"SFC").startsWith("DPDK")?"DPDK":"SFC",transition=String(state.data_plane_transition||"READY");
  const pending=app.switchingPlane, busy=Boolean(pending)||transition!=="READY";
  const elapsed=pending?Math.floor((Date.now()-pending.started)/1000):0;
  const progress=pending?`${pending.mode==="DPDK"?"正在切到 DPDK":pending.mode==="SFC"?"正在交还网卡并恢复 SFC":"正在恢复普通交易"} · 已等待 ${elapsed} 秒`:transition;
  const software=state.experiment_profile==="SOFTWARE";
  const switchButton=$("x2522-mode-switch"),target=mode==="DPDK"?"SFC":"DPDK";
  const baselineButton=$("x2522-baseline");baselineButton.hidden=software;baselineButton.disabled=busy;
  text("x2522-mode",software?"普通交易":"路径测试 · "+mode);text("x2522-owner",state.data_plane_owner||(mode==="DPDK"?"vfio-pci":"sfc"));text("x2522-transition",app.planeError||progress);text("x2522-rule-text",software?"Socket、Onload、TCPDirect 都可下单；DPDK 需切换独占":mode==="DPDK"?"DPDK 独占 X2522；三条 sfc 路径已停流":"三条 sfc 路径可用；DPDK 等待独占切换");text("x2522-mode-switch",target==="DPDK"?"切到 DPDK 独占":"交还并切回 SFC");switchButton.dataset.targetMode=target;switchButton.disabled=busy;
  Object.entries(TRANSPORTS).forEach(([transport,config])=>{
    const health=state.health?.[config.component]?.status||"WAITING",card=$(`transport-card-${config.key}`),button=card.querySelector(".transport-submit"),available=config.mode===mode&&health==="ONLINE"&&transition==="READY";
    text(`transport-status-${config.key}`,health);card.classList.toggle("online",health==="ONLINE");card.classList.toggle("available",available);card.classList.toggle("unavailable",config.mode!==mode);button.disabled=busy||app.submittingOrder||Boolean(orderUnavailable(state,transport));
    const latency=state.client_latency?.[config.component]||{};text(`transport-rtt-${config.key}`,duration(latency.p50_ns));text(`compare-rtt-${config.key}`,duration(latency.p50_ns));text(`transport-samples-${config.key}`,latency.samples||0);
    const receipt=state.hardware_receipts?.[config.key],receiptNode=$(`transport-receipt-${config.key}`);receiptNode.classList.toggle("pending",!receipt?.verified);receiptNode.textContent=receipt?.verified?(receipt.summary||"当前机器硬件路径已验真"):software?"已部署并启动；路径证据在测试时采集":"收据待采集";
  });
  const latest=[...(state.orders||[])].reverse().find(order=>order.origin==="MANUAL_GUI"&&order.order_transport),last=Object.values(TRANSPORTS).find(item=>item.wire===latest?.order_transport);text("x2522-last-route",`最后下单通道：${last?.label||"—"}${latest?.order_rtt_ns?` · ${duration(latest.order_rtt_ns)}`:""}`);
}
function render(state){
  if(state?.gui_reset_ns && state.gui_reset_ns!==app.state?.gui_reset_ns) clearManualOrder();
  if(!state)return;app.state=state;text("session",`SESSION ${state.session||"—"}`);text("market-mode",({MULTICAST_A:"仅 A 路组播",MULTICAST:"仅 A 路组播",MULTICAST_B:"仅 B 路组播",DUAL:"A/B 双路组播",UNICAST:"内部单播"})[state.market_mode]||state.market_mode||"—");
  renderReplay(state);renderWatchlist(state);renderTrend(state);const quote=selectedInstrument(),book=selectedBook();text("selected-symbol",app.selected);text("book-symbol",app.selected);text("hero-price",price(quote.last_x10000));
  const bid=book.bids?.[0],ask=book.asks?.[0];text("best-bid",price(bid?.[0]));text("bid-size",bid?`${bid[1]} 股`:"—");text("best-ask",price(ask?.[0]));text("ask-size",ask?`${ask[1]} 股`:"—");
  renderOrderSubmit();
  renderFeedGap(state);
  const network=state.market_network||{},abReady=network.market_schema==="udp-multicast-ab-v1";
  text("market-endpoints",abReady?`A  ${network.market_group_a}:${network.market_port_a}\nB  ${network.market_group_b}:${network.market_port_b}`:"等待 A/B 行情通道就绪");
  const currentMode=state.market_mode==="MULTICAST"?"MULTICAST_A":state.market_mode;
  const marketStatus=$("market-switch-status"),modeLabel=({MULTICAST_A:"仅 A 路组播",MULTICAST_B:"仅 B 路组播",DUAL:"A/B 双路组播"})[currentMode];
  if(!app.switchingMarket&&(marketStatus.dataset.observedMode!==currentMode||marketStatus.dataset.ready!==String(abReady))){
    marketStatus.className="market-switch-status";
    marketStatus.textContent=abReady?(modeLabel?`当前：${modeLabel}`:`当前：${currentMode}，请选择 A/B 行情通道`):"正在读取行情模式…";
    marketStatus.dataset.observedMode=currentMode;
    marketStatus.dataset.ready=String(abReady);
  }
  document.querySelectorAll("[data-mode]").forEach(button=>{
    const active=button.dataset.mode===(state.market_mode==="MULTICAST"?"MULTICAST_A":state.market_mode);
    button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));
    button.disabled=app.switchingMarket||!abReady;
  });renderBook();
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

document.querySelectorAll("[data-mode]").forEach(button=>button.addEventListener("click",async()=>{
  if(app.switchingMarket)return;
  app.switchingMarket=true;const status=$("market-switch-status"),mode=button.dataset.mode;
  status.className="market-switch-status";status.textContent=`正在切换为${button.textContent}…`;render(app.state);
  try{
    await request("/api/market",{method:"POST",body:JSON.stringify({market_mode:mode})});
    let confirmed=false;
    for(let i=0;i<30;i++){
      const state=await request("/api/state");render(state);
      if(state.market_mode===mode){confirmed=true;break;}
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    if(!confirmed)throw new Error("暂未确认模式生效，请查看当前行情状态");
    status.textContent=`已切换为${button.textContent}`;status.dataset.observedMode=mode;toast(status.textContent);
  }catch(error){status.className="market-switch-status error";status.textContent=`切换失败：${error.message}`;toast(error.message,true);}
  finally{app.switchingMarket=false;render(app.state);}
}));
document.querySelectorAll("[data-side]").forEach(button=>button.addEventListener("click",()=>{app.side=button.dataset.side;document.querySelectorAll("[data-side]").forEach(item=>{item.classList.toggle("active",item===button);item.setAttribute("aria-pressed",String(item===button));});renderOrderSubmit();}));
$("order-symbol").addEventListener("change",()=>{setSelected($("order-symbol").value);renderOrderSubmit();});
$("order-quantity").addEventListener("input",renderOrderSubmit);
async function submitOrder(transport="SOCKET"){
  if(app.submittingOrder) return;
  const status=$("order-submit-status"),raw=$("order-price").value.trim(),route=TRANSPORTS[transport];
  const order={symbol:$("order-symbol").value,side:app.side,quantity:Number($("order-quantity").value),limit_price_x10000:raw?Math.round(Number(raw)*10000):0,transport};
  try{
    const reason=orderUnavailable(app.state,transport);if(reason) throw new Error(reason);
    if(!$("order-quantity").checkValidity()||!Number.isInteger(order.quantity)||order.quantity<1) throw new Error("请输入有效的整数股数");
    if(raw&&(!Number.isSafeInteger(order.limit_price_x10000)||order.limit_price_x10000<=0)) throw new Error("请输入大于 0 的有效限价");
    app.submittingOrder=true;renderOrderSubmit();if(app.state)renderTransportLab(app.state);
    status.className="order-submit-status pending";
    status.textContent=`正在提交${order.side==="BUY"?"买单":"卖单"} · ${order.symbol} ${order.quantity} 股 · ${route.label}…`;
    const result=await request("/api/order",{method:"POST",body:JSON.stringify(order)});
    app.pendingManualReceipt=result.client_order_id;
    saveManualOrder({...order,client_order_id:result.client_order_id,origin:"MANUAL_GUI",order_transport:route.wire,transport:route.label,state:"QUEUED",replay_loop:app.state?.replay?.loop||0});
    renderReceipt(app.state||{orders:[],replay:{loop:app.lastManualOrder.replay_loop}});
    status.className="order-submit-status";
    status.textContent=`已提交 #${result.client_order_id} · ${order.side==="BUY"?"买入":"卖出"} ${order.symbol} ${order.quantity} 股 · ${route.label}；成交结果见下方回执。`;
    toast(`订单 #${result.client_order_id} 已进入 ${route.label} 链路`);
  }catch(error){status.className="order-submit-status error";status.textContent=`提交失败：${error.message}`;toast(error.message,true);}
  finally{app.submittingOrder=false;renderOrderSubmit();if(app.state)renderTransportLab(app.state);}
}
$("submit-order").addEventListener("click",()=>submitOrder("SOCKET"));
document.querySelectorAll("[data-order-transport]").forEach(button=>button.addEventListener("click",()=>submitOrder(button.dataset.orderTransport)));
async function switchDataPlane(mode) {
  if(app.switchingPlane)return;
  app.switchingPlane={mode,started:Date.now()};app.planeError="";
  const timer=setInterval(()=>{if(app.state)renderTransportLab(app.state);},1000);
  if(app.state)renderTransportLab(app.state);
  try {
    await request("/api/data-plane",{method:"POST",body:JSON.stringify({mode})});
    toast(mode==="DPDK"?"X2522 已交给 DPDK":mode==="SFC"?"X2522 已交还 sfc":"普通交易配置已恢复");
  } catch(error) {
    app.planeError=`切换未完成：${error.message}`;toast(app.planeError,true);
  } finally {
    clearInterval(timer);app.switchingPlane=null;
    await refresh();
  }
}
$("x2522-mode-switch").addEventListener("click",async()=>{const mode=$("x2522-mode-switch").dataset.targetMode;if(app.switchingPlane||!["SFC","DPDK"].includes(mode))return;const warning=mode==="DPDK"?"切到 DPDK 会停止三条 sfc 客户端，并由 VFIO 暂时接管 X2522。继续吗？":"将切换到三路径测试配置，自动策略暂停。继续吗？";if(window.confirm(warning))await switchDataPlane(mode);});
$("strategy-toggle").addEventListener("click",async()=>{try{await request("/api/strategy",{method:"POST",body:JSON.stringify({enabled:!app.state.strategy.enabled})});await refresh();}catch(error){toast(error.message,true);}});
$("replay-toggle").addEventListener("click",async()=>{try{const action=app.state?.replay?.status==="PAUSED"?"RESUME":"PAUSE";await request("/api/replay",{method:"POST",body:JSON.stringify({action})});await refresh();}catch(error){toast(error.message,true);}});
$("replay-restart").addEventListener("click",async()=>{const button=$("replay-restart");button.disabled=true;try{toast("正在清空各通道交易并重新开始，请稍候");await request("/api/replay",{method:"POST",body:JSON.stringify({action:"RESTART",clear_trades:true})});clearManualOrder();await refresh();await refreshLanz();toast("已重新开始，交易、统计、图表和交换机队列事件已重置");}catch(error){toast(error.message,true);}finally{button.disabled=false;}});
$("replay-speed").addEventListener("change",async()=>{try{const speed=Number($("replay-speed").value);await request("/api/replay",{method:"POST",body:JSON.stringify({action:"SPEED",speed})});toast(`播放速度已设为 ${speed}×`);}catch(error){toast(error.message,true);}});

function lanzClock(event) {
  // Older readers mislabeled raw 10-us ticks as timestamp_us. Never guess.
  if(event.timestamp_tick_us!==10) return "时间单位未确认";
  const value=event.timestamp_us;
  if(!Number.isSafeInteger(value)||value<0) return "—";
  const date=new Date(Math.floor(value/1000));
  if(!Number.isFinite(date.getTime())) return "—";
  return date.toISOString().slice(0,19).replace("T"," ")+"."+String(value%1000000).padStart(6,"0");
}
function renderLanz(data) {
  const connected=Boolean(data&&data.connected);
  const events=data&&data.events||[];
  text("lanz-stream-status", connected ? "已连上 7150:50001" : events.length ? "当前未连接 · 以下为保留的历史记录" : "接收器未连接");
  $("lanz-stream-status").title=data&&data.error||"";
  $("lanz-stream-status").className = connected ? "lanz-ok" : "";
  text("lanz-segment-size", data&&data.config&&data.config.segment_size ? `${data.config.segment_size} B` : "—");
  text("lanz-history-summary",`显示采集器保留的全部 ${events.length} 条记录，最新在上。保留上限 80 条，更早记录不在此列表。`);
  const node=$("lanz-stream-rows");
  if(!node) return;
  const identity=JSON.stringify(events);
  if(node.dataset.records===identity) return;
  const scrollTop=node.scrollTop;
  node.replaceChildren();
  node.dataset.records=identity;
  if(!events.length){
    const empty=document.createElement("div");
    empty.className="lanz-empty";
    empty.textContent="还没有收到拥塞记录";
    node.appendChild(empty);
    return;
  }
  [...events].reverse().forEach(event=>{
    const row=document.createElement("div");
    const kind=event.entry_type||"—";
    row.className="lanz-row";
    const values=[kind==="START"?"S 开始":kind==="END"?"E 结束":kind==="UPDATE"?"U 更新":kind,
      event.intf_name??"—",event.traffic_class==null?"—":`TC${event.traffic_class}`,
      event.queue_size??"—",lanzClock(event)];
    values.forEach((value,index)=>{const cell=document.createElement("span");cell.textContent=value;if(index===0)cell.className=kind.toLowerCase();row.appendChild(cell);});
    node.appendChild(row);
  });
  node.scrollTop=scrollTop;
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

$("x2522-baseline").addEventListener("click",async()=>{if(app.switchingPlane||!window.confirm("停止路径测试，恢复普通交易与自动策略。继续吗？"))return;await switchDataPlane("BASELINE");});
