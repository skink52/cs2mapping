// Checks the 1.6 rules (src/core) against numbers from 1.6 itself. usage: node tools/build.mjs && node test/core_test.cjs
const C = require('../build/core_test.cjs');
let fails = 0;
function eq(name, got, want, tol = 0.01) {
  const norm = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? Object.keys(v).sort().map((k) => [k, v[k]]) : v);
  const ok = typeof want === 'number' ? Math.abs(got - want) <= tol : JSON.stringify(norm(got)) === JSON.stringify(norm(want));
  if (!ok) { fails++; console.log('FAIL', name, 'got', got, 'want', want); }
}
const W = C.WEAPONS;
// damage at point blank: 1.6 base x hit group
eq('ak47 chest', C.bulletDamage16(W.ak47, false, 0, 2), 36);
eq('ak47 head', C.bulletDamage16(W.ak47, false, 0, 1), 144);
eq('ak47 leg', C.bulletDamage16(W.ak47, false, 0, 6), 27);
eq('m4a1 silenced', C.bulletDamage16(W.m4a1, true, 0, 2), 33);
eq('ak47 at 1000u', C.bulletDamage16(W.ak47, false, 1000, 2), 36 * 0.98 * 0.98);
eq('m3 pellet at 1500u', C.bulletDamage16(W.m3, false, 1500, 2), 10);
eq('m3 pellet past range', C.bulletDamage16(W.m3, false, 4000, 2), 0);
// armour: AK into a vest: health 36 x 0.775, armour loses (36 - 27.9) / 2
let r = C.armorAbsorb(36, 100, W.ak47.armor, true, false);
eq('ak47 vs vest health', r.health, 27.9); eq('ak47 vs vest armour', r.armor, 100 - 4.05);
r = C.armorAbsorb(144, 2, W.ak47.armor, true, false);
eq('vest runs out (bullet): damage - 2 x armour', r.health, 140); eq('vest gone', r.armor, 0);
r = C.armorAbsorb(80, 5, 1, true, true);
eq('vest runs out (blast): damage - armour', r.health, 75);
eq('head needs helmet', C.isArmored(1, false), false); eq('legs never armoured', C.isArmored(6, true), false);
eq('he at 0', C.blastDamage16(100, 0), 100); eq('he at 175', C.blastDamage16(100, 175), 50); eq('he at 400', C.blastDamage16(100, 400), 0);
eq('c4 500 at 875', C.blastDamage16(500, 875), 250);
eq('fall 500', C.fallDamage16(500), 0); eq('fall 800', C.fallDamage16(800), 62.5);
eq('knife stab back', C.knifeDamage16(true, false, true), 195); eq('knife slash chained', C.knifeDamage16(false, true, false), 15);
// money
eq('bombed', C.teamRewards({ winner: 2, reason: 'bombed' }), { 2: 3500, 3: 0 });
eq('defused', C.teamRewards({ winner: 3, reason: 'defused' }), { 2: 800, 3: 3250 });
const lb = new C.LossBonus();
eq('loss 1', lb.apply(3), 1400); eq('loss 2', lb.apply(3), 1900); eq('loss 3', lb.apply(3), 2400); eq('loss 4', lb.apply(3), 2900);
eq('loss 5', lb.apply(3), 3400); eq('streak broken', lb.apply(2), 1500);
// buying
const inv = { team: 2, money: 2600, primary: null, secondary: 'glock18', armor: 0, helmet: false, defuser: false, nades: {}, primaryAmmo: null, secondaryAmmo: null };
eq('buy ak', C.planPurchase(inv, 'ak47').ok, true);
eq('T cannot buy m4', C.planPurchase(inv, 'm4a1').ok, false);
eq('too poor for awp', C.planPurchase(inv, 'awp').msg, 'You have insufficient funds!');
eq('helmet only', C.planPurchase({ ...inv, armor: 100 }, 'vesthelm').price, 350);
// splitting 64 players over 3 maps
const cfg = { MAPS_BY_PLAYERS: [[0, 1], [25, 2], [45, 3]], MAP_ORDER: ['dust2', 'train', 'nuke'] };
eq('maps for 10', C.mapCountFor(5, 5, cfg), 1); eq('maps for 30', C.mapCountFor(15, 15, cfg), 2); eq('maps for 64', C.mapCountFor(32, 32, cfg), 3);
eq('maps limited by smaller team', C.mapCountFor(40, 2, cfg), 2);
const ev = []; for (let i = 0; i < 64; i++) ev.push({ slot: i, team: i % 2 ? 3 : 2, prev: null, want: i === 3 ? 'nuke' : null });
const plan = C.assignMaps(ev, ['dust2', 'train', 'nuke']);
const cnt = {}; for (const p of ev) { const k = plan.get(p.slot) + p.team; cnt[k] = (cnt[k] || 0) + 1; }
eq('split', cnt, { dust22: 11, dust23: 11, train2: 11, train3: 11, nuke2: 10, nuke3: 10 });
eq('request honoured', plan.get(3), 'nuke');
// round results
const mr = new C.MapRound('dust2'); mr.start(5, 5);
eq('all CT dead', mr.check(3, 0, false), true); eq('T elim', mr.result, { winner: 2, reason: 'elim' });
const m2 = new C.MapRound('train'); m2.start(5, 5); m2.plant('A', 10, 45);
eq('Ts dead but bomb planted: on', m2.check(0, 3, true), false);
m2.defuse(); eq('defused', m2.result, { winner: 3, reason: 'defused' });
eq('two maps split = draw', C.overallResult([mr, m2]), { winner: 0, reason: 'draw' });
console.log(fails ? fails + ' failed' : 'core rules: all checks passed');
process.exit(fails ? 1 : 0);
