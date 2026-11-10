// The extended round statistics the map sends to the server (src/cs2/70_server.js srvRoundStats; SERVER_CONTRACT.md section 2b):
// every name fits the plugin's stat column ([a-z0-9_], at most 32), none but mech_wins looks like a win stat, zero values are not sent.
// usage: node test/server_stats.cjs
const fs = require('fs'), path = require('path'), vm = require('vm');
const { C } = require('./lib.cjs');
const src = fs.readFileSync(path.join(__dirname, '..', 'src', 'cs2', '70_server.js'), 'utf8');
const fn = src.match(/function srvRoundStats\(slot, won\) \{[\s\S]*?\n\}/)[0];
let fails = 0, n = 0;
const ok = (c, name, info) => { n++; if (!c) { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } };
const P = C.PARTS, frames = P.parts.filter((p) => p.kind === 'frame'), weapons = P.parts.filter((p) => p.kind === 'arm' || p.kind === 'shoulder');
for (const mode of ['tb', 'cq', 'kh', 'ctf', 'sk', 'so']) for (const fr of frames) {
  const sent = [];
  const w = {}; for (const p of weapons) w[p.key] = { kills: 3, damage: 123456 };
  const sb = { game: { pilotStats: () => ({ mode, frame: fr.key, won: true, kills: 7, damage: 654321, shots: 900, hits: 400, qb: 30, mslFired: 48, dodges: 5, staggers: 4, od: 1, crates: 2,
    flagReturns: 1, dmgTaken: 54321, lifeBest: 187, weapons: w }) }, ifrStatLater: (slot, k, v) => { if (v > 0) sent.push([k, v]); } };
  vm.createContext(sb); vm.runInContext(fn + '; srvRoundStats(3, true);', sb);
  for (const [k, v] of sent) {
    ok(/^[a-z0-9_]{1,32}$/.test(k), 'stat name fits the column', k);
    ok(Number.isInteger(v) && v > 0, 'whole positive value', k + ' ' + v);
    ok(k === 'mech_wins' || !(/_wins$/.test(k) || /^wins_/.test(k)), 'not a win-marking name', k);
  }
  const names = new Set(sent.map((x) => x[0]));
  ok(names.size === sent.length, 'no name twice in a round', sent.length - names.size);
  ok(names.has('mech_' + mode + '_rounds') && names.has('mech_won_' + mode) && names.has('mech_f_' + fr.key + '_rounds') && names.has('mech_w_rifle_kills') && names.has('best_life_s'), 'mode, frame, weapon and best stats present');
}
{ // nothing happened: only the rounds played
  const sent = []; const sb = { game: { pilotStats: () => ({ mode: 'tb', frame: 'atlas', won: false, kills: 0, damage: 0, shots: 0, hits: 0, qb: 0, mslFired: 0, dodges: 0, staggers: 0, od: 0, crates: 0, flagReturns: 0, dmgTaken: 0, lifeBest: 0, weapons: {} }) },
    ifrStatLater: (slot, k, v) => { if (v > 0) sent.push(k); } };
  vm.createContext(sb); vm.runInContext(fn + '; srvRoundStats(3, false);', sb);
  ok(sent.join() === 'mech_tb_rounds,mech_f_atlas_rounds', 'an idle round sends only the two round counters', sent.join());
}
console.log((fails ? 'FAIL ' + fails + ' of ' : 'ok: ') + n + ' checks (round statistics names and values)');
process.exit(fails ? 1 : 0);
