/* Run with node tests/test_transport_ui.js; no browser or live device required. */
async function runTransportSwitchTests(source) {
  function assert(value, message) { if (!value) throw new Error(message); }
  const nodes = new Map();
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, {
      dataset:{}, classList:{toggle(){}},
      querySelector(){return get(id + '-submit');},
    });
    return nodes.get(id);
  };
  const app = {state:null, switchingPlane:null, planeError:""};
  const routes = {DPDK:{component:'trader_dpdk',key:'dpdk',mode:'DPDK'}};
  let resolveRequest, rejectRequest, requests=0, timer, after;
  const request = () => {
    requests++;
    return new Promise((resolve,reject) => {resolveRequest=resolve;rejectRequest=reject;});
  };
  const render = source.slice(source.indexOf('function renderTransportLab('),
                              source.indexOf('\nfunction render(state)'));
  const change = source.slice(source.indexOf('async function switchDataPlane('),
                              source.indexOf('\n$("x2522-mode-switch").addEventListener'));
  let api;
  api = new Function('app','$','text','TRANSPORTS','duration','orderUnavailable',
                    'request','toast','refresh','setInterval','clearInterval',
                    render + '\n' + change + '\nreturn {renderTransportLab,switchDataPlane};')(
    app,get,(id,value)=>{get(id).textContent=value;},routes,()=>'',()=>false,
    request,()=>{},async()=>{app.state=after;api.renderTransportLab(after);},
    callback=>{timer=callback;return 1;},()=>{timer=null;});
  const dpdk = {features:{transport_lab:true}, data_plane_mode:'DPDK',
                data_plane_transition:'READY',experiment_profile:'TRANSPORT',
                health:{trader_dpdk:{status:'ONLINE'}}};
  const sfc = {...dpdk,data_plane_mode:'SFC'};
  app.state=dpdk;after=sfc;
  api.renderTransportLab(dpdk);
  const pending = api.switchDataPlane('SFC');
  // A stale READY poll must not re-enable switching or order submission.
  api.renderTransportLab(dpdk);
  assert(get('x2522-mode-switch').disabled,'stale READY unlocked switch');
  assert(get('x2522-baseline').disabled,'stale READY unlocked baseline');
  assert(get('transport-card-dpdk-submit').disabled,'stale READY unlocked orders');
  app.switchingPlane.started-=3000;timer();
  assert(get('x2522-transition').textContent.includes('3 秒'),'elapsed time missing');
  await api.switchDataPlane('DPDK');
  assert(requests===1,'duplicate operation submitted');
  resolveRequest({});await pending;
  assert(!timer && !app.switchingPlane,'pending operation not cleared');
  assert(!get('x2522-mode-switch').disabled,'verified SFC remained disabled');
  assert(get('x2522-mode-switch').dataset.targetMode==='DPDK','wrong return target');
  const failure=api.switchDataPlane('DPDK');
  rejectRequest(new Error('device restore failed'));await failure;
  assert(get('x2522-transition').textContent.includes('device restore failed'),
         'failure disappeared after refresh');
  api.renderTransportLab({...sfc,data_plane_transition:'DEGRADED'});
  assert(get('x2522-mode-switch').disabled,'unverified state enabled switching');
  return 'PASS: pending lock, elapsed display, duplicate rejection, success, error, degraded gate';
}

if (typeof module !== 'undefined' && require.main === module) {
  const fs=require('fs'), path=require('path');
  runTransportSwitchTests(fs.readFileSync(path.join(__dirname,'../web/terminal.js'),'utf8'))
    .then(message=>console.log(message)).catch(error=>{console.error(error);process.exitCode=1;});
}
