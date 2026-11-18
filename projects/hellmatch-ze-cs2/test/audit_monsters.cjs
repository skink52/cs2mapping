// Monster audit: runs Boss Battle (or deathmatch + monsters) on every level with bots and reports the failure
// classes met before: things in or outside walls, stuck or idle AI, floating, spawn failures, HUD text too long,
// slow tics.  usage: node test/audit_monsters.cjs [boss|dm] [bots] [seconds] [mapId...]
const C = require('../build/core_test.cjs');
const MODE = process.argv[2] || 'boss', N = +(process.argv[3] || 8), SECS = +(process.argv[4] || 480);
const only = process.argv.slice(5);
const maps = C.LEVELS.filter((L) => !only.length || only.includes(L.id));
const STATES = C.STATES;
const MF_FLOAT = 0x4000, MF_NOGRAVITY = 512;

function audit(L) {
  const cfg = JSON.parse(JSON.stringify(C.DEFAULT_CFG));
  if (MODE === 'dm') cfg.monsterChance = 1;
  const rm = new C.RoundManager([L], cfg);
  for (let i = 0; i < N; i++) rm.addPerson(i, 'bot' + i, i % 2 ? 3 : 2, true);
  rm.startRound(MODE === 'boss' ? 'boss' : 'ffa');
  const a = rm.arenas[0], d = a.director;
  const r = { map: L.id, mode: a.modeKey, area: Math.round((L.bb[2] - L.bb[0]) * (L.bb[3] - L.bb[1]) / 1e6 * 10) / 10,
    spawnFail: 0, unstick: 0, outside: 0, inWall: 0, floating: 0, stuckSec: 0, idleSec: 0, maxAlive: 0, mkills: 0, pdeaths: 0,
    botStuckSec: 0, hudLong: new Set(), maxTicMs: 0, slowTics: 0, spawned: 0, telefrag: 0, offFloor: 0, ledge: 0 };
  if (d) {
    const os = d.spawn.bind(d);
    d.spawn = (t, o) => { const mo = os(t, o); if (!mo) r.spawnFail++; else r.spawned++; return mo; };
    // AUDIT_BOSS=cyber|twin|spider|swarm|lords: that boss whenever it can be placed
    const op = d.planBoss.bind(d);
    if (process.env.AUDIT_BOSS) d.planBoss = (n) => { let p; for (let i = 0; i < 40; i++) { p = op(n); if (p.kind === process.env.AUDIT_BOSS) break; } return p; };
    const ou = d.unstick.bind(d);
    d.unstick = () => { const before = r.spawned; ou(); r.unstick += r.spawned - before; };
  }
  const track = new Map();   // mobj id -> { x, y, since, state }
  let tics = 0;
  while (rm.state === 'running' && tics < 35 * SECS) {
    const t0 = process.hrtime.bigint();
    rm.tic(600 - tics / 35); tics++;
    const ms = Number(process.hrtime.bigint() - t0) / 1e6;
    if (ms > r.maxTicMs) r.maxTicMs = ms;
    if (ms > 16) r.slowTics++;
    for (const e of a.events) {
      if (e.type === 'monsterKill') { r.mkills++; if (a.damageCtx === 'telefrag') r.telefrag++; }
      if (e.type === 'kill') r.pdeaths++;
    }
    a.events.length = 0; rm.events.length = 0;
    if (tics % 35 !== 0) continue;
    // once a second: look at every live monster
    const bb = L.bb;
    const players = [...a.players.values()].filter((p) => p.mo && !p.mo.removed && p.playerstate === 'live');
    let alive = 0;
    a.run(() => {
      for (const m of a.mobjs) {
        if (m.info.kind !== 'monster' || m.health <= 0) continue;
        alive++;
        if (m.x < bb[0] - 8 || m.y < bb[1] - 8 || m.x > bb[2] + 8 || m.y > bb[3] + 8) {
          r.outside++;
          if (process.env.AUDIT_VERBOSE && r.outside <= 3) console.log(`  outside: t=${tics / 35} ${m.info.key} @${m.x | 0},${m.y | 0} z${m.z | 0} bb ${bb.join(',')} ${STATES[m.state].name} boss=${!!m.boss} flags ${m.flags.toString(16)}`);
        }
        // in a wall: a line blocks at its own position (things ignored)
        C.checkPositionProbe(m, m.x, m.y);   // the thing itself: it is skipped in the thing check
        if (C.TM.blockline) {
          r.inWall++;
          if (process.env.AUDIT_VERBOSE && r.inWall <= 3) { const bl = C.TM.blockline; console.log(`  in wall: t=${tics / 35} ${m.info.key} @${m.x.toFixed(1)},${m.y.toFixed(1)} z${m.z} r${m.radius} sec${m.sector.id} ${STATES[m.state].name} boss=${!!m.boss} line ${bl.id} (${bl.x1},${bl.y1})-(${bl.x2},${bl.y2}) flags ${bl.flags} 2s=${!!bl.backsector}`); }
        }
        if (C.TM.floorz - m.sector.floorheight > 24) r.ledge = (r.ledge || 0) + 1;
        if (!(m.flags & (MF_FLOAT | MF_NOGRAVITY)) && m.z > m.floorz + 4) r.floating++;
        if (!(m.flags & (MF_FLOAT | MF_NOGRAVITY)) && m.z < m.floorz - 1) r.offFloor++;
        const st = STATES[m.state].name;
        let tr = track.get(m.id);
        if (!tr) { tr = { x: m.x, y: m.y, since: tics, idle: 0 }; track.set(m.id, tr); }
        const moved = Math.hypot(m.x - tr.x, m.y - tr.y);
        if (moved > 24) { tr.x = m.x; tr.y = m.y; tr.since = tics; }
        // stuck: alive, chasing something out of melee range, not moved 24 units in 10 s
        const tgt = m.target && !m.target.removed && m.target.health > 0 ? m.target : null;
        const far = tgt ? Math.hypot(tgt.x - m.x, tgt.y - m.y) > 96 : false;
        if (tgt && far && tics - tr.since > 10 * 35 && !/ATK|PAIN|DIE/.test(st)) r.stuckSec++;
        // idle: still in its spawn state (never saw anyone) 20 s after arriving while players live
        if (m.state === m.info.spawnstate && players.length && tics - (m.spawnTic || (m.spawnTic = tics)) > 20 * 35) r.idleSec++;
      }
      for (const p of a.players.values()) {
        if (!p.mo || p.mo.removed || p.playerstate !== 'live' || p.frozen) continue;
        let tr = track.get('p' + p.slot);
        if (!tr) { tr = { x: p.mo.x, y: p.mo.y, since: tics }; track.set('p' + p.slot, tr); }
        if (Math.hypot(p.mo.x - tr.x, p.mo.y - tr.y) > 24) { tr.x = p.mo.x; tr.y = p.mo.y; tr.since = tics; }
        else if (tics - tr.since > 5 * 35) r.botStuckSec++;
      }
    });
    if (alive > r.maxAlive) r.maxAlive = alive;
    // HUD lines as the CS2 side would build them (32 slots for the top-right lines, 24 for the centre)
    if (d) {
      const line1 = (d.wave >= d.cfg.waves ? 'BOSS' : d.wave > 0 ? `WAVE ${d.wave} OF ${d.cfg.waves}` : 'BOSS BATTLE') + ' - 8:00';
      const line2 = (d.wave >= d.cfg.waves ? `${d.left()} TO KILL` : `${d.left()} MONSTERS`) + '  LIVES 3';
      if (line1.length > 32) r.hudLong.add(line1); if (line2.length > 32) r.hudLong.add(line2);
    }
  }
  r.secs = Math.round(tics / 35); r.result = a.result ? a.result.text : 'running'; r.wave = d ? d.wave : '-'; r.boss = d && d.bossPlan ? d.bossPlan.name : '-';
  r.hudLong = [...r.hudLong];
  return r;
}

const rows = [];
for (const L of maps) {
  const r = audit(L);
  rows.push(r);
  console.log(`${r.map} ${String(r.area).padStart(5)}M ${r.mode} ${String(r.secs).padStart(3)}s wave ${r.wave} ${r.boss.padEnd(18)} ${r.result.padEnd(34)} spawned ${String(r.spawned).padStart(3)} fail ${r.spawnFail} unstick ${r.unstick} maxAlive ${r.maxAlive} | out ${r.outside} wall ${r.inWall} ledge ${r.ledge} float ${r.floating} below ${r.offFloor} stuck ${r.stuckSec}s idle ${r.idleSec}s botStuck ${r.botStuckSec}s | mk ${r.mkills} pd ${r.pdeaths} | tic max ${r.maxTicMs.toFixed(1)}ms slow ${r.slowTics}${r.hudLong.length ? ' HUDLONG ' + r.hudLong.join('|') : ''}`);
}
const sum = (k) => rows.reduce((t, r) => t + r[k], 0);
console.log(`TOTAL maps ${rows.length}: spawnFail ${sum('spawnFail')} unstick ${sum('unstick')} outside ${sum('outside')} inWall ${sum('inWall')} ledge ${sum('ledge')} floating ${sum('floating')} below ${sum('offFloor')} stuck ${sum('stuckSec')}s idle ${sum('idleSec')}s botStuck ${sum('botStuckSec')}s slowTics ${sum('slowTics')} maxTic ${Math.max(...rows.map((r) => r.maxTicMs)).toFixed(1)}ms`);
if (MODE === 'boss') {
  console.log('results:', rows.map((r) => r.result.split(' ')[0]).reduce((o, k) => (o[k] = (o[k] || 0) + 1, o), {}));
  const by = {}; for (const r of rows) { const k = r.boss; by[k] = by[k] || {}; const res = r.result.split(' ')[0]; by[k][res] = (by[k][res] || 0) + 1; }
  console.log('by boss:', JSON.stringify(by));
}
