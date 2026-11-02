// ---------------------------------------------------------------- next-mode vote
// When a Doom round ends, everyone gets a short ballot for the next round's mode. One key per mode (keys that don't
// move you, so nobody votes by walking about in the lobby), or chat: !ffa !tdm !elim !lms !boss / !vote <mode>.
// A vote counts 1 + VOTE_TOP_BONUS x (your frags / the top frags in your arena): the top fragger's vote counts 3.
// A mode played the last two rounds running is not on the ballot (no third in a row); if the winner can't be
// played when the round starts (people left, no one on one side), the next choice is used.

const VOTE_ORDER = ["ffa", "tdm", "elim", "lms", "boss"];
const VOTE_SHORT = { ffa: "FFA", tdm: "TDM", elim: "ELIM", lms: "LMS", boss: "BOSS" };
const VOTE_KEY_LABEL = { ATTACK: "M1", ATTACK2: "M2", USE: "E", RELOAD: "R", LOOK_AT_WEAPON: "F", JUMP: "SPACE", DUCK: "CTRL" };

// vote: null, or { open, endsAt, inputFrom, options: [mode], weights: Map(slot -> weight), choice: Map(slot -> mode),
//                  totals: { mode: weight }, result: [mode, ...] (best first; set when it closes), pawns: Map(slot -> pawn) }
let vote = null;

function voteRepeatBanned(k) {
  const h = rm.modeHistory;
  return h.length >= 2 && h[h.length - 1] === k && h[h.length - 2] === k;
}

// the modes that could be played next with the people here now
function voteOptions() {
  let n = 0, t = 0, ct = 0;
  for (const pe of rm.people.values()) {
    if ((pe.csTeam !== 2 && pe.csTeam !== 3) || (pe.afk && !pe.bot)) continue;
    n++; if (pe.csTeam === 2) t++; else ct++;
  }
  if (n < CONFIG.MIN_PLAYERS) return [];
  const smallest = Math.min(...arenaSizes(n, rm.cfg));
  return VOTE_ORDER.filter((k) => MODES[k] && (CONFIG.MODE_WEIGHTS[k] || 0) > 0 && CONFIG.VOTE_KEYS[k] && smallest >= MODES[k].minPlayers &&
    !(MODES[k].teams && (!t || !ct)) && !voteRepeatBanned(k));
}

// called when the Doom round ends (before the arenas are cleared): weights come from this round's frags
function voteStart(now) {
  vote = null;
  if (!CONFIG.VOTE || !(CONFIG.VOTE_SECONDS > 0)) return;
  let humans = 0;
  for (const pe of rm.people.values()) if (!pe.bot) humans++;
  if (!humans) return;
  const options = voteOptions();
  if (options.length < 2) return;   // nothing to choose
  const weights = new Map();
  for (const a of rm.arenas) {
    let top = 0;
    for (const p of a.players.values()) if (p.frags > top) top = p.frags;
    for (const p of a.players.values()) {
      const pe = p.person;
      if (!pe || pe.bot) continue;
      const share = top > 0 ? Math.max(0, Math.min(1, p.frags / top)) : 0;
      weights.set(pe.slot, 1 + (CONFIG.VOTE_TOP_BONUS || 0) * share);
    }
  }
  const totals = {};
  for (const k of options) totals[k] = 0;
  vote = { open: true, endsAt: now + CONFIG.VOTE_SECONDS, inputFrom: now + 1, options, weights, choice: new Map(), totals, result: null, pawns: new Map(), pawnsAt: 0 };
  sayAll(`VOTE FOR THE NEXT MODE (${CONFIG.VOTE_SECONDS} s): ` + options.map((k) => `${voteKeyLabel(k)} ${MODES[k].name}`).join(", ") + " - or type !" + options.map((k) => k).join(" !"));
}

function voteKeyLabel(k) { const key = CONFIG.VOTE_KEYS[k]; return VOTE_KEY_LABEL[key] || key; }
function voteWeight(slot) { return (vote && vote.weights.get(slot)) || 1; }

function voteCast(slot, mode) {
  if (!vote || !vote.open || !vote.options.includes(mode)) return false;
  const pe = rm.person(slot);
  if (!pe || pe.bot) return false;
  const old = vote.choice.get(slot);
  if (old === mode) return true;
  const w = voteWeight(slot);
  if (old) vote.totals[old] -= w;
  vote.choice.set(slot, mode);
  vote.totals[mode] += w;
  return true;
}

function voteDrop(slot) {
  if (!vote || !vote.open) return;
  const old = vote.choice.get(slot);
  if (old) { vote.totals[old] -= voteWeight(slot); vote.choice.delete(slot); }
  vote.pawns.delete(slot);
}

function voteClose() {
  if (!vote || !vote.open) return;
  vote.open = false;
  vote.pawns.clear();
  const voted = vote.options.filter((k) => vote.totals[k] > 1e-6);
  if (!voted.length) { vote.result = null; log("vote: no votes, the mode is picked at random"); return; }
  // best first; a tie is settled by lot
  const lot = new Map(voted.map((k) => [k, Math.random()]));
  voted.sort((a, b) => (vote.totals[b] - vote.totals[a]) || (lot.get(b) - lot.get(a)));
  vote.result = voted;
  const tally = voted.map((k) => `${VOTE_SHORT[k]} ${voteShow(vote.totals[k])}`).join(", ");
  sayAll(`NEXT MODE: ${MODES[voted[0]].name} (votes ${tally})`);
  log(`vote: ${voted[0]} (${tally}; ${vote.choice.size} voters)`);
}

function voteShow(x) { return String(Math.round(x * 10) / 10); }

// per server tick while the ballot is open: key presses of everyone who can vote
function voteTick(now) {
  if (!vote || !vote.open) return;
  if (now >= vote.endsAt) { voteClose(); return; }
  if (now < vote.inputFrom) return;   // a fire button still held from the round doesn't vote
  // pawns: the parked one while it's there, else looked up a few times a second (not every tick)
  if (now >= vote.pawnsAt) {
    vote.pawnsAt = now + 0.25;
    vote.pawns.clear();
    for (const pe of rm.people.values()) {
      if (pe.bot) continue;
      const pk = parked.get(pe.slot);
      const pawn = pk && live(pk.pawn) ? pk.pawn : pawnOf(pe.slot);
      if (pawn) vote.pawns.set(pe.slot, pawn);
    }
  }
  for (const [slot, pawn] of vote.pawns) {
    try {
      for (let i = 0; i < vote.options.length; i++) {
        const k = vote.options[i];
        if (pawn.WasInputJustPressed(VOTE_INPUT[k])) voteCast(slot, k);
      }
    } catch (err) { vote.pawns.delete(slot); }
  }
}
const VOTE_INPUT = {};
for (const k of VOTE_ORDER) if (CONFIG.VOTE_KEYS[k]) VOTE_INPUT[k] = CSInputs[CONFIG.VOTE_KEYS[k]];

// the preference list for the next round (best first), or undefined (random); used once
function voteTake() {
  const r = vote && !vote.open ? vote.result : null;
  vote = null;
  return r || undefined;
}

function voteBusy(now) { return !!(vote && vote.open && now < vote.endsAt); }

// HUD lines for the lobby screen while there is a ballot (or its result)
function voteLines(pe, now, info) {
  if (!vote) return;
  if (vote.open) {
    const left = Math.max(0, Math.ceil(vote.endsAt - now));
    info.center = `VOTE NEXT MODE: ${left}`;
    const mine = vote.choice.get(pe.slot);
    const toks = vote.options.map((k) => `${mine === k ? ">" : ""}${voteKeyLabel(k)} ${VOTE_SHORT[k]} ${voteShow(vote.totals[k])}`);
    voteSplit(toks, info);
    if (pe.bot) return;
    const w = voteWeight(pe.slot);
    info.line2 = mine ? `YOUR VOTE: ${VOTE_SHORT[mine]} (X${voteShow(w)})` : `YOUR VOTE COUNTS X${voteShow(w)}`;
  } else if (vote.result) {
    info.center = `NEXT: ${MODES[vote.result[0]].name}`;
    voteSplit(vote.result.map((k) => `${VOTE_SHORT[k]} ${voteShow(vote.totals[k])}`), info);
  }
}

// option tokens over the two bottom lines (40 then 32 characters)
function voteSplit(toks, info) {
  let a = "", b = "";
  for (const t of toks) {
    if (!b && (a ? a.length + 2 + t.length : t.length) <= 40) a = a ? a + "  " + t : t;
    else b = b ? b + "  " + t : t;
  }
  info.spec2 = a; info.spec = b.slice(0, 32);
}
