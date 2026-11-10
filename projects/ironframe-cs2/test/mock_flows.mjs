// Scripted flows for the mock engine (create/test/mock_point_script.mjs scenario=test/mock_flows.mjs): one human (slot 0) drives the
// screens by chat and keys while the other players run at random. Checks the Nov 2026 playtest bugs:
//  - `!spec` then `!garage` (and every order of !spec / !garage / !back / sortie) ends in the garage with the hangar camera, then back in a mech;
//  - a round end while the garage is open: the podium shows (cards filled from the round's scores), the next round starts and the player is
//    piloting again without pressing anything;
//  - the round flow never stalls on the podium (round 2 starts; the HUD leaves stPodium);
//  - the pawn is alive whenever the garage is open (a dead pawn shows CS2's observer view, not the hangar camera);
//  - two arm picks in the garage fill R, then L.
// FLOW_NORESTART=1 runs it with a CS2 that ends round 1 but never starts round 2 (the script's RESTART_WAIT fallback).
// usage (tools/mock_flows.sh builds the short-round script and runs both):
//   node ../../create/test/mock_point_script.mjs build/ironframe_flows.js <entities.json> players=6 seconds=150 scenario=test/mock_flows.mjs hud=<layout.xml>
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const HUD = JSON.parse(fs.readFileSync(path.join(ROOT, 'out', 'addon', '_gen', 'hud.json'), 'utf8'));
const ROOTP = HUD.root;
const ME = 0;
const fails = [], seen = [];
let api = null;
const bays = [];

// the text a HUD text slot shows for a player: the dialog variable `v` of the slot's Label (one id per text since the panel-id cap, 10 Nov 2026)
function text(slot, name) { return String(api.hudVar(slot, HUD.text_slots[name].panel, 'v') || '').replace(/\u00a0/g, ' ').trim(); }
function screen(slot) { const s = api.hud(slot, ROOTP); return ['stFight', 'stSpec', 'stDeath', 'stIntro', 'stPodium', 'stGarage'].filter((c) => s.has(c)).join('+') || (s.has('stOn') ? 'on' : 'off'); }
function camMode(slot) { const p = api.pawn(slot); return p && p.cam ? p.cam.mode : -1; }
function camPos(slot) { const p = api.pawn(slot); return p && p.cam ? p.cam._p : null; }
const CM = () => api.ENUMS.CustomCameraMode;

// the timeline: [second, action] (actions run once at that second); `expect` checks run at their second
const steps = [];
const at = (t, what, fn) => steps.push({ t, what, fn, done: false });
const tap = (mask) => () => { api.keys(ME, mask); };
let state = {};
function expectScreen(t, want, what) {
  at(t, 'expect ' + want + ' (' + what + ')', () => { const s = screen(ME); seen.push(t + 's ' + s); if (!s.split('+').includes(want)) fails.push(`${what}: at ${t} s the screen is ${s}, expected ${want}`); });
}
function expectGarageCam(t, what) {
  at(t, 'expect hangar camera (' + what + ')', () => {
    const m = camMode(ME), p = camPos(ME);
    if (m !== CM().CONTROLLED) { fails.push(`${what}: camera mode ${m}, expected CONTROLLED`); return; }
    if (!bays.length) return;
    const d = Math.min(...bays.map((b) => Math.hypot(b[0] - p.x, b[1] - p.y, b[2] - p.z)));
    if (d > 2000) fails.push(`${what}: the camera is ${Math.round(d)} u from the nearest hangar bay (not in the hangar)`);
  });
}
function expectFollow(t, what) { at(t, 'expect follow camera (' + what + ')', () => { if (camMode(ME) !== CM().FOLLOW_POSITION) fails.push(`${what}: camera mode ${camMode(ME)} at ${t} s, expected FOLLOW_POSITION (piloting)`); }); }
// garage keys: W (FORWARD) from the first tab wraps to SORTIE, Space (JUMP) launches
function sortie(t) { at(t, 'W', tap(api.IN.FORWARD)); at(t + 0.1, 'release', tap(0)); at(t + 0.3, 'SPACE', tap(api.IN.JUMP)); at(t + 0.4, 'release', tap(0)); }

export default {
  setup(a) {
    api = a; api.manual.add(ME);
    const ents = JSON.parse(fs.readFileSync(process.env.IF_FLOW_ENTS || path.join(ROOT, 'out', 'addon', '_gen', 'entities.json'), 'utf8'));
    for (const e of ents) if (/^ifr_bay_\d+$/.test(e.name || e.targetname || '')) bays.push(e.origin);
    // round 1 (core rounds 70 s + 5 s warmup in the flows build): the intro sorties by itself
    expectScreen(10, 'stFight', 'first spawn');
    expectFollow(10, 'first spawn');
    at(12, '!spec', () => api.chat(ME, '!spec'));
    expectScreen(13, 'stSpec', '!spec');
    at(13.9, 'the pawn dies (CS2 observer view)', () => { const p = api.pawn(ME); if (p && p._alive) { p.Kill(); state.forced = (state.forced || 0) + 1; } });
    at(14, '!garage', () => api.chat(ME, '!garage'));
    at(14.1, 'pawn alive in the garage', () => { const p = api.pawn(ME); if (!p || !p._alive) fails.push('!garage with a dead pawn: the pawn stays dead (no custom camera in CS2)'); });
    expectScreen(15, 'stGarage', '!spec then !garage');
    expectGarageCam(15.5, '!spec then !garage');
    sortie(16);
    if (process.env.FLOW_DEBUG) for (const t of [15.8, 16.2, 16.6, 17, 18, 20, 23]) at(t, 'debug', () => api.log(t + ' s: screen ' + screen(ME) + ', tab ' + [...Array(9).keys()].filter((i) => api.hud(ME, 'ifr_gc' + i).has('stSel')).join() + ', row0 ' + text(ME, 'gr0n') + ' / ' + text(ME, 'gr0t') + ', hint ' + text(ME, 'ghint') + ', legend ' + text(ME, 'glegend')));
    expectScreen(25, 'stFight', 'sortie from the garage after !spec');
    expectFollow(25, 'sortie from the garage after !spec');
    at(26, '!garage in a mech', () => api.chat(ME, '!garage'));
    expectScreen(27, 'stFight', '!garage while piloting does nothing');
    at(28, '!spec', () => api.chat(ME, '!spec'));
    at(29, '!back', () => api.chat(ME, '!back'));
    expectScreen(30, 'stGarage', '!spec then !back');
    expectGarageCam(30.5, '!spec then !back');
    // garage slots: Primary tab, the GT-9 (row 3) then the LR-Lumen (row 5): R then L (Nov 2026: every pick went to R)
    at(30.6, 'S', tap(api.IN.BACK)); at(30.7, 'release', tap(0)); at(30.8, 'SPACE', tap(api.IN.JUMP)); at(30.9, 'release', tap(0));
    for (let k = 0; k < 3; k++) { at(31 + k * 0.2, 'S', tap(api.IN.BACK)); at(31.1 + k * 0.2, 'release', tap(0)); }
    at(31.8, 'SPACE', tap(api.IN.JUMP)); at(31.9, 'release', tap(0));
    for (let k = 0; k < 2; k++) { at(32 + k * 0.2, 'S', tap(api.IN.BACK)); at(32.1 + k * 0.2, 'release', tap(0)); }
    at(32.6, 'SPACE', tap(api.IN.JUMP)); at(32.7, 'release', tap(0));
    at(33, 'arms', () => {
      const r = text(ME, 'ge0n'), l = text(ME, 'ge1n'); state.arms = r + ' / ' + l;
      if (!/^GT-9/.test(r) || !/^LR/.test(l)) fails.push('garage: two arm picks should fill R then L, the equipped panel shows R ' + r + ', L ' + l);
    });
    // stand-alone upgrade (10 Nov 2026 playtest: the tracks did nothing offline): D to the tracks, Space asks for the frame AP track, Space confirms;
    // the next sortie's fight HUD must show the upgraded AP maximum
    at(33.04, 'D', tap(api.IN.RIGHT)); at(33.08, 'release', tap(0)); at(33.12, 'SPACE', tap(api.IN.JUMP)); at(33.16, 'release', tap(0));
    at(33.2, 'SPACE', tap(api.IN.JUMP)); at(33.24, 'release', tap(0));
    at(33.27, 'upgraded', () => { state.upHint = text(ME, 'ghint'); state.upTrack = text(ME, 'ur0l'); });
    at(33.3, 'CTRL', tap(api.IN.DUCK)); at(33.34, 'release', tap(0));   // tracks -> list
    at(33.38, 'CTRL', tap(api.IN.DUCK)); at(33.42, 'release', tap(0));   // list -> tabs (Primary)
    at(33.46, 'W', tap(api.IN.FORWARD)); at(33.5, 'release', tap(0));    // All
    sortie(33.7);
    expectScreen(42, 'stFight', 'sortie after !back');
    at(42.5, 'AP after the upgrade', () => {
      const P = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'parts.json'), 'utf8')), f = P.parts.find((q) => q.id === 4), c = P.classes[f.class];
      const want = Math.round(c.ap * ((f.mods || {}).ap || 1) * (1 + Math.min(P.caps.ap_pct, f.upgrade.pct) / 100));
      let t = String(want); for (let i = t.length - 3; i > 0; i -= 3) t = t.slice(0, i) + ' ' + t.slice(i);
      state.apmax = text(ME, 'apmax');
      if (state.apmax !== '/ ' + t) fails.push('stand-alone upgrade: the fight HUD shows AP ' + state.apmax + ', expected / ' + t + ' (frame MK I; garage said "' + state.upHint + '", track level ' + state.upTrack + ')');
    });
    at(43, '!spec', () => api.chat(ME, '!spec'));
    at(43.5, '!spec again', () => api.chat(ME, '!spec'));
    at(43.8, '!garage', () => api.chat(ME, '!garage'));
    at(44, '!spec in the garage', () => api.chat(ME, '!spec'));
    expectScreen(45, 'stSpec', '!spec from the garage');
    at(46, '!garage', () => api.chat(ME, '!garage'));
    at(46.5, '!garage again', () => api.chat(ME, '!garage'));
    expectScreen(47, 'stGarage', '!spec, !garage, !spec, !garage');
    expectGarageCam(47.5, '!spec, !garage, !spec, !garage');
    sortie(48);
    expectScreen(57, 'stFight', 'sortie after the mixed order');
    // the round ends (core 75 s) while the garage is open; watched per tick from here (a Sortie can end early)
    at(62, '!spec', () => api.chat(ME, '!spec'));
    at(63, '!garage', () => api.chat(ME, '!garage'));
    at(64, 'watch the round end', () => { state.watch = true; });
    // FLOW_NORESTART=1: CS2 ends the round but never starts the next one (end of match, a plugin): the script must start it itself
    if (process.env.FLOW_NORESTART) at(80, 'CS2 stops restarting rounds', () => { api.cvars.mp_round_restart_delay = '99999'; });
    if (process.env.FLOW_DEBUG) for (let t = 70; t <= 100; t += 1) at(t + 0.5, 'debug', () => api.log(t + 0.5 + ' s: screen ' + screen(ME) + ' cam ' + camMode(ME) + ' phead ' + text(ME, 'phead')));
  },
  // the round end, the podium and round 2, as they happen
  watch(a) {
    const sc = screen(ME);
    state.maxRounds = Math.max(state.maxRounds || 0, a.rounds);   // mp_restartgame (the script's no-restart fallback) zeroes a.rounds
    if (!state.podiumAt) {
      if (sc.includes('stPodium')) { state.podiumAt = a.time; state.endFrom = state.last; seen.push(a.time.toFixed(1) + 's podium (from ' + state.last + ')'); }
      state.last = sc; return;
    }
    if (!state.cards && a.time > state.podiumAt + 1) {
      state.cards = true;
      state.podium = [0, 1, 2].map((i) => [text(ME, 'pn' + i), text(ME, 'ps' + i)]);
      state.phead = text(ME, 'phead');
      if (!state.phead) fails.push('podium: no headline');
      if (!state.podium[0][0]) fails.push('podium: the first card has no name');
      if (!/KILLS/.test(state.podium[0][1])) fails.push('podium: the first card has no kills line (' + state.podium[0][1] + ')');
      if (!state.podium[2][0]) fails.push('podium: the third card is empty (' + JSON.stringify(state.podium) + ')');
    }
    if (!state.fightAt && a.time > state.podiumAt + 5 && sc.includes('stFight') && camMode(ME) === CM().FOLLOW_POSITION) { state.fightAt = a.time; seen.push(a.time.toFixed(1) + 's piloting in round 2'); }
  },
  tick(a) {
    for (const s of steps) if (!s.done && a.time >= s.t - 1e-9) { s.done = true; s.fn(); }
    if (state.watch) this.watch(a);
  },
  check(a) {
    // kill credit: real CS2 kills between pawns, and score for the script AI's kills
    const ctl = a.players.filter(Boolean);
    const kills = ctl.reduce((n, c) => n + c.kills, 0), score = ctl.filter((c) => !c.bot).reduce((n, c) => n + c.score, 0);
    a.log(`pawn deaths ${a.stats.kills}, kills on the scoreboard ${kills}, human score ${score}, rounds ${a.rounds}, screens ${seen.join(', ')}`);
    a.log('arms after two picks: ' + state.arms);
    a.log('stand-alone upgrade: garage said "' + state.upHint + '", track level ' + state.upTrack + ', fight HUD AP ' + state.apmax);
    if (state.podium) a.log('podium ' + state.phead + ': ' + state.podium.map((p) => p.join(' / ')).join(' | '));
    // (kill credit is logged, not checked: deaths to the script's AI mechs are world kills by design; the 32-player mock run shows the credit)
    if (!state.podiumAt) fails.push('round 1 never reached the podium');
    else {
      if (state.endFrom !== 'stGarage') fails.push('the round ended on ' + state.endFrom + ', not with the garage open (timeline drifted)');
      if ((state.maxRounds || a.rounds) < 1) fails.push('CS2 never ended round 1 (FireWinCondition)');
      if (!state.fightAt) fails.push('round 2: the player was never piloting again after the podium (stuck on ' + screen(ME) + ')');
      else if (state.fightAt > state.podiumAt + 12 + (process.env.FLOW_NORESTART ? 15 + 1 : 7) + 6 + 10) fails.push('round 2: piloting only ' + Math.round(state.fightAt - state.podiumAt) + ' s after the podium');
    }
    for (const s of steps) if (!s.done) fails.push('the run ended before step "' + s.what + '" at ' + s.t + ' s');
    return fails;
  },
};
