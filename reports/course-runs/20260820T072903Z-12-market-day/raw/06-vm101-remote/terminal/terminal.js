"use strict";

const model = {
  events: [],
  liveIds: new Set(),
  tickPoints: [],
  feedA: 0,
  feedB: 0,
  duplicate: 0,
  state: null,
  stream: null,
};

const byId = (id) => document.getElementById(id);
const text = (id, value) => { byId(id).textContent = value ?? "—"; };
const field = (event, name) => event.fields && event.fields[name] !== undefined ? event.fields[name] : undefined;

function formatNs(value) {
  if (value === undefined || value === null || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  if (number >= 1e6) return `${(number / 1e6).toFixed(3)} ms`;
  if (number >= 1e3) return `${(number / 1e3).toFixed(3)} µs`;
  return `${number.toLocaleString()} ns`;
}

function toast(message, error = false) {
  const node = byId("toast");
  node.textContent = message;
  node.className = error ? "show error" : "show";
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => { node.className = ""; }, 2800);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function sendCommand(action, values = {}) {
  try {
    const data = await api("/api/v1/commands", {
      method: "POST",
      body: JSON.stringify({ action, origin: "ui", ...values }),
    });
    const disposition = data.command.disposition || data.status;
    toast(`${data.command.action} ${disposition} · ${data.command.command_id}`);
    await refreshState();
  } catch (error) {
    toast(error.message, true);
  }
}

function setObserved(name) {
  const node = byId(`node-${name}`);
  const dot = byId(`health-${name}`);
  const label = byId(`health-${name}-text`);
  node.classList.add("observed");
  node.querySelector("span").textContent = "EVENT OBSERVED";
  dot.className = "ok";
  label.textContent = "OBSERVED";
}

function markLifecycle(id, value) {
  const node = byId(id);
  node.classList.add("seen");
  node.querySelector("b").textContent = value;
}

function updateFromEvent(event) {
  const f = event.fields || {};
  const role = String(f.role || "");
  if (role.includes("exchange") || event.source.includes("exchange") || ["tick_tx", "order_rx", "response_tx", "order_apply", "order_replay"].includes(event.kind)) setObserved("exchange");
  if (role.includes("trader") || event.source.includes("trader") || ["tick_rx", "tick_accept", "order_tx", "response_rx", "duplicate_drop"].includes(event.kind)) setObserved("trader");

  if (f.feed === "A") model.feedA += 1;
  if (f.feed === "B") model.feedB += 1;
  if (event.kind === "duplicate_drop") model.duplicate += 1;
  if (f.duplicate !== undefined) model.duplicate = Number(f.duplicate);
  text("feed-a", model.feedA);
  text("feed-b", model.feedB);
  text("duplicates", model.duplicate);

  if (f.sequence !== undefined) {
    text("last-sequence", f.sequence);
    model.tickPoints.push(Number(f.sequence));
    model.tickPoints = model.tickPoints.slice(-80);
    drawChart();
  }
  if (f.gap_remaining !== undefined) text("gap", f.gap_remaining);
  if (f.tick_window_ns !== undefined) text("tick-window", formatNs(f.tick_window_ns));
  if (f.correlation !== undefined) text("correlation", f.correlation);

  if (event.kind === "order_tx" || event.kind === "order_rx" || event.kind === "order_apply" || event.kind === "order_replay") markLifecycle("life-order", event.kind.toUpperCase());
  if (event.kind === "response_tx" && String(f.types || "").includes("ACK")) markLifecycle("life-ack", "OBSERVED");
  if (event.kind === "response_tx" && String(f.types || "").includes("EXECUTION")) markLifecycle("life-execution", "OBSERVED");
  if (event.kind === "response_rx" && String(f.value || "").startsWith("ACK|")) markLifecycle("life-ack", "OBSERVED");
  if (event.kind === "response_rx" && String(f.value || "").startsWith("EXECUTION|")) markLifecycle("life-execution", "OBSERVED");
  if (event.kind === "response_rx" && f.response_type === "ACK") markLifecycle("life-ack", f.replay ? "REPLAYED ACK" : "ACKNOWLEDGED");
  if (event.kind === "response_rx" && f.response_type === "EXECUTION") markLifecycle("life-execution", f.replay ? "REPLAYED EXECUTION" : "FILLED");
  if (event.kind === "execution_delivery") markLifecycle("life-execution", String(f.result || "OBSERVED"));

  if (f.price_x10000 !== undefined) {
    text("market-price", (Number(f.price_x10000) / 10000).toFixed(4));
    text("price-source", "CURRENT-RUN price_x10000");
  } else if (f.price !== undefined) {
    text("market-price", f.price);
    text("price-source", "CURRENT-RUN PRICE EVENT");
  }

  [["p50", "p50_ns"], ["p99", "p99_ns"], ["p999", "p999_ns"], ["ptp-offset", "offset_ns"]].forEach(([id, key]) => {
    if (f[key] !== undefined) text(id, formatNs(f[key]));
  });
  if (f.clock_domain !== undefined) text("clock-domain", f.clock_domain);
  if (f.trex_tx_packets !== undefined) text("trex-tx", f.trex_tx_packets);
  if (f.nic_rx_packets !== undefined) text("nic-rx", f.nic_rx_packets);
  if (f.lanz_events !== undefined) {
    text("lanz-events", f.lanz_events);
    text("pressure-note", "Current-run LANZ event fields received.");
  }
  if (f.max_queue_segments !== undefined) text("max-queue", `${f.max_queue_segments} segments`);

  if (event.kind === "command_accepted") {
    const command = f;
    if (command.mode) text("mode", command.mode.toUpperCase());
    if (command.phase) text("phase", command.phase);
  }
  text("last-update", `LAST UPDATE ${event.ingested_at}`);
}

function addEvent(event, initial = false) {
  const key = `${event.delivery}:${event.event_id}`;
  if (event.delivery === "live" && model.liveIds.has(event.event_id)) return;
  if (event.delivery === "live") model.liveIds.add(event.event_id);
  if (!model.events.some((item) => `${item.delivery}:${item.event_id}` === key)) {
    model.events.push(event);
    model.events = model.events.slice(-300);
  }
  updateFromEvent(event);
  renderTape();
  if (!initial && event.delivery === "replay") toast(`Replay event ${event.event_id}`);
}

function renderTape() {
  const tape = byId("event-tape");
  const fragment = document.createDocumentFragment();
  model.events.slice(-120).reverse().forEach((event) => {
    const row = document.createElement("div");
    row.className = `event-row ${event.delivery === "replay" ? "replay" : ""}`;
    const sequence = document.createElement("span");
    sequence.textContent = `#${event.sequence} ${event.ingested_at.slice(11, 23)}`;
    const source = document.createElement("span");
    source.textContent = `${event.source} / ${event.phase}`;
    const kind = document.createElement("span");
    kind.textContent = `${event.delivery === "replay" ? "↻ " : ""}${event.kind}`;
    const raw = document.createElement("code");
    raw.textContent = event.raw_line || JSON.stringify(event.fields);
    row.append(sequence, source, kind, raw);
    fragment.appendChild(row);
  });
  tape.replaceChildren(fragment);
  text("event-count", model.state ? model.state.last_sequence : model.liveIds.size);
}

function drawChart() {
  const canvas = byId("tape-chart");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#172a34";
  ctx.lineWidth = 1;
  for (let y = 20; y < height; y += 40) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
  }
  if (model.tickPoints.length < 2) {
    ctx.fillStyle = "#526a77";
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillText("AWAITING CURRENT-RUN TICK EVENTS", 16, height / 2);
    return;
  }
  const points = model.tickPoints;
  const min = Math.min(...points);
  const max = Math.max(...points);
  ctx.strokeStyle = "#32d6ff";
  ctx.shadowColor = "#32d6ff";
  ctx.shadowBlur = 8;
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((value, index) => {
    const x = (index / (points.length - 1)) * width;
    const y = height - 18 - ((value - min) / Math.max(1, max - min)) * (height - 36);
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.shadowBlur = 0;
}

function applyState(state) {
  model.state = state;
  text("run-id", state.run_id);
  text("mode", state.mode.toUpperCase());
  text("phase", state.phase);
  text("event-count", state.last_sequence);
  text("coupling", `DATA PLANE: ${state.data_plane_coupling.replaceAll("_", " ")}`);
  document.querySelectorAll("[data-mode]").forEach((button) => button.classList.toggle("selected", button.dataset.mode === state.mode));
  document.querySelectorAll("[data-phase]").forEach((button) => button.classList.toggle("selected", button.dataset.phase === state.phase));
}

async function refreshState() {
  const state = await api("/api/v1/state");
  applyState(state);
}

function connectStream(after) {
  if (model.stream) model.stream.close();
  const stream = new EventSource(`/api/v1/events/stream?after=${after}`);
  model.stream = stream;
  stream.onopen = () => {
    byId("stream-dot").className = "ok";
    text("stream-status", "LIVE SSE");
    byId("health-stream").className = "ok";
    text("health-stream-text", "CONNECTED");
  };
  stream.addEventListener("market", (message) => addEvent(JSON.parse(message.data)));
  stream.onerror = () => {
    byId("stream-dot").className = "bad";
    text("stream-status", "RECONNECTING");
    byId("health-stream").className = "bad";
    text("health-stream-text", "RECONNECTING");
  };
}

async function boot() {
  try {
    const state = await api("/api/v1/state");
    applyState(state);
    const history = await api(`/api/v1/events?limit=300&after=0`);
    history.events.forEach((event) => addEvent(event, true));
    drawChart();
    connectStream(state.last_sequence);
  } catch (error) {
    toast(error.message, true);
    byId("stream-dot").className = "bad";
    text("stream-status", "OFFLINE");
  }
}

document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => sendCommand("set_mode", { mode: button.dataset.mode })));
document.querySelectorAll("[data-phase]").forEach((button) => button.addEventListener("click", () => sendCommand("set_phase", { phase: button.dataset.phase })));
byId("replay-button").addEventListener("click", () => sendCommand("replay", { limit: 250, interval_ms: 20 }));
byId("order-form").addEventListener("submit", (event) => {
  event.preventDefault();
  sendCommand("submit_order", {
    symbol: "AAPL",
    side: byId("order-side").value,
    quantity: Number(byId("order-quantity").value),
  });
});
window.addEventListener("beforeunload", () => { if (model.stream) model.stream.close(); });
boot();
