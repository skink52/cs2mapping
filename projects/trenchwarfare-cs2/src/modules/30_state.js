// 30_state: per-player records, mortar crews, shells in flight, counters

// ------------------------------------------------------------------ state
const players = new Map();   // slot -> P
let genNext = 1;             // a new number for every new player record: credit checks that a slot still holds the same player
function P(slot) {
  let p = players.get(slot);
  if (!p) {
    p = { slot, gen: genNext++, role: null, team: 0, crew: -1, seat: "", deployAt: 0, deployed: false, first: true, streak: 0, kills: 0, upgraded: false,
          pref: "", carrying: false, inSight: false, u: 0.5, v: 0.3, prevKeys: 0, lives: 0, merit: 0, flown: 0, toastUntil: 0, bannerUntil: 0, infoUntil: 0,
          healing: false, mortarKills: 0, hud: new Map(), uniformAt: 0, uniformDone: false, noUniform: false, stockModel: "",
          bot: false, sane: false, lastActive: 0, lastEye: undefined, sortie: false, firedAt: -99,
          aiRole: "", aiFly: undefined, anchor: undefined, outT: 0, checkAt: 0, lastCombat: -99 };
    players.set(slot, p);
    hudReset(p);             // a slot that changed hands must not keep the last player's HUD classes
  }
  return p;
}
const crews = { [T]: [], [CT]: [] };
function resetCrews() {
  for (const team of [T, CT]) {
    crews[team] = [];
    for (let k = 0; k < CONFIG.CREWS; k++) crews[team].push({ a: -1, b: -1, loaded: false, loader: -1, loaderGen: 0, target: null, cooldown: 0, impacts: [], ai: undefined });
  }
}
resetCrews();
const shells = [];           // in flight
// counters: the per-minute perf line, the mock's coverage table and the balance report read them (globalThis.__twDebug)
const stats = { killsBy: {}, killsByTeam: {}, deploys: { infantry: 0, mortar: 0, air: 0 }, shots: 0, impacts: 0, assistShares: 0, bombs: 0, crashes: 0, unlocks: 0,
                heals: 0, upgrades: 0, swaps: 0, leash: 0, uniforms: 0, ambient: 0, deferred: 0, afk: 0, sanitised: 0, reloads: 0, blocked: 0,
                crewDeaths: 0, perfLines: 0, errors: 0, sightLocks: 0, loads: 0, planeHits: 0, teamLeft: 0, flights: 0, stows: 0, gunHits: 0, gunRounds: 0,
                // bots (85_ai): where infantry bots were sent, why the out-of-play leash moved one, the script-run roles and hand-overs
                botDeploys: { fire: 0, support: 0, area: 0 }, botLeash: { nml: 0, lobby: 0, far: 0, lock: 0 },
                aiPilots: 0, aiSorties: 0, aiGunRounds: 0, aiBombs: 0, aiCrews: 0, aiShots: 0, aiReleased: { humans: 0, yield: 0, trim: 0, lives: 0, lost: 0 },
                yields: { air: 0, seat: 0 } };
try { globalThis.__twDebug = { players, crews, shells, stats, CONFIG }; } catch (e) {}
let poolIdx = 0;
