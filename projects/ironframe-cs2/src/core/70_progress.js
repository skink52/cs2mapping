// ===================================================================================================================
// IRONFRAME core, part 7: progression (DESIGN.md section 7) and the garage catalogue. IF_Progress.validate is the map
// side of the shared contract (docs/SERVER_CONTRACT.md section 5; vectors in data/contract_vectors.json, rules in
// tools/contract_vectors.py): the plugin's Loadout.Validate returns the same (deny, ref) for the same input.
// ===================================================================================================================

const IF_progressIndex = new WeakMap();
function IF_partsIndex(parts) {
  if (!parts) parts = (typeof PARTS !== 'undefined') ? PARTS : null;
  if (!parts) return null;
  if (parts.byId instanceof Map) return parts;           // already an index
  let ix = IF_progressIndex.get(parts);
  if (!ix) { ix = IF_indexParts(parts); IF_progressIndex.set(parts, ix); }
  return ix;
}
function IF_owns(pilot, id) {
  const o = pilot.owned;
  if (!o) return false;
  if (o instanceof Set) return o.has(id) || o.has(String(id));
  if (Array.isArray(o)) return o.indexOf(id) >= 0 || o.indexOf(String(id)) >= 0;
  return !!o[id];
}

const IF_Progress = {
  lastRef: 0,
  // (deny code; the reference part / position is left in IF_Progress.lastRef, and validateRef returns both)
  validate(loadoutStr, pilot, parts) { const r = IF_Progress.validateRef(loadoutStr, pilot, parts); return r.deny; },
  validateRef(loadoutStr, pilot, parts) {
    const P = IF_partsIndex(parts), out = { deny: 7, ref: 0 };
    IF_Progress.lastRef = 0;
    const ids = IF_parseLoadout(loadoutStr);
    if (!ids || !P) return out;
    for (let pos = 1; pos <= 9; pos++) {
      const id = ids[pos - 1], kind = IF_LOADOUT_KINDS[pos - 1];
      if (id === 0) { if (pos >= 2 && pos <= 5) continue; out.ref = pos; IF_Progress.lastRef = pos; return out; }
      const p = P.byId.get(id);
      if (!p || p.kind !== kind || (p.left_only && pos === 2)) { out.ref = pos; IF_Progress.lastRef = pos; return out; }
    }
    if (pilot) {
      for (const id of ids) if (id && !IF_owns(pilot, id)) { out.deny = IF_DENY.NOT_OWNED; out.ref = id; IF_Progress.lastRef = id; return out; }
    }
    const b = IF_Progress.sums(ids, P);
    if (b.weight > b.load) { out.deny = IF_DENY.WEIGHT; return out; }
    if (b.en > b.output * IF_EN_FACTOR) { out.deny = IF_DENY.EN; return out; }
    out.deny = 0;
    return out;
  },
  // weight / EN sums of a parsed (structurally valid) loadout, contract rules (frame mods do not change the load)
  sums(ids, P) {
    let weight = 0, en = 0;
    for (const id of ids) { if (!id) continue; const p = P.byId.get(id); if (p) { weight += p.weight || 0; en += p.en || 0; } }
    const frame = P.byId.get(ids[0]), bst = P.byId.get(ids[6]), gen = P.byId.get(ids[5]);
    const load = (frame && P.classes[frame.class] ? P.classes[frame.class].load : 0) + (bst && bst.b && bst.b.load_bonus ? bst.b.load_bonus : 0);
    const output = gen && gen.g ? gen.g.output : 1;
    return { weight, en, load, output };
  },
  // cumulative XP to reach rank: sum over n < rank of floor(rank_base + rank_mult * n^rank_pow)
  xpFor(rank, parts) {
    const P = IF_partsIndex(parts), X = P ? P.xp : { rank_base: 600, rank_mult: 180, rank_pow: 1.5, max_rank: 50 };
    rank = IF_clamp(Math.floor(IF_fin(+rank, 1)), 1, X.max_rank || 50);
    let s = 0;
    for (let n = 1; n < rank; n++) s += Math.floor(X.rank_base + X.rank_mult * Math.pow(n, X.rank_pow));
    return s;
  },
  rankFor(xp, parts) {
    const P = IF_partsIndex(parts), max = P ? P.xp.max_rank : 50;
    xp = IF_fin(+xp, 0);
    let r = 1;
    while (r < max && IF_Progress.xpFor(r + 1, parts) <= xp) r++;
    return r;
  },
  // XP and credits for a round summary. ctx: {won, rank, medianRank, parts, cap}
  // kill XP x2 / x3 for bounty kills (caps.bounty), x catchup below the lobby median rank, capped per round.
  roundXp(s, ctx) {
    ctx = ctx || {};
    const P = IF_partsIndex(ctx.parts), X = P.xp, caps = P.caps;
    const b2 = s.bountyKills2 || 0, b3 = s.bountyKills3 || 0, plain = Math.max(0, (s.kills || 0) - b2 - b3);
    let xp = X.participation + X.kill * (plain + 2 * b2 + 3 * b3) + X.assist * (s.assists || 0) + X.capture * (s.captures || 0)
      + (ctx.won !== undefined ? (ctx.won ? X.win : 0) : (s.won ? X.win : 0)) + Math.floor(X.survive_per_s * (s.survive || 0))
      + 20 * (s.pveKills || 0) + 400 * (s.bossKills || 0);
    if (ctx.rank > 0 && ctx.medianRank > 0 && ctx.rank < ctx.medianRank) xp *= caps.catchup_xp_mult || 1.5;
    xp = Math.min(Math.round(xp), ctx.cap || 6000);
    return { xp, credits: Math.round(xp * X.credits_per_xp) };
  },
  // the rookie damage multiplier a victim of rank vr takes from an attacker of rank ar
  rookieMult(vr, ar, parts) {
    const P = IF_partsIndex(parts);
    for (const rs of P.caps.rookie_shield || []) if (vr > 0 && vr < rs.below_rank && ar >= rs.vs_rank) return 1 - rs.pct / 100;
    return 1;
  },
};

// ---------------------------------------------------------------------------------------------------------- garage
class IF_Garage {
  constructor(game) { this.game = game; }
  get P() { return this.game.P; }
  // parts of a kind for the UI (no PvE parts), by rank then id
  list(kind) { return (this.P.byKind[kind] || []).filter((p) => !p.pve).slice().sort((a, b) => (a.rank - b.rank) || (a.id - b.id)); }
  // budgets of a loadout string for the garage bars: {weight, load, en, output, overdraw, valid, deny, ref, ap, walk, boost, qb, enMax, regen}
  budgets(loadoutStr, pilot) {
    const P = this.P, r = IF_Progress.validateRef(loadoutStr, pilot || null, P);
    const ids = IF_parseLoadout(loadoutStr) || [0, 0, 0, 0, 0, 0, 0, 0, 0];
    const s = IF_Progress.sums(ids, P);
    const frame = P.byId.get(ids[0]), cls = frame && P.classes[frame.class];
    const gen = P.byId.get(ids[5]), bst = P.byId.get(ids[6]), mods = (frame && frame.mods) || {};
    const lvl = (id) => IF_upgradeLevel(pilot, id, P.caps);
    const out = { weight: s.weight, load: s.load, en: s.en, output: s.output, overdraw: s.output > 0 ? s.en / s.output : 0,
      valid: r.deny === 0, deny: r.deny, ref: r.ref, ap: 0, walk: 0, boost: 0, qb: 0, enMax: 0, regen: 0, dps: 0 };
    if (cls) {
      out.ap = Math.round(cls.ap * (mods.ap || 1) * (1 + Math.min(P.caps.ap_pct, (frame.upgrade ? frame.upgrade.pct : 0) * lvl(frame.id)) / 100));
      out.walk = Math.round(cls.walk * (mods.walk || 1));
      if (bst && bst.b) { out.boost = Math.round(cls.boost * bst.b.thrust * (mods.boost || 1)); out.qb = Math.round(cls.qb * bst.b.qb_mult * (mods.qb || 1)); }
    }
    if (gen && gen.g) {
      out.enMax = Math.round(gen.g.capacity * (1 + ((gen.upgrade ? gen.upgrade.pct : 0) * lvl(gen.id)) / 100));
      out.regen = Math.round(gen.g.regen * (mods.regen || 1) * (s.en > s.output ? s.output / s.en : 1));
    }
    for (let i = 1; i <= 4; i++) { const p = P.byId.get(ids[i]); if (p && p.w) out.dps += IF_weaponDps(p, lvl(p.id), P.caps); }
    out.dps = Math.round(out.dps);
    return out;
  }
  // a part's card: {id, key, name, kind, desc, cost, rank, level, maxLevel, rows: [[label, value]], lines: [text]}
  describe(id, pilot) {
    const P = this.P, p = P.byId.get(+id);
    if (!p) return null;
    const lvl = IF_upgradeLevel(pilot, p.id, P.caps), rows = [];
    const add = (k, v) => rows.push([k, String(v)]);
    if (p.kind === 'frame') {
      const c = P.classes[p.class] || {}, m = p.mods || {};
      add('Class', p.class); add('Legs', p.legs);
      add('AP', Math.round(c.ap * (m.ap || 1) * (1 + Math.min(P.caps.ap_pct, (p.upgrade ? p.upgrade.pct : 0) * lvl) / 100)));
      add('Walk', Math.round(c.walk * (m.walk || 1))); add('Boost', Math.round(c.boost * (m.boost || 1))); add('Quick boost', Math.round(c.qb * (m.qb || 1)));
      add('Load', c.load); add('Stagger cap', Math.round(c.stagger * ((P.legs[p.legs] || {}).stagger_mult || 1) * (m.stagger || 1)));
    } else if (p.w) {
      const w = p.w, mult = 1 + Math.min(P.caps.dps_pct, ((p.upgrade && p.upgrade.stat === 'damage') ? p.upgrade.pct : 0) * lvl) / 100;
      add('Type', w.type + (w.ability ? ' (' + w.ability + ')' : ''));
      if (w.damage) add('Damage', Math.round(w.damage * mult) + (w.pellets ? ' x' + w.pellets : '') + (w.count ? ' x' + w.count : ''));
      if (w.rate) add('Rate', w.rate + '/s'); if (w.cd) add('Cooldown', w.cd + ' s');
      const fo = P.raw.falloff && P.raw.falloff[p.key];
      if (w.range) add('Range', fo ? Math.round(w.range * fo.ideal) + ' / ' + w.range : w.range); if (w.impact) add('Impact', w.impact); if (w.splash) add('Splash', w.splash);
      if (w.mag) add('Magazine', w.mag); if (w.ammo) add('Ammo', w.ammo); if (w.en_shot) add('EN per shot', w.en_shot);
      if (w.lock) add('Lock', w.lock); if (w.block) add('Blocks', Math.round(w.block * 100) + ' % in front');
      if (w.shield_hp) add('Bubble HP', w.shield_hp); if (w.heal) add('Heal', w.heal); if (w.charges) add('Charges', w.charges);
      const dps = IF_weaponDps(p, lvl, P.caps); if (dps > 0) add('DPS', Math.round(dps));
    } else if (p.g) { add('Capacity', p.g.capacity); add('Regen', p.g.regen + '/s'); add('Output', p.g.output); add('Stall', p.g.stall + ' s'); }
    else if (p.b) { add('Thrust', 'x' + p.b.thrust); add('Quick boost', 'x' + p.b.qb_mult); add('QB cost', 'x' + p.b.qb_cost_mult); add('Hover', 'x' + p.b.hover); add('Drain', 'x' + p.b.drain_mult); if (p.b.load_bonus) add('Load bonus', p.b.load_bonus); }
    else if (p.f) { add('Cone', p.f.cone + ' deg'); add('Range', p.f.range); add('Soft lock', p.f.soft + ' s'); add('Hard lock', p.f.hard + ' s'); add('Gimbal', p.f.gimbal + ' deg'); }
    if (p.weight !== undefined) add('Weight', p.weight);
    if (p.en !== undefined && p.kind !== 'paint') add('EN load', p.en);
    return { id: p.id, key: p.key, name: p.name, kind: p.kind, desc: p.desc || '', cost: p.cost || 0, rank: p.rank || 1, level: lvl, maxLevel: P.caps.levels,
      upgrade: p.upgrade ? p.upgrade.stat + ' +' + p.upgrade.pct + ' %/level' : '', rows, lines: rows.map((r) => r[0] + ': ' + r[1]) };
  }
  // can this slot's pilot buy part id? 0 or a deny code (stand-alone: everything is owned -> 6)
  canBuy(slot, id) {
    const m = this.game.mechs.get(slot), p = this.P.byId.get(+id);
    if (!p || p.pve) return IF_DENY.BAD;
    const pilot = m ? m.pilot : null;
    if (!pilot) return IF_DENY.CAP;
    if (IF_owns(pilot, p.id)) return IF_DENY.CAP;
    if ((pilot.rank || 1) < (p.rank || 1)) return IF_DENY.RANK;
    if ((pilot.credits || 0) < (p.cost || 0)) return IF_DENY.CREDITS;
    return 0;
  }
  canUpgrade(slot, id) {
    const m = this.game.mechs.get(slot), p = this.P.byId.get(+id);
    if (!p || p.pve) return IF_DENY.BAD;
    const pilot = m ? m.pilot : null;
    if (!pilot || !IF_owns(pilot, p.id)) return IF_DENY.NOT_OWNED;
    const lvl = IF_upgradeLevel(pilot, p.id, this.P.caps);
    if (lvl >= this.P.caps.levels) return IF_DENY.CAP;
    if ((pilot.credits || 0) < IF_upgradeCost(p, lvl, this.P.caps)) return IF_DENY.CREDITS;
    return 0;
  }
}

// the credits for the step from level lvl to lvl + 1: floor(max(cost, caps.upgrade_floor_cost) x caps.upgrade_cost_pct / 100) x (lvl + 1);
// the plugin's Catalog.UpgradeCost is the same integer maths (SERVER_CONTRACT.md section 5b).
// The floor (11 Nov 2026, skink52): a starter part has price 0 and every part has the same upgrade track, so a starter got for nothing
// what a bought part pays 4.5 x its price for. A free part's upgrades are priced as if it cost the floor (the cheapest paid part).
function IF_upgradeCost(p, lvl, caps) {
  const pct = caps && caps.upgrade_cost_pct !== undefined ? caps.upgrade_cost_pct : 100;
  return Math.floor(Math.max(p.cost || 0, (caps && caps.upgrade_floor_cost) || 0) * pct / 100) * ((lvl || 0) + 1);
}
// the garage name of an upgrade level: STOCK, MK I .. MK V
function IF_tierName(lvl) { return lvl > 0 ? 'MK ' + ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'][Math.min(9, lvl - 1)] : 'STOCK'; }

// sustained DPS of a weapon part (catalogue maths, for the garage and the balance tables)
function IF_weaponDps(p, lvl, caps) {
  const w = p.w; if (!w || !w.damage) return 0;
  const mult = 1 + Math.min(caps ? caps.dps_pct : 10, ((p.upgrade && p.upgrade.stat === 'damage') ? p.upgrade.pct : 0) * (lvl || 0)) / 100;
  const per = w.damage * (w.pellets || 1) * (w.count || 1) * mult;
  let period = w.rate ? 1 / w.rate : (w.cd || 1);
  if (w.windup) period = Math.max(period, w.windup);
  if (w.mag && w.reload) period = (w.mag * period + w.reload) / w.mag;
  if (w.heat_time) period *= (w.heat_time + w.cool_time) / w.heat_time;
  return per / period;
}

// ===================================================================================================================
// Customisation that follows the pilot, the leaderboard and the operator's match rules (docs/SERVER_CONTRACT.md sections
// 8-10). MAP CONTRACT: the SlimeMG IronFrame module (IronFrame/Career.cs) writes these strings and origin ints; the
// tables are data/career.json (CAREER), a copy of which the plugin loads. Vectors: data/contract_vectors.json profiles /
// server_rules / boards / texts (tools/contract_vectors.py states the rules once). Stand-alone play uses the same
// profile object, kept by the adapter for the session (IF_Career.blank()).
// ===================================================================================================================
// (the data constants of the build are declared after the core: CAREER is read at the first use, never while the module loads)
let IF_careerCache = /** @type {any} */ (null);
function IF_careerData() {
  if (!IF_careerCache) IF_careerCache = /** @type {any} */ ((typeof CAREER !== 'undefined' && CAREER) || { slots: 6, name_len: 10, callsign_len: 12,
    alphabet: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -', accents: [], camera: [{ id: 0, name: 'Standard', mult: 1 }], honours: [], contract_stats: [], modes: ['tb', 'cq', 'kh', 'ctf', 'sk', 'so'] });
  return IF_careerCache;
}
// the operator's rules for this server (IF_Career.setRules; null = the map's own): every arena copy's core reads them
let IF_RULES = /** @type {any} */ (null);
const IF_Career = {
  get data() { return IF_careerData(); },
  KIND_PROFILE: 3, KIND_RULES: 4, KIND_BOARD: 5,
  PREF_CAM: 7, PREF_HINTS_OFF: 8,
  get slots() { return IF_careerData().slots || 6; },
  // ---- text: a-z to capitals (ASCII only), '_' is a space, anything outside the alphabet goes, runs of spaces to one, cut to max
  clean(text, max) {
    const A = IF_careerData().alphabet; let t = '';
    for (const ch of String(text === undefined || text === null ? '' : text)) {
      let c = ch; if (c >= 'a' && c <= 'z') c = String.fromCharCode(c.charCodeAt(0) - 32); if (c === '_') c = ' ';
      if (c.length === 1 && A.indexOf(c) >= 0) t += c;
    }
    return t.split(' ').filter((x) => x).join(' ').slice(0, max).trim();
  },
  wire(text) { return String(text || '').replace(/ /g, '_'); },
  // n ints -> text (two characters an int: code1 + 40 x code2; code = alphabet index + 1, 0 ends)
  unpairs(v, i, n) {
    const A = IF_careerData().alphabet; let t = '';
    for (let k = 0; k < n; k++) { const x = v[i + k] | 0; for (const c of [x % 40, Math.floor(x / 40) % 40]) { if (c <= 0 || c > A.length) return t; t += A[c - 1]; } }
    return t;
  },
  honour(id) { return IF_careerData().honours.find((h) => h.id === (id | 0)) || null; },
  accent(id) { return IF_careerData().accents.find((a) => a.id === (id | 0)) || null; },
  camera(id) { return IF_careerData().camera.find((c) => c.id === (id | 0)) || IF_careerData().camera[0]; },
  contractLabel(code) { const c = IF_careerData().contract_stats[(code | 0) - 1]; return c ? c.label : 'CONTRACT'; },
  // a profile with nothing set (a new pilot; the stand-alone pilot of a session)
  blank() {
    return { callsign: '', title: 0, badge: 0, earned: new Set(), prefs: 0, fav: 0, place: 0, accents: [0, 0, 0, 0, 0, 0], loadouts: [null, null, null],
      names: ['', '', '', '', '', ''], daily: [] };
  },
  // "q1.<callsign>.<title>.<badge>.<earned hex>.<prefs>.<fav>.<place>.<accents>.<L4>.<L5>.<L6>.<names>.<daily>" -> profile, or null
  parseProfile(s) {
    const f = String(s).split('.');
    if (f[0] !== 'q1' || f.length < 14) return null;
    const int = (x, hi) => IF_clamp(parseInt(x, 10) || 0, 0, hi);
    const p = IF_Career.blank();
    p.callsign = IF_Career.clean(f[1], IF_careerData().callsign_len);
    p.title = int(f[2], 24); p.badge = int(f[3], 24);
    const hex = /^[0-9a-f]{1,8}$/.test(f[4]) ? parseInt(f[4], 16) : 0;
    for (let b = 1; b <= 24; b++) if (Math.floor(hex / Math.pow(2, b)) % 2 === 1) p.earned.add(b);
    p.prefs = int(f[5], 8191); p.fav = int(f[6], 8191); p.place = int(f[7], 1e9);
    for (let k = 0; k < 6; k++) { const a = parseInt((f[8] || '')[k], 16); p.accents[k] = Number.isFinite(a) ? a : 0; }
    for (let k = 0; k < 3; k++) p.loadouts[k] = f[9 + k] && f[9 + k] !== '0' && IF_parseLoadout(f[9 + k]) ? f[9 + k] : null;
    const names = String(f[12] || '').split(',');
    for (let k = 0; k < 6; k++) p.names[k] = IF_Career.clean(names[k] || '', IF_careerData().name_len);
    if (f[13] && f[13] !== '0') for (const d of f[13].split(',').slice(0, 3)) {
      const x = d.split('-').map((y) => parseInt(y, 10) || 0);
      if (x.length >= 3 && x[2] > 0) p.daily.push({ code: x[0], progress: Math.min(x[1], x[2]), goal: x[2], reward: x[3] || 0 });
    }
    return p;
  },
  // the origin form (kind 3) -> the string form
  profileFromInts(v) {
    let i = 0; const next = () => (i < v.length ? v[i++] | 0 : 0);
    if (next() < 2) return null;
    const title = next(), badge = next(), earned = next() + next() * 8192, prefs = next(), fav = next(), place = next(), a0 = next(), a1 = next();
    const acc = [a0 & 15, (a0 >> 4) & 15, (a0 >> 8) & 15, a1 & 15, (a1 >> 4) & 15, (a1 >> 8) & 15].map((x) => x.toString(16)).join('');
    const callsign = IF_Career.unpairs(v, i, 6); i += 6;
    const nd = Math.min(3, next()), daily = [];
    for (let k = 0; k < nd; k++) daily.push([next(), next(), next(), next()].join('-'));
    const lm = next(), lds = [];
    for (let k = 0; k < 3; k++) { if (lm & (1 << k)) { const ids = []; for (let j = 0; j < 9; j++) ids.push(next()); lds.push(ids.join(',')); } else lds.push('0'); }
    const nm = next(), names = [];
    for (let k = 0; k < 6; k++) { if (nm & (1 << k)) { names.push(IF_Career.wire(IF_Career.unpairs(v, i, 5))); i += 5; } else names.push(''); }
    return ['q1', IF_Career.wire(callsign), title, badge, earned.toString(16), prefs, fav, place, acc, lds[0], lds[1], lds[2], names.join(','), daily.length ? daily.join(',') : '0'].join('.');
  },
  // "r1.<rotation>.<round s>.<ai min x 10>.<ai max x 10>.<xp %>.<flags>" -> rules, or null
  parseRules(s) {
    const f = String(s).split('.');
    if (f[0] !== 'r1' || f.length < 7) return null;
    const M = IF_careerData().modes, int = (x, lo, hi, d) => { const n = parseInt(x, 10); return Number.isFinite(n) ? IF_clamp(n, lo, hi) : d; };
    const rotation = f[1] === '0' ? [] : f[1].split(',').filter((m) => M.indexOf(m) >= 0).slice(0, 8);
    const rs = int(f[2], 0, 3600, 0), a = int(f[3], 0, 20, 0) / 10, b = int(f[4], 0, 20, 20) / 10;
    return { rotation, roundS: rs >= 60 ? rs : 0, aiMin: Math.min(a, b), aiMax: Math.max(a, b), xpRate: int(f[5], 0, 1000, 100) / 100, flags: int(f[6], 0, 8191, 0) };
  },
  rulesFromInts(v) {
    if ((v[0] | 0) < 1) return null;
    const M = IF_careerData().modes, rot = [];
    for (const x of [v[1] | 0, v[2] | 0]) for (let k = 0; k < 4; k++) { const c = (x >> (3 * k)) & 7; if (c >= 1 && c <= M.length) rot.push(M[c - 1]); }
    return ['r1', rot.length ? rot.join(',') : '0', v[3] | 0, v[4] | 0, v[5] | 0, v[6] | 0, v[7] | 0].join('.');
  },
  // "t1.<total>.<NAME>,<rank>,<xp>..." -> {total, rows: [{name, rank, xp}]}, or null
  parseBoard(s) {
    const f = String(s).split('.');
    if (f[0] !== 't1' || f.length < 2) return null;
    const rows = [];
    for (const r of f.slice(2, 12)) { const x = r.split(','); if (x.length >= 3) rows.push({ name: IF_Career.clean(x[0], IF_careerData().callsign_len) || 'PILOT', rank: parseInt(x[1], 10) || 1, xp: parseInt(x[2], 10) || 0 }); }
    return { total: parseInt(f[1], 10) || 0, rows };
  },
  boardFromInts(v) {
    if ((v[0] | 0) < 1) return null;
    const n = Math.min(10, v[1] | 0), out = ['t1', v[2] | 0];
    for (let k = 0; k < n; k++) { const i = 3 + k * 9; out.push(IF_Career.wire(IF_Career.unpairs(v, i, 6)) + ',' + (v[i + 6] | 0) + ',' + ((v[i + 7] | 0) + (v[i + 8] | 0) * 8192)); }
    return out.join('.');
  },
  // ---- the operator's match rules: null / nothing set = the map's own behaviour
  setRules(r) { IF_RULES = r && (r.rotation.length || r.roundS || r.aiMin > 0 || r.aiMax < 2 || r.xpRate !== 1 || r.flags) ? r : null; return IF_RULES; },
  rules() { return IF_RULES; },
  // the next mode of the operator's rotation: a vote for a mode in the rotation wins, else the entry after the last mode played
  rotationPick(last, tally) {
    const R = IF_RULES && IF_RULES.rotation; if (!R || !R.length) return '';
    let best = '', bv = 0;
    if (tally) for (const k of R) if ((tally[k] || 0) > bv) { bv = tally[k]; best = k; }
    if (best) return best;
    return R[(R.indexOf(last) + 1) % R.length];
  },
  // ---- what the HUD says about a pilot: {name, tag, title}; `fallback` is the player's own name
  identity(profile, fallback) {
    const b = profile ? IF_Career.honour(profile.badge) : null, t = profile ? IF_Career.honour(profile.title) : null;
    return { name: (profile && profile.callsign) || String(fallback || ''), tag: b && b.kind === 'badge' ? String(b.tag || '') : '', title: t && t.kind === 'title' ? String(t.name).toUpperCase() : '' };
  },
};
