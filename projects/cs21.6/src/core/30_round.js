// ---------------------------------------------------------------- one map's round (1.6 win conditions)

class MapRound {
  constructor(key) {
    this.key = key;
    this.active = false;
    this.result = null;          // { winner, reason } once decided
    this.bomb = null;            // { site, planted: time, explodes: time, defused, exploded }
    this.hadT = false; this.hadCT = false;
    this.c4Given = false;
  }
  start(nT, nCT) {
    this.active = nT > 0 && nCT > 0;
    this.result = null; this.bomb = null;
    this.hadT = nT > 0; this.hadCT = nCT > 0;
    this.c4Given = false;
  }
  get decided() { return !!this.result; }
  decide(winner, reason) {
    if (this.result) return false;
    this.result = { winner, reason };
    return true;
  }
  plant(site, now, timer) {
    if (this.result) return;
    this.bomb = { site, planted: now, explodes: now + timer, defused: false, exploded: false };
  }
  defuse() { if (this.bomb) this.bomb.defused = true; return this.decide(TEAM_CT, 'defused'); }
  explode() { if (this.bomb) this.bomb.exploded = true; return this.decide(TEAM_T, 'bombed'); }
  // elimination / time checks; returns true when this call decided the map
  check(aliveT, aliveCT, timeUp) {
    if (!this.active || this.result) return false;
    const planted = this.bomb && !this.bomb.defused && !this.bomb.exploded;
    if (aliveCT === 0 && aliveT === 0 && !planted) return this.decide(0, 'draw');
    if (aliveCT === 0) return this.decide(TEAM_T, 'elim');
    if (aliveT === 0 && !planted) return this.decide(TEAM_CT, 'elim');
    if (timeUp && !planted) return this.decide(TEAM_CT, 'saved');
    return false;
  }
}

// the CS2 round result from all the maps: the side that won more maps; a tie is a draw.
// With one map the 1.6 reason is kept (bombed / defused / saved / elimination).
function overallResult(rounds) {
  const played = rounds.filter((r) => r.active && r.result);
  if (!played.length) return { winner: 0, reason: 'draw' };
  if (played.length === 1) return played[0].result;
  let t = 0, ct = 0;
  for (const r of played) { if (r.result.winner === TEAM_T) t++; else if (r.result.winner === TEAM_CT) ct++; }
  if (t > ct) return { winner: TEAM_T, reason: 'maps' };
  if (ct > t) return { winner: TEAM_CT, reason: 'maps' };
  return { winner: 0, reason: 'draw' };
}

// FireWinCondition values when CONFIG.EXACT_END_REASONS is on (CS2's own round-end numbering, as CounterStrikeSharp has
// it: 1 bombed, 7 defused, 8 CTs win, 9 Terrorists win, 10 draw, 12 saved). Off by default: wins send 8 / 9 only.
const END_REASON = { bombed: 1, saved: 12, defused: 7, draw: 10, ct: 8, t: 9 };
function endReasonFor(res) {
  if (res.reason === 'bombed') return END_REASON.bombed;
  if (res.reason === 'defused') return END_REASON.defused;
  if (res.reason === 'saved') return END_REASON.saved;
  if (res.winner === TEAM_T) return END_REASON.t;
  if (res.winner === TEAM_CT) return END_REASON.ct;
  return END_REASON.draw;
}

// 1.6 centre text and radio line for a map result
function resultText(res) {
  switch (res.reason) {
    case 'bombed': return { text: 'Target Successfully Bombed!', sound: 'terwin' };
    case 'defused': return { text: 'The bomb has been defused!', sound: 'bombdef' };
    case 'saved': return { text: 'Target has been saved!', sound: 'ctwin' };
    case 'draw': return { text: 'Round Draw!', sound: 'rounddraw' };
  }
  return res.winner === TEAM_T ? { text: 'Terrorists Win!', sound: 'terwin' } : { text: 'Counter-Terrorists Win!', sound: 'ctwin' };
}
