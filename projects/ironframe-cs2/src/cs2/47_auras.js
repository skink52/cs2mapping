// ===================================================================================================================
// IRONFRAME CS2 adapter: frame auras (docs/FEATURES.md "Frame auras"). Every player frame wears a signature effect made by
// tools/auras.py: small additive models (AURAS = out/addon/_gen/auras.json) PARENTED to the frame's upper or legs prop, so
// they ride along with no per-tick moves; their idle motion is the material's own flipbook. The script only swaps a part's
// model (its state) and its SetColor brightness when a flare, a hold or the LOD tier changes.
//   data   PARTS.auras[<frame key>]: style, parts {attach upper|legs|none, idle (base state or null), states, cam}, flares
//          [{on, part, seq [[state, t]...] ('' = back to base), gap, if, pfx, fx}], holds [{when, part, state}], level, reduced
//   LOD    every CONFIG.AURA.every ticks: tier 2 (every part + flares) for humans' own mechs and the nearest fullCap mechs
//          within fullDist of a human; tier 1 (the 'reduced' part, idle only) for the next reducedCap within reducedDist;
//          tier 0 (nothing) beyond. A prop budget (maxProps, and never within `reserve` of CONFIG.MAX_POOL) downgrades the
//          farthest first. Claims per tick are capped (claimsPerTick); a part that could not get a prop retries next tick.
//   events handleEvent -> auraEvent: qb land damage fire(hp >= 2) stagger trait overdrive death; polled every `poll` ticks
//          for tier-2 mechs that use them: wind assault (assault_on) shield (block) reload od od_full.
//   pilot  a human's own mech dims the parts marked cam (CS2 can't hide a prop from one client: the dimming shows to all).
//   hooks  40_fx.js fxMechGone -> auraGone(slot) (before the rig's props are reused), fxReset -> auraReset;
//          90_main.js handleEvent -> auraEvent(ev), frame -> auraTick() after the mechs are drawn.
// ===================================================================================================================
const AURA_CFG = /** @type {any} */ (Object.assign({ on: true, fullDist: 4000, reducedDist: 9000, fullCap: 40, reducedCap: 32, maxProps: 160, reserve: 60,
  claimsPerTick: 6, every: 16, poll: 4, ghosts: 12, hyst: 400 }, /** @type {any} */ (CONFIG).AURA || {}));
const AURA_DATA = /** @type {any} */ ((typeof AURAS === 'object' && AURAS) || {});
const AURA_MODELS = AURA_DATA.frames || {};
const AURA_SPEC = /** @type {any} */ ({});
for (const k of Object.keys(/** @type {any} */ (PARTS).auras || {})) {
  if (k.charAt(0) === '_') continue;
  const sp = /** @type {any} */ (PARTS).auras[k]; const uses = {};
  for (const h of sp.holds || []) uses[h.when] = true;
  for (const f of sp.flares || []) { uses[f.on] = true; if (f.if) uses[f.if] = true; }
  if (sp.level) uses[sp.level.from] = true;
  sp._uses = uses; AURA_SPEC[k] = sp;
}
// the aura particle pools join the shared ones (40_fx.js fxInit finds ifr_pfx_aura_<frame>_NN when the map has them)
for (const k of Object.keys(AURA_DATA.pools || {})) if (!(k in PFX_POOLS)) /** @type {any} */ (PFX_POOLS)[k] = AURA_DATA.pools[k].count || 4;

/** @type {Map<number, any>} */
const auraSt = new Map();          // slot -> {slot, key, spec, rig, upper, tier, human, dist, dirty, busy, cond, parts, hits, assault, od}
const auraFx = [];                 // unparented one-offs (afterimages, drain beams): {p, slot, at, until, steps, kind, model, life, spawned}
const auraHitBy = new Map();       // attacker slot -> victim slot (this tick's damage events, for the drain beam)
let auraUsed = 0, auraClaims = 0, auraFxLive = 0;
const auraStats = { claims: 0, fails: 0, flares: 0, tiers: [0, 0, 0] };

function auraModel(key, pid, state) {
  const f = AURA_MODELS[key]; const p = f && f.parts && f.parts[pid];
  return (p && p.states && p.states[state]) || '';
}
function auraNew(m, key, spec) {
  const parts = {};
  for (const pid of Object.keys(spec.parts)) {
    const def = spec.parts[pid];
    if (def.attach === 'none') continue;
    parts[pid] = { id: pid, def, prop: undefined, cur: '', k: -1, seq: null, si: 0, t0: 0, seqState: '', last: -99 };
  }
  const st = { slot: m.slot, key, spec, rig: rigs.get(m.slot), upper: undefined, tier: 0, human: false, dist: Infinity, dirty: true, busy: false,
    cond: { trait: false }, parts, hits: 0, assault: false, od: -1, tint: auraMk5Tint(m, spec) };
  st.upper = st.rig ? st.rig.upper : undefined;
  auraSt.set(m.slot, st);
  return st;
}
// Mk V reward (docs/AC_FEEL.md, 'Upgrade value'): a frame upgraded to the top level wears its aura in the aura's accent colour
function auraMk5Tint(m, spec) {
  const caps = /** @type {any} */ (PARTS.caps || {}), a = spec && spec.accent;
  return a && m.frame && typeof IF_upgradeLevel === 'function' && IF_upgradeLevel(m.pilot, m.frame.id, caps) >= (caps.levels || 5) ? a : null;
}
function auraBase(st, part) {
  for (const h of st.spec.holds || []) if (h.part === part.id && st.cond[h.when]) return h.state;
  return part.def.idle || '';
}
function auraWant(st, part) {
  if (st.tier === 0) return '';
  if (st.tier === 1) return part.id === st.spec.reduced ? (part.def.idle || '') : '';
  if (part.seq) return part.seqState === '' ? auraBase(st, part) : part.seqState;
  return auraBase(st, part);
}
function auraK(st, part, state) {
  const sp = st.spec, ks = sp.k || {};
  let k = state in ks ? ks[state] : state === part.def.idle ? (sp.idle === undefined ? 0.55 : sp.idle) : 1;
  if (sp.level && sp.level.part === part.id && sp.level.from === 'od' && !part.seq) { const m = game.mechs.get(st.slot); const od = m ? Math.max(0, Math.min(1, m.overdrive || 0)) : 0; k = Math.max(k, k + (1 - k) * od); }
  if (st.human && part.def.cam) k *= sp.cam === undefined ? 0.6 : sp.cam;
  return Math.max(0, Math.min(1, Math.round(k * 16) / 16));
}
// a part's parent: legs parts ride the legs prop (feet rings), the rest the upper body; both keep the frame's model origin
function auraParent(st, part) {
  const r = st.rig; if (!r) return undefined;
  const p = part.def.attach === 'legs' ? (r.legs || r.upper) : r.upper;
  return p && p.lastPos && live(p.ent) ? p : undefined;
}
function auraRoom() { return auraUsed < AURA_CFG.maxProps && propCount < CONFIG.MAX_POOL - AURA_CFG.reserve; }
function auraClaim(st, part, model) {
  if (auraClaims <= 0 || !auraRoom()) { auraStats.fails++; return false; }
  const parent = auraParent(st, part); if (!parent) return false;
  const p = takeProp(); if (!p) { auraStats.fails++; return false; }
  auraClaims--; auraUsed++; auraStats.claims++;
  part.prop = p; part.cur = ''; part.k = -1;
  guard('aura claim', () => {
    propModel(p, model); part.cur = '';
    // on the parent's transform as the ENGINE reports it (30_render.js propParentLocal), local offset zero. It used to Teleport to
    // parent.lastPos, where the script last ASKED the parent to be: stale after a pooled prop is re-used, and null since release clears it
    if (!propParentLocal(p, parent, [0, 0, 0])) { p.ent.Teleport({ position: clampWorld(parent.lastPos || HIDE_POS), angles: parent.lastAng || ZERO_ANG }); p.ent.SetParent(parent.ent); p.parent = parent; }
  });
  return true;
}
function auraRelease(part) {
  if (!part.prop) return;
  releaseProp(part.prop); part.prop = undefined; part.cur = ''; part.k = -1; auraUsed = Math.max(0, auraUsed - 1);
}
// bring every part to the state its tier / hold / flare wants; false while a claim is still pending
function auraSync(st) {
  let ok = true;
  for (const pid of Object.keys(st.parts)) {
    const part = st.parts[pid];
    const want = auraWant(st, part), model = want ? auraModel(st.key, pid, want) : '';
    if (!model) { auraRelease(part); continue; }
    if (!part.prop && !auraClaim(st, part, model)) { ok = false; continue; }
    const p = part.prop; if (!p) continue;
    if (part.cur !== want) { guard('aura state', () => propModel(p, model)); part.cur = want; }
    const k = auraK(st, part, want);
    if (k !== part.k) { const c = Math.round(255 * k), t = st.tint; guard('aura k', () => propColor(p, t ? [Math.round(c * t[0] / 255), Math.round(c * t[1] / 255), Math.round(c * t[2] / 255)] : [c, c, c])); part.k = k; }
  }
  st.dirty = !ok;
  return ok;
}
function auraDropParts(st) { for (const pid of Object.keys(st.parts)) auraRelease(st.parts[pid]); }
function auraGone(slot) {
  const st = auraSt.get(slot); if (!st) return;
  auraDropParts(st); auraSt.delete(slot);
}
function auraReset() {
  for (const st of auraSt.values()) auraDropParts(st);
  auraSt.clear();
  for (const f of auraFx) if (f.p) guard('aura fx reset', () => { if (live(f.p.ent)) f.p.ent.SetModel(NULL_MODEL); });
  auraFx.length = 0; auraHitBy.clear(); auraUsed = 0; auraFxLive = 0;
}

// ---- LOD: rank the mechs by distance to the nearest human, assign tiers within the caps and the prop budget
function auraLod() {
  const hum = [];
  for (const pe of people.values()) {
    if (!pe.human) continue;
    const pm = game.mechs.get(pe.slot); const p = pm && pm.alive ? pm.pos : (pe.deathPos || (pm ? pm.pos : null));
    if (p) hum.push(p);
  }
  const cand = [];
  for (const m of game.mechs.values()) {
    const key = m.frame && m.frame.key, spec = key && AURA_SPEC[key] && AURA_MODELS[key] ? AURA_SPEC[key] : null;
    let st = auraSt.get(m.slot);
    if (!spec || !m.alive || !rigs.has(m.slot)) { if (st) auraGone(m.slot); continue; }
    if (!st || st.key !== key) { if (st) auraGone(m.slot); st = auraNew(m, key, spec); }
    const pe = people.get(m.slot); st.human = !!(pe && pe.human);
    let d = Infinity; for (const p of hum) { const dd = vdist(p, m.pos); if (dd < d) d = dd; }
    st.dist = d; cand.push(st);
  }
  for (const [slot, st] of auraSt) if (!game.mechs.has(slot)) auraGone(st.slot);
  cand.sort((a, b) => (Number(b.human) - Number(a.human)) || (a.dist - b.dist));
  let full = 0, red = 0, budget = AURA_CFG.maxProps;
  const T = auraStats.tiers; T[0] = T[1] = T[2] = 0;
  for (const st of cand) {
    const h2 = st.tier === 2 ? AURA_CFG.hyst : 0, h1 = st.tier >= 1 ? AURA_CFG.hyst : 0;
    let tier = 0;
    if (st.human || (st.dist < AURA_CFG.fullDist + h2 && full < AURA_CFG.fullCap)) tier = 2;
    else if (st.dist < AURA_CFG.reducedDist + h1 && red < AURA_CFG.reducedCap) tier = 1;
    let need = 0;
    if (tier === 2) { for (const pid of Object.keys(st.parts)) if (auraBase(st, st.parts[pid]) || st.parts[pid].prop) need++; if (need > budget) tier = 1; }
    if (tier === 1) { need = st.parts[st.spec.reduced] ? 1 : 0; if (need > budget) tier = 0; }
    if (tier === 0) need = 0;
    budget -= need;
    if (tier === 2 && !st.human) full++; else if (tier === 1) red++;
    T[tier]++;
    if (tier !== st.tier) {
      st.tier = tier; st.dirty = true;
      if (tier < 2) for (const pid of Object.keys(st.parts)) st.parts[pid].seq = null;
    }
  }
}

// ---- flares
function auraFire(st, on) {
  if (!st || st.tier < 2) return;
  const now = gameTime();
  for (const f of st.spec.flares || []) {
    if (f.on !== on) continue;
    if (f.if && !st.cond[f.if]) continue;
    const part = f.part ? st.parts[f.part] : null;
    if (part) {
      if (now - part.last < (f.gap || 0)) continue;
      part.last = now; part.seq = f.seq; part.si = 0; part.t0 = now; part.seqState = part.cur || ''; st.busy = true;
    }
    auraStats.flares++;
    if (f.pfx) auraPfx(st, f.pfx, part);
    if (f.fx === 'ghosts') for (let i = 0; i < (f.count || 3); i++) auraFx.push({ p: undefined, slot: st.slot, at: now + i * (f.every || 0.05), until: 0, kind: 'ghost', model: auraModel(st.key, f.fx_part, 'on'), life: f.life || 0.5, spawned: false, steps: [] });
    if (f.fx === 'drain') auraFx.push({ p: undefined, slot: st.slot, at: now, until: 0, kind: 'drain', model: auraModel(st.key, f.fx_part, 'on'), life: f.life || 0.3, spawned: false, steps: [] });
  }
  if (st.busy) auraSeqStep(st, now);
}
function auraFireSlot(slot, on) { const st = auraSt.get(slot); if (st) auraFire(st, on); }
function auraSeqStep(st, now) {
  let busy = false;
  for (const pid of Object.keys(st.parts)) {
    const part = st.parts[pid]; if (!part.seq) continue;
    const seq = part.seq; let changed = false;
    while (part.si < seq.length && now - part.t0 >= seq[part.si][1] - 1e-6) { part.seqState = seq[part.si][0]; part.si++; changed = true; }
    if (part.si >= seq.length) { part.seq = null; changed = true; } else busy = true;
    if (changed) st.dirty = true;
  }
  st.busy = busy;
  if (st.dirty) auraSync(st);
}
function auraPfx(st, kind, part) {
  const m = game.mechs.get(st.slot); if (!m || !(/** @type {any} */ (PFX_POOLS)[kind] > 0)) return;
  const h = (m.cls && m.cls.height) || 288;
  const pos = v3(m.pos.x, m.pos.y, m.pos.z + (part && part.def.attach === 'legs' ? 24 : h * 0.6));
  pfxBurst(kind, pos, 0.9);
}
// polled conditions (only those the frame's aura uses): a change re-syncs, an edge may fire a flare
function auraPoll(st) {
  const m = game.mechs.get(st.slot); if (!m || !m.alive) return;
  const U = st.spec._uses, c = st.cond; let ch = false;
  const set = (k, v) => { if (c[k] !== v) { c[k] = v; ch = true; } };
  if (U.wind) set('wind', !!(m.trT && m.trT.wind > 0));
  if (U.assault || U.assault_on) { const a = !!m.assault; if (a && !st.assault) auraFire(st, 'assault_on'); st.assault = a; set('assault', a); }
  if (U.shield || U.block) {
    let up = false, hits = 0;
    for (const w of m.weapons || []) if (w && w.type === 'shield') { up = up || !!w.raised; hits += w.hits || 0; }
    set('shield', up);
    if (hits > st.hits) auraFire(st, 'block');
    st.hits = hits;
  }
  if (U.reload) set('reload', !!((m.weapons[2] && m.weapons[2].reloading) || (m.weapons[3] && m.weapons[3].reloading)));
  if (U.od_full) set('od_full', (m.overdrive || 0) >= 1);
  if (U.od) { const q = Math.round((m.overdrive || 0) * 16); if (q !== st.od) { st.od = q; ch = true; } }
  if (ch) st.dirty = true;
}
// one-off props that are not parented: afterimage ghosts (left where the mech was) and the drain beam (victim -> attacker)
function auraFxTick(now) {
  for (let i = auraFx.length - 1; i >= 0; i--) {
    const f = auraFx[i];
    if (!f.spawned) {
      if (now < f.at) continue;
      f.spawned = true;
      const m = game.mechs.get(f.slot), r = rigs.get(f.slot);
      if (!f.model || !m || !m.alive || !r || !r.upper || !r.upper.lastPos || auraFxLive >= AURA_CFG.ghosts || !auraRoom()) { auraFx.splice(i, 1); continue; }
      let pos = r.upper.lastPos, ang = r.upper.lastAng || ZERO_ANG, scale = 1;
      if (f.kind === 'drain') {
        const v = game.mechs.get(auraHitBy.has(f.slot) ? auraHitBy.get(f.slot) : (m.lock && m.lock.target >= 0 ? m.lock.target : -1));
        if (!v) { auraFx.splice(i, 1); continue; }
        const hv = (v.cls && v.cls.height) || 288, ha = (m.cls && m.cls.height) || 288;
        const a = v3(v.pos.x, v.pos.y, v.pos.z + hv * 0.55), b = v3(m.pos.x, m.pos.y, m.pos.z + ha * 0.55), d = vsub(b, a), l = Math.max(1, vlen(d));
        if (l > 1500) { auraFx.splice(i, 1); continue; }
        pos = a; ang = { pitch: -Math.asin(Math.max(-1, Math.min(1, d.z / l))) * R2D, yaw: Math.atan2(d.y, d.x) * R2D, roll: 0 }; scale = Math.max(0.3, Math.min(4, l / 400));
      }
      const p = takeProp(); if (!p) { auraFx.splice(i, 1); continue; }
      f.p = p; auraFxLive++; auraUsed++;
      guard('aura fx', () => { propModel(p, f.model); if (scale !== 1) propScale(p, scale); p.ent.Teleport({ position: clampWorld(pos), angles: ang }); p.lastPos = pos; p.tpRun = 1; propColor(p, [235, 235, 235]); });
      f.until = now + f.life; f.steps = [[now + f.life * 0.4, 150], [now + f.life * 0.75, 70]];
      continue;
    }
    while (f.steps.length && now >= f.steps[0][0]) { const c = f.steps.shift()[1]; if (f.p) guard('aura fx fade', () => propColor(f.p, [c, c, c])); }
    if (now >= f.until) { if (f.p) { releaseProp(f.p); auraFxLive--; auraUsed = Math.max(0, auraUsed - 1); } auraFx.splice(i, 1); }
  }
}

// ---- the per-tick director (after renderAll: every rig is placed this tick)
function auraTick() {
  if (!AURA_CFG.on) return;
  const now = gameTime();
  auraClaims = AURA_CFG.claimsPerTick;
  if (ifrTickNo % AURA_CFG.every === 0) auraLod();
  for (const st of auraSt.values()) {
    const r = rigs.get(st.slot);
    if (!r || r !== st.rig || r.upper !== st.upper || r.upHid) {   // the rig was re-claimed (frame change) or hidden: start over on it
      auraDropParts(st); st.rig = r; st.upper = r ? r.upper : undefined; st.dirty = true;
      if (!r || r.upHid) continue;
    }
    if (st.tier === 2 && (ifrTickNo + st.slot) % AURA_CFG.poll === 0) auraPoll(st);
    if (st.busy) auraSeqStep(st, now);
    if (st.dirty) auraSync(st);
  }
  if (auraFx.length) auraFxTick(now);
  auraHitBy.clear();
}
function auraEvent(ev) {
  if (!AURA_CFG.on) return;
  switch (ev.t) {
    case 'trait': {
      const st = auraSt.get(ev.slot); if (!st) return;
      if (ev.phase === 'on' || ev.phase === 'off') { const v = ev.phase === 'on'; if (st.cond.trait !== v) { st.cond.trait = v; st.dirty = true; } }
      auraFire(st, 'trait:' + ev.phase);
      break;
    }
    case 'qb': auraFireSlot(ev.slot, 'qb'); break;
    case 'land': auraFireSlot(ev.slot, 'land'); if (ev.hard) auraFireSlot(ev.slot, 'land_hard'); break;
    case 'damage':
      if (ev.attacker >= 0 && ev.attacker !== ev.victim) { auraHitBy.set(ev.attacker, ev.victim); auraFireSlot(ev.attacker, 'hit'); }
      auraFireSlot(ev.victim, 'damage');
      break;
    case 'fire': if (ev.hp >= 2) auraFireSlot(ev.slot, 'fire_s'); break;
    case 'stagger': auraFireSlot(ev.slot, 'stagger'); break;
    case 'overdrive': auraFireSlot(ev.slot, 'od:' + ev.phase); break;
    case 'death': auraGone(ev.slot); break;
    default: break;
  }
}
