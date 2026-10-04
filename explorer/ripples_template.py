"""Belief ripples page template (vis-network). Filled by app.py and by ripples_export.py.

Placeholders: __DATA__ (belief-graph JSON), __DRIFT__ ({agents:{...}} stance timelines or {}),
__MOMENTS__ (list of {at,label,row,color,lane}), __H__ (graph height in px).
"""

BELIEF_HTML = r"""
<div id="wrap" style="display:flex;gap:14px;font-family:Inter,system-ui,sans-serif;color:#e8e8ea">
 <div style="flex:1;min-width:0">
  <div id="hud" style="display:flex;align-items:flex-start;gap:14px;margin:0 0 4px 4px">
   <button id="play" style="background:#ff5c6c;color:#fff;border:0;border-radius:6px;padding:8px 16px;font-size:15px;cursor:pointer;flex:none">▶ play</button>
   <div style="flex:1;min-width:160px">
    <input id="t" type="range" min="0" max="1000" value="1000" style="width:100%;margin:8px 0 2px 0">
    <div id="moments" style="position:relative;height:62px"></div>
   </div>
  </div>
  <div id="clock" style="font-size:15px;font-weight:600;margin:0 0 6px 4px"></div>
  <div id="net" style="height:__H__px;border-radius:10px;background:radial-gradient(circle at 50% 50%,#1b1d26 0%,#0e1117 70%)"></div>
  <div style="font-size:12.5px;color:#a9adb8;margin:6px 4px;line-height:1.6">
   Rings = time since the start (log): 1 min · 1 h · 1 day · 1 week. <b>Agents</b> are split circles:
   top = what it <b>said</b> <span id="stlegend"></span>, bottom = what it <b>did</b> (<span style="color:#f2a541">●</span> acted,
   <span style="color:#3ddc97">●</span> checked &amp; held, <span style="color:#ff5c6c">✕</span> checked &amp; failed).
   <b>Claims</b> are diamonds: <span style="color:#3ddc97">◆</span> screen backs it · <span style="color:#ff5c6c">◆ cracked</span>
   screen contradicts it · <span style="color:#d9dbe1">◇</span> not checked. Dots = links/files touched.
   Lines: <span style="color:#ff5c6c">red</span> told · <span style="color:#8a8f9c">grey</span> said/did · <span style="color:#3ddc97">green</span>/<span style="color:#ff5c6c">red</span> checked.
  </div>
 </div>
 <div id="side" style="width:290px;flex:none;background:#161922;border-radius:10px;padding:14px;font-size:13.5px;line-height:1.45;height:__H__px;overflow:auto">
  <div style="font-weight:700;font-size:15px;margin-bottom:6px">Evidence</div>
  <div id="info" style="color:#c9ccd4">Click anything to see what was said, what was done, and the dataset rows behind it.</div>
 </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/vis-network@9/standalone/umd/vis-network.min.js"></script>
<script>
const G = __DATA__;
const MOMENTS = __MOMENTS__;               // verified key moments (row ids) for this seed, shown under the slider
const D = (__DRIFT__).agents || {};      // claim drift per agent: a timeline of stances (first text + 72 h of chat)
const PRI = {neutral: 0, hedges: 1, repeats: 2, checks: 3, flags: 4, amplifies: 5, original: 6};
Object.values(D).forEach(d => { if (!d.timeline) d.timeline = [{at: d.at, stance: d.stance, gist: d.gist, cue: d.cue, row: d.row, src: "first text"}]; });
function stanceAt(id) {                  // most escalated stance among this agent's labelled texts up to NOW
  const d = D[id]; if (!d) return null; let best = null;
  d.timeline.forEach(e => { if (mins(e.at) <= NOW && (!best || PRI[e.stance] > PRI[best.stance])) best = e; });
  return best;
}
const STANCE = {original: ["#b28dff", "the original claim"], repeats: ["#ff5c6c", "repeated it"], amplifies: ["#ff2fb4", "pushed it further (more certain, published or promoted)"],
  hedges: ["#f2c14e", "passed it on with caution"], checks: ["#2ec4b6", "checked it itself"], flags: ["#4ea8ff", "flagged it as wrong"],
  neutral: ["#5b6070", "only touched the link"]};
const P = iso => Date.parse(iso.endsWith("Z") ? iso : iso + "Z");
const T0 = P(G.t0), mins = iso => (P(iso) - T0) / 60000;
const RMAX = 10080, rad = m => 80 + 330 * Math.log10(1 + Math.max(m, 0)) / Math.log10(1 + RMAX);
const fmt = m => m < 1 ? "<1 min" : m < 60 ? Math.round(m) + " min" : m < 2880 ? (m / 60).toFixed(1) + " h" : (m / 1440).toFixed(1) + " days";
const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
const centerId = G.seed.kind === "agent" ? "agent:" + G.seed.value : "artifact:" + G.seed.value;
const byId = Object.fromEntries(G.nodes.map(n => [n.id, n]));
const isClaim = n => n.kind === "artifact" && /^Claim /.test(n.label || "");
// per-node timelines
const st = {};
G.nodes.forEach(n => st[n.id] = {said: Infinity, did: Infinity, ok: Infinity, bad: Infinity, first: mins(n.first_at), edges: []});
G.edges.forEach(e => {
  const m = mins(e.at), s = st[e.source], t = st[e.target];
  if (s) s.edges.push(e); if (t && e.target !== e.source) t.edges.push(e);
  if (!s) return;
  if (e.kind === "said") s.said = Math.min(s.said, m);
  if (e.kind === "did") s.did = Math.min(s.did, m);
  if (e.kind === "checked") {
    const tgt = st[e.target];
    if (e.status === "supported") { s.ok = Math.min(s.ok, m); if (tgt) tgt.ok = Math.min(tgt.ok, m); }
    // a verifier run that errored is a run signal, not evidence the claim is false: keep it out of 'contradicted'
    if (e.status === "contradicted" && e.basis === "verifier") s.err = Math.min(s.err ?? Infinity, m);
    else if (e.status === "contradicted") { s.bad = Math.min(s.bad, m); if (tgt) tgt.bad = Math.min(tgt.bad, m); }
  }
});
// layout: centre fixed, others on log-time rings by first appearance, golden angle, agents first
const others = G.nodes.filter(n => n.id !== centerId).sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "agent" ? -1 : 1) || st[a.id].first - st[b.id].first);
const pos = {[centerId]: {x: 0, y: 0}};
others.forEach((n, i) => { const ang = i * 2.39996 + (n.kind === "agent" ? 0 : 0.6); const r = rad(st[n.id].first); pos[n.id] = {x: r * Math.cos(ang), y: r * Math.sin(ang)}; });
const ALL = 1e12; let NOW = ALL;           // 'all time' must stay finite: Infinity <= Infinity is true
const on = m => m <= NOW;
function agentColors(id) {
  const s = st[id], touched = on(s.said) || on(s.did) || on(s.ok) || on(s.bad);
  const sa = stanceAt(id), top = !touched && !sa ? "#3a3f4b" : D[id] ? STANCE[(sa || {stance: "neutral"}).stance]?.[0] || "#ff5c6c" : "#ff5c6c";
  let bot = "#3a3f4b", crack = false;
  if (on(s.did)) bot = "#f2a541";
  if (on(s.ok)) bot = "#3ddc97";
  if (on(s.bad) && !on(s.ok)) { bot = "#ff5c6c"; crack = true; }
  if (on(s.bad) && on(s.ok)) crack = true;   // has both a held-up and a failed check: green with a crack
  return {top, bot, crack, lit: top !== "#3a3f4b" || bot !== "#3a3f4b" || on(s.first)};
}
const short = l => (l || "").replace("Claude ", "");
function agentRenderer({ctx, id, x, y, state: {selected, hover}, label}) {
  return {drawNode() {
    const c = agentColors(id), big = id === centerId, R0 = big ? 24 : 15, r = selected || hover ? R0 + 3 : R0;
    ctx.save(); ctx.globalAlpha = c.lit ? 1 : 0.35;
    ctx.beginPath(); ctx.arc(x, y, r, Math.PI, 0); ctx.closePath(); ctx.fillStyle = c.top; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI); ctx.closePath(); ctx.fillStyle = c.bot; ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - r, y); ctx.lineTo(x + r, y); ctx.strokeStyle = "#0e1117"; ctx.lineWidth = 2; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.strokeStyle = selected || big ? "#ffffff" : "rgba(255,255,255,0.55)"; ctx.lineWidth = selected || big ? 2.5 : 1; ctx.stroke();
    if (c.crack) { ctx.beginPath(); ctx.moveTo(x - r * .4, y + 3); ctx.lineTo(x - r * .05, y + r * .6); ctx.lineTo(x + r * .2, y + r * .25); ctx.lineTo(x + r * .45, y + r * .75); ctx.strokeStyle = "#0e1117"; ctx.lineWidth = 2; ctx.stroke(); }
    // crowded graphs (> 40 agents): names only for the centre, hovered and selected nodes
    if (big || selected || hover || G.nodes.filter(n => n.kind === "agent").length <= 40) {
      ctx.fillStyle = "#e8e8ea"; ctx.font = (big ? "bold 15px" : "13px") + " Inter, sans-serif"; ctx.textAlign = "center";
      ctx.fillText(label, x, y + r + 15);
    }
    ctx.restore();
  }, nodeDimensions: {width: 2 * R, height: 2 * R}};
}
const R = 15;
function claimRenderer({ctx, id, x, y, state: {selected, hover}}) {
  const s = st[id], big = id === centerId, r = (big ? 22 : 11) + (selected || hover ? 3 : 0);
  return {drawNode() {
    const col = on(s.bad) ? "#ff5c6c" : on(s.ok) ? "#3ddc97" : "#d9dbe1";
    ctx.save(); ctx.globalAlpha = on(s.first) ? 1 : 0.3;
    ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
    ctx.fillStyle = col; ctx.fill(); ctx.strokeStyle = selected ? "#ffffff" : "#0e1117"; ctx.lineWidth = selected ? 2.5 : 1.5; ctx.stroke();
    if (on(s.bad)) { ctx.beginPath(); ctx.moveTo(x - r * .5, y - r * .2); ctx.lineTo(x - r * .1, y + r * .25); ctx.lineTo(x + r * .15, y - r * .1); ctx.lineTo(x + r * .5, y + r * .35); ctx.strokeStyle = "#0e1117"; ctx.lineWidth = 2; ctx.stroke(); }
    if (big || selected || hover) { ctx.fillStyle = "#e8e8ea"; ctx.font = (big ? "bold 14px" : "11px") + " Inter, sans-serif"; ctx.textAlign = "center"; ctx.fillText(big ? "the claim" : "claim", x, y + r + 14); }
    ctx.restore();
  }, nodeDimensions: {width: 2 * r, height: 2 * r}};
}
const visNodes = G.nodes.map(n => {
  const base = {id: n.id, fixed: true, x: pos[n.id].x, y: pos[n.id].y};
  if (n.kind === "agent") return {...base, label: short(n.label), shape: "custom", ctxRenderer: agentRenderer};
  if (isClaim(n)) return {...base, shape: "custom", ctxRenderer: claimRenderer};
  if (n.id === centerId) return {...base, label: G.seed.kind === "url" ? (String(G.seed.value).startsWith("technique:") ? "the technique" : "the link") : "artifact", shape: "star", size: 26, color: {background: "#b28dff", border: "#ffffff"}, font: {color: "#e8e8ea", size: 14, vadjust: -6}};
  return {...base, shape: "dot", size: 4, color: {background: "#8a8f9c", border: "#8a8f9c"}, title: n.label};
});
const nodes = new vis.DataSet(visNodes);
// edges: one best incoming 'told' per agent; said/did/checked edges only between drawn nodes; in big graphs drop said/did to links
const rankEv = {explicit: 0, seen: 0, temporal: 1, mention: 2}, bestIn = {};
G.edges.filter(e => e.kind === "told" && st[e.source] && st[e.target] && e.source !== e.target).forEach(e => {
  const k = e.target + "|" + (e.artifact || ""), b = bestIn[k];
  if (!b || rankEv[e.evidence] < rankEv[b.evidence] || (rankEv[e.evidence] === rankEv[b.evidence] && e.at < b.at)) bestIn[k] = e;
});
const told = Object.values(bestIn);
const sayDo = G.edges.filter(e => (e.kind === "said" || e.kind === "did") && st[e.source] && st[e.target] && (isClaim(byId[e.target]) || G.nodes.length <= 40 || e.target === centerId));
const checks = G.edges.filter(e => e.kind === "checked" && st[e.source] && st[e.target]);
const drawn = [].concat(
  told.map(e => ({id: e.id, from: e.source, to: e.target, kind: "told", at: e.at, arrows: {to: {enabled: true, scaleFactor: 0.5}}, width: (e.evidence === "explicit" || e.evidence === "seen") ? 2.6 : 0.9, dashes: e.evidence === "mention", color: {color: "rgba(255,92,108,0.6)", highlight: "#ffffff"}, smooth: {type: "curvedCW", roundness: 0.15}})),
  sayDo.map(e => ({id: e.id, from: e.source, to: e.target, kind: e.kind, at: e.at, width: 0.6, color: {color: "rgba(138,143,156,0.35)", highlight: "#ffffff"}, smooth: false})),
  checks.map(e => ({id: e.id, from: e.source, to: e.target, kind: "checked", at: e.at, width: 2.4, color: {color: e.status === "contradicted" ? "#ff5c6c" : e.status === "supported" ? "#3ddc97" : "rgba(217,219,225,0.5)", highlight: "#ffffff"}, dashes: e.status === "unknown", smooth: false})));
const edges = new vis.DataSet(drawn);
// Fit graph + evidence panel to the viewer's window (the iframe itself has a fixed height).
try { const h = Math.max(420, Math.min(__H__, window.parent.innerHeight - 240));
      ["net", "side"].forEach(id => document.getElementById(id).style.height = h + "px"); } catch (e) {}
const net = new vis.Network(document.getElementById("net"), {nodes, edges}, {physics: false, interaction: {hover: true, zoomView: true, tooltipDelay: 80}});
net.on("beforeDrawing", ctx => {
  [[1, "1 min"], [60, "1 h"], [1440, "1 day"], [RMAX, "1 week"]].forEach(([m, t]) => {
    const r = rad(m); ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.setLineDash([4, 6]); ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "rgba(255,255,255,0.40)"; ctx.font = "12px Inter"; ctx.fillText(t, r + 4, -4);
  });
  if (NOW < ALL) { const r = rad(NOW); ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.strokeStyle = "rgba(255,92,108,0.35)"; ctx.lineWidth = 2; ctx.stroke(); }
});
const sl = document.getElementById("t"), clock = document.getElementById("clock");
const toM = v => Math.pow(10, v / 1000 * Math.log10(1 + RMAX)) - 1;
const agents = G.nodes.filter(n => n.kind === "agent");
function update(v, exactMin) {  // exactMin: jump to a moment's own time (slider steps are coarse late on the log scale)
  NOW = exactMin != null ? exactMin : v >= 1000 ? ALL : toM(v);
  edges.update(drawn.map(e => ({id: e.id, hidden: mins(e.at) > NOW})));
  const believed = agents.filter(a => [st[a.id].said, st[a.id].did, st[a.id].ok, st[a.id].bad].some(on)).length;
  const ok = agents.filter(a => on(st[a.id].ok)).length;
  const bad = G.nodes.filter(n => isClaim(n) && on(st[n.id].bad)).length;
  const okClaims = G.nodes.filter(n => isClaim(n) && on(st[n.id].ok)).length;
  const lit = agents.filter(a => [st[a.id].said, st[a.id].did, st[a.id].ok, st[a.id].bad].some(on));
  const cnt = k => agents.filter(a => (stanceAt(a.id) || (lit.includes(a) && D[a.id] ? {stance: "neutral"} : null))?.stance === k).length;
  const drift = Object.keys(D).length ? ` · <span style="color:#ff5c6c">${cnt("repeats") + cnt("amplifies")} passed it on</span> (<span style="color:#ff2fb4">${cnt("amplifies")} pushed it further</span>)` + (cnt("flags") ? ` · <span style="color:#4ea8ff">${cnt("flags")} flagged it</span>` : "") + ` · <span style="color:#9aa0a6">${cnt("neutral")} only touched the link</span>` : "";
  clock.innerHTML = (NOW === ALL ? "all time" : "+" + fmt(NOW)) + (Object.keys(D).length ? drift : ` · <span style="color:#ff5c6c">${believed} ${believed === 1 ? "agent" : "agents"} took it up</span>`) +
    (G.seed.kind === "url" && G.edges.some(e => e.kind === "checked") ? ` · <span style="color:#3ddc97">${ok} ran a check that passed ✔</span>` : "") +
    (okClaims ? ` · <span style="color:#3ddc97">${okClaims} ${okClaims === 1 ? "claim" : "claims"} backed by the screen ✔</span>` : "") +
    (bad ? ` · <span style="color:#ff5c6c">${bad} ${bad === 1 ? "claim" : "claims"} contradicted by the agent's own screen ✕</span>` : "");
  net.redraw();
}
sl.oninput = () => update(+sl.value);
let timer = null; const btn = document.getElementById("play");
btn.onclick = () => {
  if (timer) { clearInterval(timer); timer = null; btn.textContent = "▶ play"; return; }
  let v = 0; btn.textContent = "❚❚ pause";
  timer = setInterval(() => { v += 4; sl.value = v; update(v); if (v >= 1000) { clearInterval(timer); timer = null; btn.textContent = "▶ play"; } }, 40);
};
const rowList = es => es.slice(0, 14).map(e => `<div><code>${esc((e.row || (e.rows || [])[1] || "")).slice(0, 8)}</code> ${e.kind}${e.channel ? " · " + e.channel : ""}${e.status ? " · <b>" + e.status + "</b>" : ""}${e.basis ? " (" + e.basis + ")" : ""} · +${fmt(mins(e.at))}</div>`).join("");
net.on("click", p => {
  const info = document.getElementById("info");
  if (p.nodes.length) {
    const n = byId[p.nodes[0]], s = st[n.id];
    const line = (lab, m, col) => m < Infinity ? `<div><span style="color:${col}">●</span> ${lab} at <b>+${fmt(m)}</b></div>` : "";
    if (n.kind === "agent") {
      const ins = told.filter(e => e.target === n.id).map(e => `<div>← told by <b>${esc(short(byId[e.source]?.label))}</b> (${e.evidence}, +${fmt(mins(e.at))})</div>`).join("");
      const dd = D[n.id], pk = stanceAt(n.id);
      const stance = dd ? `<div style="margin:4px 0 8px;padding:8px;border-radius:6px;background:#1f2330">` +
        (pk ? `<span style="color:${STANCE[pk.stance]?.[0]};font-weight:700">● at its strongest: ${STANCE[pk.stance]?.[1]}</span><br>${esc(pk.gist)}<br><span style="color:#9aa0a6">“${esc(pk.cue)}”</span><br><span style="color:#9aa0a6;font-size:12px">+${fmt(mins(pk.at))} · ${pk.src} · row <code>${esc(pk.row).slice(0, 8)}</code></span>` : "") +
        `<div style="margin-top:6px;font-size:12px;color:#c9ccd4">` + dd.timeline.filter(e => mins(e.at) <= NOW).slice(0, 10).map(e => `<div><span style="color:${STANCE[e.stance]?.[0]}">●</span> +${fmt(mins(e.at))} ${esc(e.gist)}</div>`).join("") +
        (dd.timeline.length > 10 ? `<div style="color:#9aa0a6">… ${dd.timeline.length - 10} more</div>` : "") + `</div></div>` : "";
      info.innerHTML = `<div style="font-size:16px;font-weight:700;margin-bottom:6px">${esc(n.label)}</div>` + stance + line("said", s.said, "#ff5c6c") + line("did / acted", s.did, "#f2a541") +
        line("a check held up", s.ok, "#3ddc97") + line("a verifier run errored (not proof either way)", s.err ?? Infinity, "#9aa0a6") + line("its claim was contradicted by its screen", s.bad, "#ff5c6c") + (ins ? `<div style="margin-top:8px;font-weight:600">Heard it from</div>${ins}` : "") +
        `<div style="margin-top:8px;font-weight:600">Rows</div>` + rowList(s.edges.filter(e => e.source === n.id));
    } else {
      const chk = s.edges.filter(e => e.kind === "checked");
      info.innerHTML = `<div style="font-size:15px;font-weight:700;margin-bottom:6px">${esc(n.label)}</div>` +
        (isClaim(n) ? (on(s.bad) ? `<div style="color:#ff5c6c;font-weight:700">✕ The agent's own screen contradicts this claim.</div>` : on(s.ok) ? `<div style="color:#3ddc97;font-weight:700">✔ The screen backs this claim.</div>` : `<div>Not checked against a screen.</div>`) : "") +
        chk.map(e => `<div style="margin-top:6px">claim row <code>${esc(e.claim_row || "").slice(0, 8)}</code> · screenshot turn <code>${esc(e.row).slice(0, 8)}</code></div>`).join("") +
        `<div style="margin-top:8px;font-weight:600">Rows</div>` + rowList(s.edges);
    }
  } else if (p.edges.length) {
    const e = G.edges.find(x => x.id === p.edges[0]);
    if (e) info.innerHTML = `<b>${esc(short(byId[e.source]?.label))}</b> → <b>${esc(short(byId[e.target]?.label))}</b><br>${e.kind}${e.evidence ? " · evidence: <b>" + e.evidence + "</b>" : ""}${e.status ? " · <b>" + e.status + "</b>" : ""} at +${fmt(mins(e.at))}<br>` +
      (e.rows ? `source post <code>${esc(e.rows[0])}</code><br>first use <code>${esc(e.rows[1])}</code>` : `row <code>${esc(e.row)}</code>`);
  }
});
if (Object.keys(D).length) document.getElementById("stlegend").innerHTML = "(" + ["repeats", "amplifies", "hedges", "checks", "flags", "neutral"].map(k => `<span style="color:${STANCE[k][0]}">●</span> ${STANCE[k][1]}`).join(" · ") + ")";
// moment markers: positioned on the slider's log-time scale; click to jump to the moment (+1 s so it counts)
const fromM = m => 1000 * Math.log10(1 + Math.max(m, 0)) / Math.log10(1 + RMAX);
const mbox = document.getElementById("moments");
mbox.style.height = `${Math.max(62, 20 + 15 * Math.max(0, ...MOMENTS.map((m, i) => m.lane ?? i % 3)))}px`;
MOMENTS.forEach((mo, i) => {
  const v = fromM(mins(mo.at)), el = document.createElement("div");
  el.style.cssText = `position:absolute;left:calc(${v / 10}% ${v > 700 ? '+ 1px' : '- 1px'});top:0;cursor:pointer;font-size:11.5px;white-space:nowrap;color:${mo.color};transform:translateX(${v > 700 ? "-100%" : "0"})`;
  const tick = `<span style="display:inline-block;width:2px;height:10px;background:${mo.color};vertical-align:top"></span>`;
  // flipped labels (right side) extend leftwards, so their tick must sit at the right end to mark the true moment
  el.innerHTML = v > 700 ? `${esc(mo.label)} ${tick}` : `${tick} ${esc(mo.label)}`;
  el.style.top = (mo.lane ?? i % 3) * 15 + "px";
  el.title = `${mo.label} · +${fmt(mins(mo.at))} · row ${mo.row}`;
  el.onclick = () => { sl.value = Math.min(999, Math.ceil(v)); update(+sl.value, mins(mo.at) + 1 / 60); };
  mbox.appendChild(el);
});
update(1000);
net.once("afterDrawing", () => net.fit({animation: false}));
setTimeout(() => net.fit({animation: false}), 300);
</script>
"""
