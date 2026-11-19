// Player boss check on every ZE level (no CS2): bots play to the boss stage (forced), a zombie player takes the boss
// over, drives it (moves, ATTACK, ATTACK2) for 6 s, hands it back to the AI, takes it again and is killed by a human.
// Checks: the body runs on its own player states (never an AI action), its missile is the boss's own, health carries
// over both ways, the stage stays active through the hand-back and ends on the kill, the kill credits the human.
//   node test/boss_check.cjs [core module=test/out/hellescape_core.cjs]
const path = require('path');
const C = require(path.resolve(process.argv[2] || path.join(__dirname, 'out/hellescape_core.cjs')));
let s0 = 5 >>> 0;
Date.now = () => 1790000000000;
Math.random = () => { s0 = (s0 + 0x6D2B79F5) >>> 0; let t = s0; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const bases = [...new Set(C.LEVELS.filter((L) => L.ze && L.side).map((L) => L.base))];
let fails = 0;
const bad = (m) => { console.log('  PROBLEM ' + m); fails++; };
for (const base of bases) {
  const cfg = JSON.parse(JSON.stringify(C.DEFAULT_CFG));
  cfg.ze.map = base;
  const rm = new C.ZeRound(C.LEVELS, cfg);
  for (let i = 0; i < 12; i++) rm.addPerson(i, 'bot' + i, i % 2 ? 3 : 2, true);
  if (!rm.startRound()) { bad(base + ': round did not start'); continue; }
  const tic = (n, fn) => { for (let i = 0; i < n && rm.state === 'running'; i++) { if (fn) fn(); rm.tic(900); for (const a of rm.arenas) a.events.length = 0; rm.events.length = 0; } };
  // god mode for every human so neither side is wiped while we test
  const god = () => { for (const a of rm.arenas) for (const p of a.players.values()) if (!p.zclass) p.powers[0] = 1 << 20; };
  tic(35 * 6, god);
  const a = rm.arenas.find((x) => x.zeSide === 2), ze = a.ze;
  // a zombie player in the T arena: kill a CT human bot and wait for it to rise
  const ctA = rm.arenas.find((x) => x.zeSide === 3);
  const victim = [...ctA.players.values()].find((p) => !p.zclass && p.playerstate === 'live');
  ctA.run(() => C.damageMobj(victim.mo, null, null, 10000));
  let z = null;
  for (let i = 0; i < 35 * 15 && !z; i++) { tic(1, god); z = [...a.players.values()].find((p) => p.zclass && p.playerstate === 'live' && p.person && p.person.slot === victim.slot); }
  if (!z) { bad(base + ': no zombie player rose in the T arena'); continue; }
  // force the boss stage
  const bs = ze.stages.find((s) => s.d.boss);
  a.run(() => { for (const s of ze.stages) if (s.i < bs.i) ze.finishStage(s); });
  if (bs.d.start && bs.d.start.line_crossed !== undefined) ze.crossed.add(bs.d.start.line_crossed);
  tic(3, god);
  if (bs.state !== 'active' || !ze.boss) { bad(`${base}: boss stage not up (${bs.state})`); continue; }
  const type = ze.boss.info.key, hp0 = ze.boss.health;
  if (!ze.offer) bad(`${base}: ${type} not offered`);
  z.isBot = false; z.person.bot = false;   // a person now (bots never take a boss); driven by this script
  if (!ze.bossEligible(z)) bad(`${base}: zombie not eligible`);
  if (!ze.takeOver(z, 'test')) { bad(`${base}: takeover of ${type} failed`); continue; }
  const cls = C.ZCLASS[z.zclass];
  const body = z.mo;
  const actions = new Set(), sprites = new Set();
  let missiles = 0;
  const seenMissiles = new Set();
  z.person.lastActive = rm.time;
  tic(35 * 6, () => {
    god(); z.person.lastActive = rm.time;
    z.cmd.forwardmove = 50; z.cmd.angle = (z.cmd.angle + 3) % 360;
    z.cmd.buttons = (rm.time % 70 < 35 ? C.BT_ATTACK : 0) | (rm.time % 70 >= 35 ? 4 : 0);
    if (z.mo) { const st = C.STATES[z.mo.state]; sprites.add(st.sprite); if (st.action) actions.add(st.action); }
    for (const m of a.mobjs) if (m.target === z.mo && m.info.kind === 'missile' && !seenMissiles.has(m)) { seenMissiles.add(m); if (m.info.key === cls.missile) missiles++; }
  });
  if (z.mo !== body || body.health <= 0) bad(`${base}: the boss body died while driven`);
  for (const act of actions) if (act !== 'A_Pain') bad(`${base}: player boss body ran AI action ${act}`);
  if (!missiles) bad(`${base}: no ${cls.missile} from the player ${type}`);
  if (body.health > hp0) bad(`${base}: health grew ${hp0} -> ${body.health}`);
  const hpBody = body.health;
  // idle -> the AI takes it back
  z.person.lastActive = rm.time - rm.zcfg.bossAfkTics - 2;
  tic(2, god);
  const ai = [...a.mobjs].filter((m) => m.info.kind === 'monster' && m.boss && m.health > 0);
  if (ze.bossPlayer || ai.length !== 1 || ai[0].info.key !== type || ze.boss !== ai[0]) bad(`${base}: AI did not take the ${type} back (${ai.length})`);
  else if (ai[0].health !== hpBody) bad(`${base}: AI boss health ${ai[0].health} != body ${hpBody}`);
  if (bs.state !== 'active') bad(`${base}: stage ended on the hand-back`);
  tic(35 * 3, () => { god(); z.person.lastActive = rm.time; });
  if (z.playerstate !== 'live' || C.ZCLASS[z.zclass].boss) bad(`${base}: ex-boss player not back as a zombie (${z.playerstate} ${z.zclass})`);
  // again, and a human kills it
  ze.offer = { until: a.leveltime + 175, opted: new Map() };
  if (!ze.takeOver(z, 'test')) { bad(`${base}: second takeover failed`); continue; }
  const human = [...a.players.values()].find((p) => !p.zclass && p.playerstate === 'live');
  const kills = [];
  a.run(() => C.damageMobj(z.mo, human.mo, human.mo, 100000));
  for (const e of a.events) if (e.type === 'kill' || e.type === 'monsterKill') kills.push(e);
  tic(2, god);
  const k = kills.find((e) => e.type === 'kill'), mk = kills.find((e) => e.type === 'monsterKill');
  if (!k || k.killer !== human || k.victim !== z) bad(`${base}: kill event does not credit the human`);
  if (!mk || !mk.boss || mk.killer !== human) bad(`${base}: no boss monsterKill for the human`);
  if (bs.state !== 'done') bad(`${base}: boss stage not done after the kill (${bs.state})`);
  console.log(`${base}: ${type} (${cls.name}) hp ${hp0}, driven 6 s: sprites ${[...sprites].join('/')}, ${missiles} x ${cls.missile}, body ${hpBody} -> AI ${ai[0] ? ai[0].health : '-'} -> retaken -> killed by ${human.name}: stage ${bs.state}`);
}
console.log(fails ? `boss_check: PROBLEMS ${fails}` : `boss_check: OK (${bases.length} levels)`);
process.exit(fails ? 1 : 0);
