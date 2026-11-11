// Balance tables: AI duels per weapon family and per class x tier, 8v8 family squads against the rifle baseline, and the
// anti-stomp check (a fully upgraded loadout vs stock). Writes docs/BALANCE.md. usage: node test/balance.cjs [seeds=1] [reps=2]
const fs = require('fs'), path = require('path');
const { C, makeGame, ROOT } = require('./lib.cjs');
const SEEDS = +(process.argv[2] || 1), REPS = +(process.argv[3] || 2);
const DT = 1 / 64;
const P = C.PARTS, byId = new Map(P.parts.map((p) => [p.id, p]));

// one fight: mechs [{lo, tier, team}], placed in two lines `gap` apart; ends at the first kill (duel) or after `secs`
function fight(specs, seed, opts) {
  opts = opts || {};
  const g = makeGame({ seed, cfg: { round: { tb: 9999, warmup: 0, podium: 2 }, ai: { npcFill: false }, tb: { killMin: 999, killMax: 999 } } });
  g.setMode('tb', 0); g.startRound(0);
  specs.forEach((s, i) => {
    g.addPlayer(i, { team: s.team, human: false, name: 'b' + i, pilot: s.pilot || null });
    const c = g.setLoadout(i, s.lo); if (c) throw new Error('deny ' + c + ' ' + s.lo);
    C.IF_Ai.attach(g, g.mechs.get(i), s.tier || 'normal');
  });
  g.tick(DT, DT);
  const gap = opts.gap || 2600, per = { 2: 0, 3: 0 };
  for (const [i, s] of specs.entries()) {
    const m = g.mechs.get(i), k = per[s.team]++;
    m.pos.x = (s.team === 2 ? -1 : 1) * gap / 2 + (k % 2) * 200; m.pos.y = (k - 3.5) * 350; m.pos.z = g.nav.height(m.pos.x, m.pos.y) + 5;
    m.dropT = 0; m.onGround = true; m.protect = 0; m.vel.x = m.vel.y = m.vel.z = 0;
  }
  const dmg = new Map(), first = { t: -1, killer: -1, victim: -1 }, kills = { 2: 0, 3: 0 };
  let t = 0;
  const secs = opts.secs || 60;
  for (let k = 0; k < secs * 64; k++) {
    g.tick(DT, t += DT);
    for (const e of g.events) {
      if (e.t === 'damage' && e.attacker >= 0 && e.attacker !== e.victim) dmg.set(e.attacker, (dmg.get(e.attacker) || 0) + e.amount);
      if (e.t === 'kill') { if (first.t < 0) { first.t = t; first.killer = e.killer; first.victim = e.victim; } const vm = g.mechs.get(e.victim); if (vm) kills[vm.team === 2 ? 3 : 2]++; }
    }
    g.events.length = 0;
    if (opts.duel && first.t >= 0) break;
  }
  const apFrac = { 2: 0, 3: 0 };
  for (const m of g.mechs.values()) if (m.alive) apFrac[m.team] += m.ap / m.apMax;
  return { g, t, first, kills, dmg, apFrac };
}
function duel(loA, loB, tierA, tierB, seed, pilots) {
  const r = fight([{ lo: loA, tier: tierA, team: 2, pilot: pilots && pilots[0] }, { lo: loB, tier: tierB, team: 3, pilot: pilots && pilots[1] }], seed, { duel: true, secs: 60 });
  let win = 0;   // +1 A, -1 B, 0 draw
  if (r.first.t >= 0) win = r.first.killer === 0 ? 1 : r.first.killer === 1 ? -1 : (r.first.victim === 0 ? -1 : 1);
  else win = r.apFrac[2] > r.apFrac[3] + 0.05 ? 1 : r.apFrac[3] > r.apFrac[2] + 0.05 ? -1 : 0;
  return { win, ttk: r.first.t >= 0 ? r.t : null, dpsA: (r.dmg.get(0) || 0) / r.t, dpsB: (r.dmg.get(1) || 0) / r.t };
}
const pct = (x) => (100 * x).toFixed(0) + ' %';
const out = [];
const t0 = Date.now();
// what was tuned in data/parts.json and why (kept with the tables)
const NOTES = [
  '- **Stagger lock** (first pass): two rifles (impact 60 x 7/s each) and gatlings (25 x 25/s) kept a medium permanently staggered, so close-range builds',
  '  could never boost in (shotgun 0-7 %, rifle 85-90 %). Fix: rifle impact 60 -> 30, gatling 25 -> 10, SMG 30 -> 15 (DESIGN: shotguns, bazookas and',
  '  blades stagger, rifles and gatlings finish), plus a core rule: for 2.5 s after a stagger ends the meter fills at 25 % (`cfg.dmg.staggerGuard`).',
  '- **Rifle** 220 -> 170 damage: with the stagger fixed it still won 85 % at every range (light, long range, gun assist). Now about 67 %.',
  '- **Gatling** 80 -> 65 and **SMG** 120 -> 100: the next dominant pair (94 % / 80 %) once the rifle came down.',
  '- **Shotgun** 90 -> 120 per pellet and range 1 200 -> 1 500, plus the AI closing in (boost and quick boost toward the target when its band is short): 0 % -> 64 %.',
  '- **Rail gun** 1 400 -> 1 200: hitscan suits the hard AI aim (75-90 %).',
  '- **Plasma** speed 2 000 -> 2 800, splash 150 -> 200, damage 600 -> 700: the slow orb missed every strafing target (6 %); now about 35 %.',
  '- **Blade** 2 200 -> 2 600: still low with AI pilots (they lunge late into a retreating rifle); a human with the lock-on lunge is expected to do far better, so it is',
  '  left for the in-game test rather than tuned further on bot numbers.',
  '- **Classes**: with equal weapons the heavy won 83-100 % of duels against the light. Light AP 7 000 -> 7 800, heavy 12 000 -> 11 000',
  '  (DESIGN.md section 3 still lists the old numbers); duels are now mixed, with more 60 s draws (the light lives by dodging).',
  '- Maxed vs stock duels with identical AI favour the maxed pilot strongly (the +15 % AP / +10 % DPS decides an otherwise even fight);',
  '  in real lobbies skill spread dominates, and the rookie shield and catch-up XP apply on top.',
  '- **Arsenal expansion** (parts 113-118, 211-214): burst rifle 165 -> 135 per round (83 % -> 54 %); energy shotgun EN 140 -> 90 per shot, 75 -> 100 x 10 pellets, range 1 500',
  '  (16 % -> about 49 %, it starved itself of EN); flamethrower 40 -> 115 direct, burn 150 -> 320 AP/s for 4 s, range 1 000 (0 % -> about 9 %: AI rifles kite out of a 1 000 u',
  '  weapon like they do the blade; the 8v8 ratio 0.3 matches shotgun and blade; a human closing from cover is the intended use). Pile bunker, heavy blade, sniper and the',
  '  four shoulders sit between 30 and 63 %. The shoulder table is new: AC-Drum (an always-on second gun) wins 100 % against missiles and utility, an old finding that is',
  '  not a regression (the 5 % anti-stomp caps hold, see below); left for a later pass.',
  '- The AI loadout `12,205,...` (hard) had a shoulder autocannon in the right arm (deny 7); it is now `12,102,...` (gatling).',
  '- **AC feel pass** (10 Nov 2026, docs/AC_FEEL.md): class AP +20 % (light 9 500, medium 10 800, heavy 12 900: AC6 build AP), boost +15 %, QB as a 0.18 s jet,',
  '  free ground boost, EN regen x1.6, stagger meter held 2 s then drained at 450/s, per-weapon direct-hit multipliers (`dha`). TTKs rose by about a third.',
  '  Frame ap mods retuned (Stryder 1.19, Lisa 1.26, Atlas 0.89, Cerberus Atlas 0.89); the shotgun went to 89 % (sticky meter + crit), so its `dha` is 1.5',
  '  and impact 70 -> 60 (back to about 67 %); laser rifle EN per shot 180 -> 230 (the faster regen had it at 77 %). Anti-stomp AP check allows 1 AP of rounding.',
  '- **Anti-stomp, second pass** (10 Nov 2026): the longer AC duels let a maxed pilot win 84-89 % of mirror duels (sides swapped). Caps AP +15 -> +5 %, DPS +10 -> +3 %,',
  '  mobility 8 -> 3 %; ladders flattened so level 5 lands on the cap: frame AP 3 -> 1 %/level, weapon damage 2 -> 0.6, generator capacity 4 -> 1, booster efficiency',
  '  3 -> 0.6, FCS lock time -3 -> -1, shield block 2 -> 1, repair / bubble 3 -> 1. Mirror duels with zero upgrades read 56-57 % for the "maxed" side (seed noise),',
  '  so about 67-70 % is an edge of 10-14 points: a stock pilot who out-plays the bot difference wins. The duel test now alternates sides (48 fights).',
  '- **Weapons, second pass**: AC6 ideal-range fall-off (`falloff` in parts.json: rifle / burst rifle 50 % of range then down to 55 %, SMG, gatling, shotguns, laser,',
  '  autocannon); blade lunges home on a locked target anywhere inside the 900 u melee lock range (AI band 720). Flamer range 1 000 -> 1 400, 115 -> 140, burn 320 -> 400;',
  '  rifle 170 -> 155, rail 1 200 -> 950, laser 700 -> 650 and EN 230 -> 270, shotgun 120 -> 112, plasma 700 -> 780, bazooka 1 800 -> 2 000;',
  '  pile bunker rate 0.2 -> 0.33, 4 200 -> 5 200, EN 450 -> 350, hit radius 170 -> 220; blade rate 0.67 -> 1.0, EN 300 -> 240, hit radius 180 -> 240,',
  '  default lunge time 0.25 -> 0.2 s (a longer 1 200 u melee lock range made blades worse); VM-6 470 per missile (was 420), speed 3 800 -> 4 300, turn 90 -> 120',
  '  (the hard AI missile two-step had it at 22 %). The AI chains only against missiles: chaining against every hard lock burned EN and lost rifle duels.',
  '- **Upgrade value** (third pass): an upgrade step costs floor(cost x caps.upgrade_cost_pct / 100) x (level + 1), pct 30 (was 100), to match the',
  '  flatter ladder; track rows show the tier (MK I-V) and a frame at MK V tints its aura with its accent colour (no stats). AC-Drum (92 %) is now a',
  '  shoulder cannon: 300 per shot (was 400), impact 100 (160), bipeds brace 0.2 s per shot (quads fire on the move). The anti-stomp duel is paired',
  '  (same seed, both orientations): the old 56 % no-upgrade floor was seed / side noise, the paired control reads 50 %. Flak then read 81 % and is',
  '  a braced shoulder cannon too (0.3 s, quads exempt): about 66 %. The shoulder table is 32 fights per entry, so +-9 % is noise.',
];

// ---------------------------------------------------------------------------------------------------------- families
const fams = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 112, 113, 114, 115, 116, 117, 118];
const MELEE = [107, 113, 118];
const famLo = (id) => `4,${id},${MELEE.includes(id) ? 101 : id},0,0,303,401,503,601`;   // a melee arm pairs with a rifle
const fam = new Map(fams.map((id) => [id, { w: 0, n: 0, ttk: 0, nk: 0, dps: 0 }]));
for (let i = 0; i < fams.length; i++) for (let j = i + 1; j < fams.length; j++) for (let s = 0; s < SEEDS; s++) for (let r = 0; r < REPS; r++) {
  const a = fams[i], b = fams[j], swap = r % 2 === 1;
  const d = duel(famLo(swap ? b : a), famLo(swap ? a : b), 'hard', 'hard', 100 + s * 31 + r * 7 + i * 13 + j);
  const A = fam.get(swap ? b : a), B = fam.get(swap ? a : b);
  A.n++; B.n++; A.dps += d.dpsA; B.dps += d.dpsB;
  if (d.win > 0) { A.w++; if (d.ttk) { A.ttk += d.ttk; A.nk++; } } else if (d.win < 0) { B.w++; if (d.ttk) { B.ttk += d.ttk; B.nk++; } } else { A.w += 0.5; B.w += 0.5; }
}
out.push('## 1v1 by weapon family', '', `Medium frame (White Glint), both arms the family (blade + rifle), GN-Reservoir, FCS-Brawler, AI tier hard, round robin, ${SEEDS} seed(s) x ${REPS} reps, sides swapped.`, '',
  '| Family | Win rate | Time to kill (s) | DPS dealt in fights | Catalogue DPS (one arm) |', '|---|---|---|---|---|');
const famRows = [];
for (const [id, s] of fam) {
  const p = byId.get(id);
  famRows.push({ key: p.key, wr: s.w / s.n });
  out.push(`| ${p.name} | ${pct(s.w / s.n)} | ${s.nk ? (s.ttk / s.nk).toFixed(1) : '-'} | ${(s.dps / s.n).toFixed(0)} | ${C.IF_Game.lib.IF_weaponDps(p, 0, P.caps).toFixed(0)} |`);
}
// ---------------------------------------------------------------------------------------------------------- shoulders
{
  const sh = [201, 202, 205, 206, 210, 211, 212, 213, 214];
  out.push('', '## Shoulder weapons', '', 'Medium frame, rifle + rifle, the shoulder in the right hand-point (nothing in the left), round robin, AI tier hard.', '', '| Shoulder | Win rate |', '|---|---|');
  const sw = new Map(sh.map((id) => [id, { w: 0, n: 0 }]));
  const lo = (id) => `4,101,101,${id},0,303,401,503,601`;
  for (let i = 0; i < sh.length; i++) for (let j = i + 1; j < sh.length; j++) for (let s = 0; s < SEEDS; s++) for (let r = 0; r < REPS; r++) {
    const swap = r % 2 === 1, a = swap ? sh[j] : sh[i], b = swap ? sh[i] : sh[j];
    const d = duel(lo(a), lo(b), 'hard', 'hard', 700 + s * 29 + r * 5 + i * 11 + j);
    const A = sw.get(a), B = sw.get(b); A.n++; B.n++;
    if (d.win > 0) A.w++; else if (d.win < 0) B.w++; else { A.w += 0.5; B.w += 0.5; }
  }
  for (const [id, x] of sw) { const p = byId.get(id); famRows.push({ key: p.key, wr: x.w / x.n }); out.push(`| ${p.name} | ${pct(x.w / x.n)} |`); }
}
// ---------------------------------------------------------------------------------------------------------- class x tier
out.push('', '## 1v1 by class and tier', '', 'Starter frames (Krasnaya light, White Glint medium, Ogre heavy) with rifle + shotgun + VM-6 + decoy, standard internals. Win rate of the row against the column.', '');
const cls = [['light', 1], ['medium', 4], ['heavy', 8]];
const clsLo = (f) => `${f},101,103,201,209,301,401,501,601`;
for (const tier of ['easy', 'normal', 'hard']) {
  out.push(`**Tier ${tier}**`, '', '| | ' + cls.map((c) => c[0]).join(' | ') + ' |', '|---|---|---|---|');
  for (const [an, af] of cls) {
    const row = [];
    for (const [bn, bf] of cls) {
      let w = 0, n = 0;
      for (let s = 0; s < SEEDS; s++) for (let r = 0; r < REPS; r++) { const d = duel(clsLo(af), clsLo(bf), tier, tier, 500 + s * 17 + r * 3 + af * 5 + bf); w += d.win > 0 ? 1 : d.win === 0 ? 0.5 : 0; n++; }
      row.push(an === bn ? '-' : pct(w / n));
    }
    out.push(`| ${an} | ${row.join(' | ')} |`);
  }
  out.push('');
}
// tier against tier, same build
{
  out.push('**Tier against tier** (medium starter build): ');
  const tiers = ['easy', 'normal', 'hard'], res = [];
  for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) {
    let w = 0, n = 0;
    for (let s = 0; s < SEEDS; s++) for (let r = 0; r < REPS * 2; r++) { const d = duel(clsLo(4), clsLo(4), tiers[j], tiers[i], 900 + s * 11 + r); w += d.win > 0 ? 1 : d.win === 0 ? 0.5 : 0; n++; }
    res.push(`${tiers[j]} beats ${tiers[i]} ${pct(w / n)}`);
  }
  out.push(res.join(', ') + '.', '');
}
// ---------------------------------------------------------------------------------------------------------- 8v8
out.push('## 8v8 family squads against the rifle', '', 'Eight mediums with the family in both arms against eight rifle mediums, AI normal, 90 s Team Battle, kills per side.', '', '| Family | Kills for | Kills against | Ratio |', '|---|---|---|---|');
for (const id of fams.filter((x) => x !== 101)) {
  let kf = 0, ka = 0;
  for (let s = 0; s < SEEDS; s++) {
    const specs = [];
    for (let i = 0; i < 16; i++) specs.push({ lo: famLo(i < 8 ? id : 101), tier: 'normal', team: i < 8 ? 2 : 3 });
    const r = fight(specs, 2000 + s * 13 + id, { secs: 90, gap: 5000 });
    kf += r.kills[2]; ka += r.kills[3];
  }
  out.push(`| ${byId.get(id).name} | ${kf} | ${ka} | ${(kf / Math.max(1, ka)).toFixed(2)} |`);
}
// ---------------------------------------------------------------------------------------------------------- anti-stomp
out.push('', '## Anti-stomp: a fully upgraded loadout against stock', '');
{
  const g = makeGame({ seed: 1 });
  const lo = '4,101,103,201,209,301,401,501,601', ids = lo.split(',').map(Number);
  const up = {}; for (const id of ids) up[id] = P.caps.levels;
  const maxed = { rank: 50, owned: new Set(ids), upgrades: up };
  const b0 = g.garage.budgets(lo, null), b5 = g.garage.budgets(lo, maxed);
  const apUp = b5.ap / b0.ap - 1, dpsUp = b5.dps / b0.dps - 1;
  const okAp = apUp <= P.caps.ap_pct / 100 + 1 / b0.ap, okDps = dpsUp <= P.caps.dps_pct / 100 + 0.005;   // budgets round DPS to whole numbers
  out.push(`Medium starter build, every part +${P.caps.levels}: AP ${b0.ap} -> ${b5.ap} (+${(apUp * 100).toFixed(1)} %, cap +${P.caps.ap_pct} %: ${okAp ? 'ok' : 'OVER'}), ` +
    `DPS ${b0.dps} -> ${b5.dps} (+${(dpsUp * 100).toFixed(1)} %, cap +${P.caps.dps_pct} %: ${okDps ? 'ok' : 'OVER'}).`);
  let w = 0, n = 0;
  // paired: every seed is fought in both orientations (the sides of the test arena are not equal; unpaired seeds read 56 % for a
  // rank-50 pilot with zero upgrades, paired reads 50 %); 24 fights per seed
  for (let s = 0; s < SEEDS; s++) for (let r = 0; r < REPS * 12; r++) {
    const side = r % 2, d = duel(lo, lo, 'normal', 'normal', 3000 + s * 97 + (r >> 1), side ? [null, maxed] : [maxed, null]);
    const mw = side ? -d.win : d.win; w += mw > 0 ? 1 : mw === 0 ? 0.5 : 0; n++;
  }
  out.push(`Duels, maxed vs stock (same AI tier, ${n} fights): the maxed pilot wins ${pct(w / n)}. The rookie shield (rank < 5 takes -20 % from rank >= 15) is on top of this in mixed lobbies.`);
  if (!okAp || !okDps) process.exitCode = 1;
}
// ---------------------------------------------------------------------------------------------------------- progression
// what a round pays (32 v 32 bots, Team Deathmatch to 150 kills) against what upgrade tracks cost (IF_upgradeCost, caps.upgrade_cost_pct)
{
  const g = makeGame({ seed: 5, cfg: { round: { tb: 600, warmup: 2, podium: 3 }, tb: { killMin: 150, killMax: 150 }, ai: { npcFill: false } } });
  g.setMode('tb', 0); g.startRound(0);
  for (let s = 0; s < 64; s++) g.addPlayer(s, { team: s % 2 ? 3 : 2, human: false, name: 'b' + s, pilot: null });
  let t = 0, end = false;
  for (let k = 0; k < 64 * 620 && !end; k++) { g.tick(DT, t += DT); for (const e of g.events) if (e.t === 'round_end') end = true; g.events.length = 0; }
  const cr = [...g.mechs.values()].filter((m) => m.slot < 64).map((m) => m.sum.credits).sort((a, b) => a - b), med = cr[cr.length >> 1];
  const lv = P.caps.levels, track = (p) => { let c = 0; for (let l = 0; l < lv; l++) c += C.IF_upgradeCost ? C.IF_upgradeCost(p, l, P.caps) : Math.floor(Math.max(p.cost || 0, P.caps.upgrade_floor_cost || 0) * (P.caps.upgrade_cost_pct || 100) / 100) * (l + 1); return c; };
  const perDay = 5 * med + 2100;   // 5 rounds plus 3 daily contracts (the plugin's default pool pays 400-1 200, about 700 each)
  out.push('', '## Progression: earn rate and upgrade costs', '',
    `One Team Deathmatch round, 32 v 32 AI pilots to 150 kills, lasted ${t.toFixed(0)} s and paid a median ${med} credits (range ${cr[0]}-${cr[cr.length - 1]}; XP x ${P.xp.credits_per_xp}). ` +
    `An upgrade step costs floor(part cost x ${P.caps.upgrade_cost_pct} %) x (level + 1), so a full track (MK I-V) is ${P.caps.upgrade_cost_pct * 15 / 100} x the part's price. ` +
    `"Regular" below is 5 rounds a day plus the 3 daily contracts (about 2 100 credits): ${perDay} credits a day.`, '',
    '| Part | Price | Full track (MK V) | Rounds to max | Regular days |', '|---|---|---|---|---|');
  for (const k of ['smg', 'gatling', 'burstrifle', 'bazooka', 'laser', 'autocannon', 'gen_high', 'bst_agile', 'stryder', 'supplice', 'sniper', 'heavyblade']) {
    const p = P.parts.find((x) => x.key === k); if (!p) continue;
    const full = track(p); out.push(`| ${p.name} | ${p.cost} | ${full} | ${Math.ceil(full / med)} | ${(full / perDay).toFixed(1)} |`);
  }
  out.push('', `Starter parts (price 0) upgrade as if they cost ${P.caps.upgrade_floor_cost || 0} (\`caps.upgrade_floor_cost\`, the cheapest paid part; 11 Nov 2026: they were free, and every part has the same track): a full track is ${track({ cost: 0 })} credits, ${Math.ceil(track({ cost: 0 }) / med)} rounds. The power on top is small by design (AP +5 %, DPS +3 % at MK V); a frame at MK V also wears its aura in the accent colour.`);
}
// ---------------------------------------------------------------------------------------------------------- findings
famRows.sort((a, b) => b.wr - a.wr);
const top = famRows[0], bottom = famRows[famRows.length - 1];
const head = ['# IRONFRAME balance tables', '', `Generated by \`node test/balance.cjs ${SEEDS} ${REPS}\` on the core sim (test arena, AI pilots) in ${((Date.now() - t0) / 1000).toFixed(0)} s. ` +
  'AI duels measure the rules plus the bots\' handling of each weapon, so read them as a smoke test for outliers, not as final balance; ' +
  'a family above about 75 % or below 25 % in the 1v1 round robin is flagged.', '',
  `Flags: ${famRows.filter((r) => r.wr > 0.75 || r.wr < 0.25).map((r) => r.key + ' ' + pct(r.wr)).join(', ') || 'none'} (best ${top.key} ${pct(top.wr)}, worst ${bottom.key} ${pct(bottom.wr)}).`, ''];
const notes = NOTES.length ? ['', '## Tuning notes', ''].concat(NOTES) : [];
fs.writeFileSync(path.join(ROOT, 'docs', 'BALANCE.md'), head.concat(out, notes).join('\n') + '\n');
console.log(head.concat(out).join('\n'));
