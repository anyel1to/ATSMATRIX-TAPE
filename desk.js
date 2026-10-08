const START = 10000;
const state = {
  price: 100,
  origin: 100,
  ticks: [],
  candles: [],
  bucket: 8,
  bidSz: 120,
  askSz: 100,
  cash: START,
  qty: 0,
  avg: 0,
  fills: [],
  regime: 0,
  regimeLeft: 24,
  mouse: null,
};

const canvas = document.querySelector("#chart");
const ctx = canvas.getContext("2d");
const els = {
  last: document.querySelector("#last"),
  chg: document.querySelector("#chg"),
  equity: document.querySelector("#equity"),
  cash: document.querySelector("#cash"),
  pos: document.querySelector("#pos"),
  avg: document.querySelector("#avg"),
  upnl: document.querySelector("#upnl"),
  bias: document.querySelector("#bias"),
  tip: document.querySelector("#tip"),
  fills: document.querySelector("#fills"),
  note: document.querySelector("#note"),
  ohlc: document.querySelector("#ohlc"),
  size: document.querySelector("#size"),
};

function money(n) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem("tape-paper") || "null");
    if (!saved) return;
    state.cash = Number(saved.cash) || START;
    state.qty = Number(saved.qty) || 0;
    state.avg = Number(saved.avg) || 0;
    state.fills = Array.isArray(saved.fills) ? saved.fills.slice(0, 12) : [];
  } catch {
    localStorage.removeItem("tape-paper");
  }
}

function save() {
  localStorage.setItem(
    "tape-paper",
    JSON.stringify({ cash: state.cash, qty: state.qty, avg: state.avg, fills: state.fills.slice(0, 12) }),
  );
}

function note(text) {
  els.note.textContent = text;
}

function size() {
  const n = Math.round(Number(els.size.value));
  return clamp(Number.isFinite(n) ? n : 1, 1, 100);
}

function stepMarket() {
  if (--state.regimeLeft <= 0) {
    state.regime = Math.floor(Math.random() * 3);
    state.regimeLeft = 28 + Math.floor(Math.random() * 24);
  }
  const pull = state.regime === 2 ? -0.08 * (state.price - 100) : 0;
  const drift = state.regime === 0 ? 0.03 : state.regime === 1 ? -0.028 : pull;
  state.price = clamp(state.price + drift + (Math.random() - 0.5) * 0.16, 94, 106);
  const imb = Math.tanh((Math.random() - 0.5) * 1.4 + (state.regime === 0 ? 0.3 : state.regime === 1 ? -0.3 : 0));
  const base = 80 + Math.random() * 80;
  state.bidSz = base * (1 + imb);
  state.askSz = base * (1 - imb);
  const side = Math.random() < 0.5 + imb * 0.2 ? 1 : -1;
  const qty = Math.random() < 0.25 ? 0 : 1 + Math.random() * 12;
  state.ticks.push({ mid: state.price, qty, side });
  if (state.ticks.length > 800) state.ticks.shift();
  rebuild();
}

function rebuild() {
  const bucket = state.bucket;
  const candles = [];
  for (let i = 0; i < state.ticks.length; i += bucket) {
    const slice = state.ticks.slice(i, i + bucket);
    candles.push({
      o: slice[0].mid,
      h: Math.max(...slice.map((t) => t.mid)),
      l: Math.min(...slice.map((t) => t.mid)),
      c: slice[slice.length - 1].mid,
      v: slice.reduce((sum, t) => sum + t.qty, 0),
    });
  }
  state.candles = candles;
}

function signal() {
  const mids = state.ticks.map((t) => t.mid);
  const i = mids.length - 1;
  const past = (k) => mids[Math.max(0, i - k)];
  const imb = (state.bidSz - state.askSz) / Math.max(1, state.bidSz + state.askSz);
  const ret8 = (state.price - past(8)) / past(8);
  const ret24 = (state.price - past(24)) / past(24);
  let vol = 0;
  const window = Math.min(12, i);
  for (let k = 1; k <= window; k += 1) vol += Math.abs((mids[i - k + 1] - mids[i - k]) / mids[i - k]);
  if (window) vol /= window;
  const score = clamp(1.6 * imb + 90 * ret8 + 46 * ret24, -3, 3);
  const confidence = Math.tanh(Math.abs(score));
  let regime = "revert";
  if (vol < 0.00055 && Math.abs(ret24) < 0.0012) regime = "chop";
  else if (ret8 * ret24 > 0 && Math.abs(ret24) > 0.0016) regime = "trend";
  const bias = score > 0.05 ? "Bid" : score < -0.05 ? "Ask" : "Flat";
  return { regime, bias, confidence, score };
}

function tip(sig) {
  const pct = Math.round(sig.confidence * 100);
  if (sig.regime === "chop") {
    return `Range is tight and confidence is ${pct}%. The desk would stay flat. This is the simulated tape, not a forecast.`;
  }
  if (sig.regime === "trend" && sig.bias === "Bid") {
    return `Fast and slow returns agree to the upside. Paper bias is bid at ${pct}% confidence. Not a recommendation.`;
  }
  if (sig.regime === "trend" && sig.bias === "Ask") {
    return `Fast and slow returns agree to the downside. Paper bias is ask at ${pct}% confidence. Not a recommendation.`;
  }
  if (sig.bias === "Flat") {
    return `Score is near zero. No paper bias until confidence clears the line.`;
  }
  return `Momentum and the book disagree. Confidence ${pct}%. A fade is a description of this tape, not advice.`;
}

function buy() {
  const n = size();
  const cost = state.price * n;
  if (state.cash + 1e-6 < cost) {
    note("Not enough paper cash.");
    return;
  }
  state.avg = state.qty === 0 ? state.price : (state.avg * state.qty + state.price * n) / (state.qty + n);
  state.qty += n;
  state.cash -= cost;
  state.fills.unshift({ side: "Buy", n, price: state.price });
  note(`Bought ${n} at ${state.price.toFixed(2)}.`);
  save();
  paintAccount();
}

function sell() {
  const n = size();
  if (state.qty < n) {
    note("Not enough paper size.");
    return;
  }
  state.qty -= n;
  state.cash += state.price * n;
  if (state.qty === 0) state.avg = 0;
  state.fills.unshift({ side: "Sell", n, price: state.price });
  note(`Sold ${n} at ${state.price.toFixed(2)}.`);
  save();
  paintAccount();
}

function reset() {
  state.cash = START;
  state.qty = 0;
  state.avg = 0;
  state.fills = [];
  note("Paper account reset.");
  save();
  paintAccount();
}

function paintAccount() {
  const equity = state.cash + state.qty * state.price;
  const open = state.qty ? (state.price - state.avg) * state.qty : 0;
  const chg = ((state.price - state.origin) / state.origin) * 100;
  els.last.textContent = state.price.toFixed(2);
  els.chg.textContent = `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%`;
  els.chg.className = chg >= 0 ? "up" : "down";
  els.equity.textContent = money(equity);
  els.cash.textContent = money(state.cash);
  els.pos.textContent = String(state.qty);
  els.avg.textContent = state.qty ? state.avg.toFixed(2) : "—";
  els.upnl.textContent = `${open >= 0 ? "+" : ""}${money(open)}`;
  els.upnl.className = open >= 0 ? "up" : "down";
  const sig = state.ticks.length > 4 ? signal() : { regime: "chop", bias: "Flat", confidence: 0, score: 0 };
  els.bias.textContent = `${sig.regime.toUpperCase()} · ${sig.bias} · ${Math.round(sig.confidence * 100)}%`;
  els.tip.textContent = state.ticks.length > 4 ? tip(sig) : "The tape needs a few prints before the desk will talk.";
  els.fills.innerHTML = state.fills
    .slice(0, 8)
    .map((fill) => `<li><span class="${fill.side === "Buy" ? "up" : "down"}">${fill.side} ${fill.n}</span><span>${fill.price.toFixed(2)}</span></li>`)
    .join("");
}

function resize() {
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

function draw() {
  const rect = canvas.parentElement.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0c0f14";
  ctx.fillRect(0, 0, w, h);
  const pad = { l: 8, r: 64, t: 28, b: 28 };
  const plotW = w - pad.l - pad.r;
  const volH = 56;
  const plotH = h - pad.t - pad.b - volH;
  const view = state.candles.slice(-70);
  if (!view.length) return;
  let lo = Math.min(...view.map((c) => c.l));
  let hi = Math.max(...view.map((c) => c.h));
  const span = Math.max(0.2, (hi - lo) * 1.18);
  const mid = (hi + lo) / 2;
  lo = mid - span / 2;
  hi = mid + span / 2;
  const xAt = (i) => pad.l + (i + 0.5) * (plotW / view.length);
  const yAt = (p) => pad.t + ((hi - p) / (hi - lo)) * plotH;

  ctx.strokeStyle = "#1c2430";
  ctx.lineWidth = 1;
  ctx.font = "11px ui-monospace, monospace";
  ctx.fillStyle = "#8b95a7";
  for (let g = 0; g < 5; g += 1) {
    const p = lo + ((hi - lo) * g) / 4;
    const y = yAt(p);
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(w - pad.r, y);
    ctx.stroke();
    ctx.fillText(p.toFixed(2), w - pad.r + 6, y + 4);
  }

  const maxV = Math.max(1, ...view.map((c) => c.v));
  view.forEach((candle, i) => {
    const x = xAt(i);
    const up = candle.c >= candle.o;
    ctx.strokeStyle = up ? "#26a69a" : "#ef5350";
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath();
    ctx.moveTo(x, yAt(candle.h));
    ctx.lineTo(x, yAt(candle.l));
    ctx.stroke();
    const top = yAt(Math.max(candle.o, candle.c));
    const bot = yAt(Math.min(candle.o, candle.c));
    const bw = Math.max(3, plotW / view.length - 3);
    ctx.fillRect(x - bw / 2, top, bw, Math.max(1, bot - top));
    const vh = (candle.v / maxV) * (volH - 8);
    ctx.globalAlpha = 0.85;
    ctx.fillRect(x - bw / 2, h - pad.b - vh, bw, vh);
    ctx.globalAlpha = 1;
  });

  if (view.length >= 8) {
    ctx.beginPath();
    ctx.strokeStyle = "#d6b25e";
    ctx.lineWidth = 1.4;
    view.forEach((candle, i) => {
      const from = Math.max(0, i - 7);
      const slice = view.slice(from, i + 1);
      const ma = slice.reduce((sum, c) => sum + c.c, 0) / slice.length;
      const x = xAt(i);
      const y = yAt(ma);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  const last = view[view.length - 1].c;
  ctx.strokeStyle = "#d5dbe3";
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(pad.l, yAt(last));
  ctx.lineTo(w - pad.r, yAt(last));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = last >= view[view.length - 1].o ? "#26a69a" : "#ef5350";
  ctx.fillRect(w - pad.r, yAt(last) - 9, 58, 18);
  ctx.fillStyle = "#04120f";
  ctx.fillText(last.toFixed(2), w - pad.r + 6, yAt(last) + 4);

  if (state.qty > 0) {
    ctx.strokeStyle = "#2962ff";
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.l, yAt(state.avg));
    ctx.lineTo(w - pad.r, yAt(state.avg));
    ctx.stroke();
    ctx.setLineDash([]);
  }

  if (state.mouse) {
    const i = clamp(Math.round((state.mouse.x - pad.l) / (plotW / view.length) - 0.5), 0, view.length - 1);
    const candle = view[i];
    const x = xAt(i);
    ctx.strokeStyle = "#8b95a7";
    ctx.beginPath();
    ctx.moveTo(x, pad.t);
    ctx.lineTo(x, h - pad.b);
    ctx.moveTo(pad.l, state.mouse.y);
    ctx.lineTo(w - pad.r, state.mouse.y);
    ctx.stroke();
    els.ohlc.textContent = `O ${candle.o.toFixed(2)}  H ${candle.h.toFixed(2)}  L ${candle.l.toFixed(2)}  C ${candle.c.toFixed(2)}`;
  }
}

document.querySelector("#buy").addEventListener("click", buy);
document.querySelector("#sell").addEventListener("click", sell);
document.querySelector("#reset").addEventListener("click", reset);
document.querySelectorAll(".intervals button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".intervals button").forEach((item) => item.classList.remove("on"));
    button.classList.add("on");
    state.bucket = Number(button.dataset.bucket);
    rebuild();
    draw();
  });
});
canvas.addEventListener("mousemove", (event) => {
  const rect = canvas.getBoundingClientRect();
  state.mouse = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  draw();
});
canvas.addEventListener("mouseleave", () => {
  state.mouse = null;
  els.ohlc.textContent = "Paper mode. Not a live market.";
  draw();
});
window.addEventListener("resize", resize);
new ResizeObserver(resize).observe(canvas.parentElement);

load();
for (let i = 0; i < 48; i += 1) stepMarket();
paintAccount();
resize();
setInterval(() => {
  stepMarket();
  paintAccount();
  draw();
}, 600);
