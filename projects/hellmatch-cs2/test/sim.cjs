const C = require('../build/core_test.cjs');
const cfg = JSON.parse(JSON.stringify(C.DEFAULT_CFG));
if (process.env.MONSTERS) cfg.monsterChance = +process.env.MONSTERS;   // MONSTERS=1: every deathmatch arena gets monsters
const N = +(process.argv[2] || 12), ROUNDS = +(process.argv[3] || 3), MODE = process.argv[4];
const rm = new C.RoundManager(C.LEVELS, cfg);
for (let i = 0; i < N; i++) rm.addPerson(i, 'bot' + i, i % 2 ? 3 : 2, true);
const t0 = Date.now();
let totalTics = 0;
for (let r = 0; r < ROUNDS; r++) {
  rm.startRound(MODE);
  const desc = rm.arenas.map((a) => `${a.mapId}:${a.modeKey}:${a.players.size}p:target${a.target}${a.loadout ? ':' + a.loadout : ''}`).join(' ');
  let kills = 0, pickups = 0, sounds = 0, msgs = 0; const sndCount = {};
  const kinds = {};
  let tics = 0;
  while (rm.state === 'running' && tics < 35 * 600) {
    rm.tic(600 - (tics + 1) / 35);
    tics++;
    for (const a of rm.arenas) {
      for (const e of a.events) {
        if (e.type === 'kill') { kills++; kinds[e.kind] = (kinds[e.kind] || 0) + 1; }
        if (e.type === 'monsterKill') { kinds.monsterKills = (kinds.monsterKills || 0) + 1; if (e.boss) kinds.bossKills = (kinds.bossKills || 0) + 1; }
        if (e.type === 'wave' || e.type === 'bossWave' || e.type === 'bossDown') kinds[e.type + (e.wave || '')] = (kinds[e.type + (e.wave || '')] || 0) + 1;
        if (e.type === 'sound') { sounds++; sndCount[e.sfx] = (sndCount[e.sfx] || 0) + 1; }
        if (e.type === 'msg') msgs++;
      }
      a.events.length = 0;
    }
    rm.events.length = 0;
  }
  totalTics += tics;
  const res = rm.arenas.map((a) => (a.result && a.result.text) + ' @' + Math.round(a.finishedAt / 35) + 's' + (a.result && a.result.timeout ? ' (time)' : '')).join(' | ');
  console.log('  top sounds', JSON.stringify(Object.entries(sndCount).sort((a,b)=>b[1]-a[1]).slice(0,5)));
  console.log(`round ${r + 1}: ${desc}\n  ${(tics / 35).toFixed(0)}s kills=${kills} msgs=${msgs} sounds=${sounds} -> ${res}\n  ${JSON.stringify(kinds)}`);
}
const ms = Date.now() - t0;
console.log(`sim ${totalTics} tics in ${ms} ms -> ${(ms / totalTics).toFixed(3)} ms per tic for ${N} players`);
