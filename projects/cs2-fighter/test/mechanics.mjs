// Deterministic mechanics tests for the shared core: every special by both input paths,
// throws and breaks, blocking rules, juggles, dashes, projectiles, trades, the duel queue,
// team handicaps, time-outs, draws, leaving in every phase, mode changes and CPU takeover.
// Usage: node test/mechanics.mjs   (after node tools/build.mjs)
import { Game, CHARACTERS, MOVES, IN, SIM_HZ, MAX_JUGGLE } from "../dist/core_node.mjs";

let failed = 0;
function test(name, fn) {
  try { fn(); console.log("ok   " + name); }
  catch (e) { failed++; console.log("FAIL " + name + "\n     " + (e && e.stack ? e.stack.split("\n").slice(0, 3).join("\n     ") : e)); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }
const chName = (i) => CHARACTERS[i].name;

// ---------------------------------------------------------------- drivers
// held[seat] = bitmask held this frame; a bit that appears counts as a press (edge detect),
// exactly like the CS2 adapter and the browser preview feed the core.
function frame(g, held = {}) {
  for (let s = 0; s < 4; s++) if (g.seats[s].kind === "human") g.fighters[s].setInput(held[s] || 0, 0);
  g.step();
  for (const e of g.events) g.log.push(e);
  g.events.length = 0;
}
function idle(g, n) { for (let i = 0; i < n; i++) frame(g); }
function runUntil(g, pred, max = SIM_HZ * 20, held = {}) {
  for (let i = 0; i < max; i++) { if (pred()) return i; frame(g, held); }
  throw new Error("timed out waiting; phase " + g.phase + " states " + g.fighters.map((f) => f.state).join(","));
}
// plays a list of per-frame held masks for one seat (others hold nothing)
function play(g, seat, masks) { for (const m of masks) frame(g, { [seat]: m }); }
function newGame(mode, humans, cfg = {}) {
  const g = new Game({ seed: 4242, halfWidth: 380, cfg: Object.assign({ mode }, cfg) });
  g.log = [];
  for (const s of humans) g.seatHuman(s, "u" + s, "H" + (s + 1));
  return g;
}
function toFight(g) {
  runUntil(g, () => g.phase === "fight");
  idle(g, 2);   // intro -> idle
}
// a two-human duel in the fight phase with chosen characters, placed at x0 / x1
function duel(c0, c1, x0 = -150, x1 = 150, cfg = {}) {
  const g = newGame("duel", [0, 1], cfg);
  g.fighters[0].setCharacter(c0); g.fighters[1].setCharacter(c1);
  assert(g.forceStart(), "forceStart");
  toFight(g);
  place(g, x0, x1);
  return g;
}
function place(g, x0, x1) {
  const [a, b] = [g.fighters[0], g.fighters[1]];
  for (const [f, x] of [[a, x0], [b, x1]]) { f.x = x; f.y = 0; f.vx = 0; f.vy = 0; f.state = "idle"; f.move = null; f.clearInput(); }
  idle(g, 1);
}
const says = (g) => g.log.filter((e) => e.t === "say").map((e) => e.text);
function ko(g, seat) {
  const f = g.fighters[seat];
  g.applyDamage(f, 99999, null);
  runUntil(g, () => g.phase !== "fight");
}
// win a whole duel for the other fighter by KOing `loser` round after round
function winMatch(g, loser) {
  runUntil(g, () => g.phase === "fight");
  while (true) {
    ko(g, loser);
    runUntil(g, () => g.phase === "fight" || g.phase === "matchEnd");
    if (g.phase === "matchEnd") return;
  }
}
// any mode: KO everyone who isn't on `seat`'s team (ends the round)
function koOthers(g, seat) {
  const team = g.fighters[seat].team;
  for (const i of g.active) if (g.fighters[i].team !== team) g.applyDamage(g.fighters[i], 99999, null);
  runUntil(g, () => g.phase !== "fight");
}
// any mode: `seat`'s team wins every round until the match is over
function winFor(g, seat) {
  runUntil(g, () => g.phase === "fight");
  while (true) {
    koOthers(g, seat);
    runUntil(g, () => g.phase === "fight" || g.phase === "matchEnd");
    if (g.phase === "matchEnd") return;
  }
}
const dirBit = (f, d) => d === "F" ? f.towardBit() : d === "B" ? f.awayBit() : d === "U" ? IN.UP : IN.DOWN;

// ---------------------------------------------------------------- data sanity
test("move data: hit windows inside the move, chains and tips exist", () => {
  const tips = new Set(["fF", "bF", "fT", "bT", "fK", "bK", "S", "H", "G"]);
  for (const ch of CHARACTERS) {
    for (const [id, m] of Object.entries(ch.moves)) {
      for (const h of m.hits) {
        assert(h.from >= 1 && h.to >= h.from && h.to <= m.total, `${ch.name} ${id} hit window ${h.from}-${h.to} / ${m.total}`);
        assert(tips.has(h.tip), `${ch.name} ${id} unknown tip ${h.tip}`);
        assert(["high", "mid", "low", "air", "over"].includes(h.level), `${ch.name} ${id} level ${h.level}`);
      }
      for (const c of m.chain) assert(ch.moves[c], `${ch.name} ${id} chains to missing ${c}`);
      if (m.projectile) assert(tips.has(m.projectile.from) && m.projectile.at < m.total, `${ch.name} ${id} projectile`);
      if (m.release !== undefined) assert(m.release <= m.total, `${ch.name} ${id} release`);
    }
    for (const id of ch.specials) {
      const m = MOVES[id];
      assert(m && m.special && Array.isArray(m.motion) && (m.btn === "P" || m.btn === "K"), `${ch.name} special ${id}`);
    }
    // no two specials of one fighter share a motion and button
    const keys = ch.specials.map((id) => MOVES[id].motion.join(",") + "+" + MOVES[id].btn);
    assert(new Set(keys).size === keys.length, `${ch.name} duplicate special inputs ${keys}`);
  }
});

test("every move of every fighter finishes and returns to neutral", () => {
  for (let c = 0; c < 4; c++) {
    for (const id of Object.keys(CHARACTERS[c].moves)) {
      if (id === "throw") continue;   // needs a victim, tested below
      const g = duel(c, 0, -200, 200);
      const f = g.fighters[0];
      if (MOVES[id].air) { f.y = 60; f.vy = 300; f.state = "air"; }
      f.startMove(id);
      runUntil(g, () => f.state === "idle" || f.state === "crouch", 400);
      assert(Number.isFinite(f.x) && Number.isFinite(f.y) && f.y === 0, `${chName(c)} ${id} ended at y ${f.y}`);
    }
  }
});

// ---------------------------------------------------------------- specials
test("every special comes out with R, toward+R and down+R", () => {
  for (let c = 0; c < 4; c++) {
    for (let k = 0; k < 3; k++) {
      const g = duel(c, 0);
      const f = g.fighters[0];
      const dir = k === 1 ? f.towardBit() : k === 2 ? IN.DOWN : 0;
      play(g, 0, [dir, dir | IN.SPECIAL]);
      const want = CHARACTERS[c].specials[k];
      assert(f.move && f.move.id === want, `${chName(c)} slot ${k}: wanted ${want}, got ${f.move ? f.move.id : f.state}`);
    }
  }
});

test("every special comes out with its motion", () => {
  for (let c = 0; c < 4; c++) {
    for (const id of CHARACTERS[c].specials) {
      const m = MOVES[id];
      const g = duel(c, 0);
      const f = g.fighters[0];
      const a = dirBit(f, m.motion[0]), b = dirBit(f, m.motion[1]);
      const btn = m.btn === "P" ? IN.PUNCH : IN.KICK;
      play(g, 0, [a, a, 0, 0, b, b | btn]);
      assert(f.move && f.move.id === id, `${chName(c)} ${m.motion.join(",")}+${m.btn}: wanted ${id}, got ${f.move ? f.move.id : f.state}`);
    }
  }
});

test("a walk forward before D,F+P still gives Rising Splinter (not Haymaker)", () => {
  const g = duel(0, 0);
  const f = g.fighters[0], F = f.towardBit();
  play(g, 0, [F, F, F, 0, 0, IN.DOWN, IN.DOWN, 0, F, F | IN.PUNCH]);
  assert(f.move && f.move.id === "risingSplinter", "got " + (f.move ? f.move.id : f.state));
});

test("rolling S and D together then P gives Rising Splinter", () => {
  const g = duel(0, 0);
  const f = g.fighters[0], F = f.towardBit();
  play(g, 0, [IN.DOWN | F, F, F | IN.PUNCH]);
  assert(f.move && f.move.id === "risingSplinter", "got " + (f.move ? f.move.id : f.state));
});

test("dash: double-tap toward dashes, a late P is a dash punch, an early P is Haymaker", () => {
  let g = duel(0, 0, -250, 250);
  let f = g.fighters[0], F = f.towardBit();
  play(g, 0, [F, 0, 0, F]);
  assert(f.state === "dash", "dash state, got " + f.state);
  play(g, 0, [0, 0, 0, 0, 0, 0, 0, 0, IN.PUNCH]);
  assert(f.move && f.move.id === "straight", "late P: got " + (f.move ? f.move.id : f.state));
  g = duel(0, 0, -250, 250); f = g.fighters[0];
  play(g, 0, [F, 0, 0, F, 0, IN.PUNCH]);
  assert(f.move && f.move.id === "haymaker", "early P: got " + (f.move ? f.move.id : f.state));
});

test("backdash is briefly invulnerable", () => {
  const g = duel(0, 0);
  const f = g.fighters[0], B = f.awayBit();
  play(g, 0, [B, 0, 0, B]);
  assert(f.state === "backdash" && f.invuln > 0 && !f.strikeable(), `state ${f.state} invuln ${f.invuln}`);
});

// ---------------------------------------------------------------- throws
test("throw: F up close grabs, throws and damages", () => {
  const g = duel(0, 0, -16, 16);
  const [a, b] = g.fighters;
  play(g, 0, [IN.THROW]);
  assert(a.state === "throw" && b.state === "thrown", `states ${a.state}/${b.state}`);
  runUntil(g, () => b.state === "down" || b.state === "getup" || b.state === "idle", 200);
  assert(b.hp === b.maxHp - Math.round(MOVES.throw.dmg * a.ch.stats.dmg), "damage " + (b.maxHp - b.hp));
});

test("throw break: tapping F or P right after the grab escapes", () => {
  for (const escape of [IN.THROW, IN.PUNCH]) {
    const g = duel(0, 0, -16, 16);
    const [a, b] = g.fighters;
    play(g, 0, [IN.THROW]);
    frame(g, { 1: 0 }); frame(g, { 1: escape }); idle(g, 3);
    assert(b.hp === b.maxHp && a.state === "blockstun" && b.state === "blockstun", `escape ${escape}: hp ${b.hp} states ${a.state}/${b.state}`);
  }
});

test("a late break does nothing", () => {
  const g = duel(0, 0, -16, 16);
  const [a, b] = g.fighters;
  play(g, 0, [IN.THROW]);
  idle(g, 12); frame(g, { 1: IN.THROW });
  runUntil(g, () => b.state === "down", 200);
  assert(b.hp < b.maxHp, "the throw should have landed");
});

// ---------------------------------------------------------------- blocking
test("block zones: standing guards high/mid/air, crouching guards mid/low only", () => {
  const g = duel(0, 0, -16, 16);
  const d = g.fighters[1];
  d.state = "block"; d.held = IN.BLOCK;
  const stand = ["high", "mid", "low", "air"].map((l) => d.canBlock(l));
  d.state = "cblock"; d.held = IN.BLOCK | IN.DOWN;
  const crouch = ["high", "mid", "low", "air"].map((l) => d.canBlock(l));
  assert(stand.join() === "true,true,false,true", "standing " + stand);
  assert(crouch.join() === "false,true,true,false", "crouching " + crouch);
});

test("a held standing block stops a real jab; a sweep goes under it", () => {
  let g = duel(0, 0, -20, 20);
  let [a, b] = g.fighters;
  for (let i = 0; i < 12; i++) frame(g, { 0: i === 0 ? IN.PUNCH : 0, 1: IN.BLOCK });
  assert(b.hp === b.maxHp && g.log.some((e) => e.id === "block"), "jab should be blocked, hp " + b.hp);
  g = duel(0, 0, -30, 30); [a, b] = g.fighters;
  for (let i = 0; i < 16; i++) frame(g, { 0: IN.DOWN | (i === 1 ? IN.KICK : 0), 1: IN.BLOCK });
  assert(b.hp < b.maxHp, "sweep should hit a standing block");
  g = duel(0, 0, -30, 30); [a, b] = g.fighters;
  for (let i = 0; i < 16; i++) frame(g, { 0: IN.DOWN | (i === 1 ? IN.KICK : 0), 1: IN.BLOCK | IN.DOWN });
  assert(b.hp === b.maxHp, "sweep should be blocked crouching, hp " + b.hp);
});

test("holding back blocks a jab; down-back blocks a sweep; backBlocks:false turns it off", () => {
  let g = duel(0, 0, -20, 20);
  let b = g.fighters[1];
  for (let i = 0; i < 14; i++) frame(g, { 0: i === 2 ? IN.PUNCH : 0, 1: b.awayBit() });
  assert(b.hp === b.maxHp && g.log.some((e) => e.id === "block"), "back should block a jab, hp " + b.hp);
  g = duel(0, 0, -30, 30); b = g.fighters[1];
  for (let i = 0; i < 16; i++) frame(g, { 0: IN.DOWN | (i === 1 ? IN.KICK : 0), 1: b.awayBit() | IN.DOWN });
  assert(b.hp === b.maxHp, "down-back should block a sweep, hp " + b.hp);
  g = duel(0, 0, -20, 20, { backBlocks: false }); b = g.fighters[1];
  for (let i = 0; i < 14; i++) frame(g, { 0: i === 2 ? IN.PUNCH : 0, 1: b.awayBit() });
  assert(b.hp < b.maxHp, "with backBlocks off, back should not block");
});

test("crouching ducks a jab", () => {
  const g = duel(0, 0, -20, 20);
  const b = g.fighters[1];
  for (let i = 0; i < 14; i++) frame(g, { 0: i === 2 ? IN.PUNCH : 0, 1: IN.DOWN });
  assert(b.hp === b.maxHp, "jab hit a croucher, hp " + b.hp);
  const g2 = duel(0, 0, -20, 20);
  for (let i = 0; i < 14; i++) frame(g2, { 0: i === 2 ? IN.PUNCH : 0 });
  assert(g2.fighters[1].hp < g2.fighters[1].maxHp, "jab should hit a standing opponent");
});

test("chip damage never KOs", () => {
  const g = duel(0, 0, -30, 30);
  const [a, b] = g.fighters;
  b.hp = 1; b.state = "block"; b.held = IN.BLOCK;
  g.resolveHit(a, b, Object.assign({}, a.ch.moves.haymaker.hits[0]), { x: b.x, y: 50 }, false);
  assert(b.hp === 1 && !b.ko, "hp " + b.hp);
});

// ---------------------------------------------------------------- juggles, projectiles, trades
test(`juggle cap: an airborne fighter takes at most ${MAX_JUGGLE} more hits`, () => {
  const g = duel(0, 0, -30, 30);
  const [a, b] = g.fighters;
  const jab = a.ch.moves.jab.hits[0];
  g.resolveHit(a, b, a.ch.moves.uppercut.hits[0], { x: b.x, y: 50 }, false);
  assert(b.state === "launch" && b.airborne, "uppercut should launch");
  let n = 0;
  for (let i = 0; i < 10; i++) { if (!b.strikeable()) break; g.resolveHit(a, b, jab, { x: b.x, y: 50 }, false); n++; }
  assert(n === MAX_JUGGLE, "air hits allowed: " + n);
});

test("projectiles clash in the middle and nobody is hurt", () => {
  const g = duel(0, 0, -200, 200);
  frame(g, { 0: IN.SPECIAL, 1: IN.SPECIAL });
  runUntil(g, () => g.projectiles.length === 2, 40);
  runUntil(g, () => g.projectiles.length === 0, 120);
  idle(g, 10);
  assert(g.fighters[0].hp === g.fighters[0].maxHp && g.fighters[1].hp === g.fighters[1].maxHp, "hp " + g.fighters.map((f) => f.hp));
});

test("one projectile at a time per fighter", () => {
  const g = duel(0, 0, -300, 300);
  play(g, 0, [IN.SPECIAL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, IN.SPECIAL]);
  idle(g, 30);
  assert(g.projectiles.length <= 1, "projectiles " + g.projectiles.length);
});

test("simultaneous jabs trade (seat order doesn't decide)", () => {
  const g = duel(0, 0, -27, 27);
  for (let i = 0; i < 12; i++) frame(g, { 0: i === 0 ? IN.PUNCH : 0, 1: i === 0 ? IN.PUNCH : 0 });
  const [a, b] = g.fighters;
  assert(a.hp < a.maxHp && b.hp < b.maxHp, "both should be hit: " + a.hp + " / " + b.hp);
});

test("armour soaks one hit of a trade (Steam Ram)", () => {
  const g = duel(1, 0, -60, 20);
  const [a, b] = g.fighters;
  a.startMove("steamRam"); idle(g, 3);
  g.resolveHit(b, a, b.ch.moves.jab.hits[0], { x: a.x, y: 50 }, false);
  assert(a.state === "attack" && a.move && a.move.id === "steamRam", "ram should keep going, state " + a.state);
});

// ---------------------------------------------------------------- rounds and matches
test("time over: more health wins the round; equal health is a draw", () => {
  let g = duel(0, 0);
  g.fighters[1].hp = 50; g.roundTimer = 0.03;
  runUntil(g, () => g.phase === "roundEnd", 20);
  assert(g.roundWinner === g.fighters[0].team && g.teamWins[g.fighters[0].team] === 1, "winner " + g.roundWinner);
  g = duel(0, 0); g.roundTimer = 0.03;
  runUntil(g, () => g.phase === "roundEnd", 20);
  assert(g.roundWinner === -1 && g.teamWins.every((w) => w === 0), "draw expected, winner " + g.roundWinner);
});

test("double KO is a drawn round", () => {
  const g = duel(0, 0);
  g.applyDamage(g.fighters[0], 999, null); g.applyDamage(g.fighters[1], 999, null);
  runUntil(g, () => g.phase === "roundEnd", 20);
  assert(g.roundWinner === -1, "winner " + g.roundWinner);
});

test("best of three ends the match and reports it once", () => {
  const g = duel(0, 0);
  winMatch(g, 1);
  assert(g.matchWinner === g.fighters[0].team && says(g).length === 1, "says: " + says(g).join(" | "));
});

test("duel queue: winner stays, loser goes to the back (3 players)", () => {
  const g = newGame("duel", [0, 1, 2]);
  g.forceStart();
  assert(g.active.join() === "0,1", "first pair " + g.active);
  winMatch(g, 1);
  runUntil(g, () => g.phase === "intro");
  assert(g.active.join() === "0,2" && g.queue.join() === "0,2,1", `second pair ${g.active} queue ${g.queue}`);
  assert(g.champion === 0 && g.streak === 1, "streak " + g.streak);
  winMatch(g, 2);
  runUntil(g, () => g.phase === "intro");
  assert(g.active.join() === "0,1" && g.streak === 2, `third pair ${g.active} streak ${g.streak}`);
  winMatch(g, 0);
  runUntil(g, () => g.phase === "intro");
  assert(g.active.join() === "1,2" && g.champion === 1 && g.streak === 1, `fourth pair ${g.active} champion ${g.champion}`);
});

test("duel draw game: both go to the back of the queue", () => {
  const g = newGame("duel", [0, 1, 2], { maxRounds: 1 });
  g.forceStart();
  toFight(g);
  g.roundTimer = 0.03;
  runUntil(g, () => g.phase === "matchEnd");
  assert(g.matchWinner === -1, "draw game expected");
  runUntil(g, () => g.phase === "intro");
  assert(g.active.join() === "2,0" && g.champion === -1, `next pair ${g.active}`);
});

test("teams: a 2 v 1 side gets double health; teammates can't hit each other", () => {
  const g = newGame("teams", [0, 1, 2]);
  g.forceStart();
  toFight(g);
  const [a, b, c] = g.fighters;
  assert(c.maxHp === 2 * c.ch.stats.hp && a.maxHp === a.ch.stats.hp, `hp ${a.maxHp} ${b.maxHp} ${c.maxHp}`);
  assert(!g.enemies(a).includes(b) && g.enemies(a).includes(c), "team enemies");
});

test("FFA: last one standing takes the round", () => {
  const g = newGame("ffa", [0, 1, 2, 3]);
  g.forceStart();
  toFight(g);
  g.applyDamage(g.fighters[0], 999, null); g.applyDamage(g.fighters[2], 999, null); idle(g, 2);
  assert(g.phase === "fight", "two still standing");
  g.applyDamage(g.fighters[3], 999, null);
  runUntil(g, () => g.phase === "roundEnd", 10);
  assert(g.roundWinner === g.fighters[1].team, "winner " + g.roundWinner);
});

// ---------------------------------------------------------------- leaving and joining
test("leaving mid-fight forfeits once", () => {
  const g = duel(0, 0);
  g.unseat(1);
  assert(g.phase === "matchEnd" && g.matchWinner === g.fighters[0].team, "phase " + g.phase);
  runUntil(g, () => g.phase === "lobby");
  assert(says(g).length === 1, "says: " + says(g).join(" | "));
});

test("leaving during the winner's celebration doesn't award a second win", () => {
  const g = newGame("duel", [0, 1, 2]);
  g.forceStart();
  winMatch(g, 1);
  g.unseat(1);
  assert(g.phase === "matchEnd" && g.streak === 1, `phase ${g.phase} streak ${g.streak}`);
  runUntil(g, () => g.phase === "intro");
  assert(g.active.join() === "0,2" && says(g).length === 1, `pair ${g.active} says ${says(g).join(" | ")}`);
});

test("leaving while 'next up' is shown re-picks the pair without a forfeit", () => {
  const g = newGame("duel", [0, 1, 2, 3]);
  g.forceStart();
  winMatch(g, 1);
  runUntil(g, () => g.phase === "nextUp");
  assert(g.active.join() === "0,2", "announced pair " + g.active);
  g.unseat(2);
  assert(g.phase === "nextUp" && g.active.join() === "0,3", `phase ${g.phase} pair ${g.active}`);
  runUntil(g, () => g.phase === "intro");
  assert(g.active.join() === "0,3" && says(g).length === 1 && g.streak === 1, `pair ${g.active} streak ${g.streak}`);
});

test("leaving in every phase never throws and lands somewhere sensible", () => {
  for (const mode of ["duel", "teams", "ffa"]) {
    for (const target of ["lobby", "countdown", "intro", "fight", "roundEnd", "matchEnd", "nextUp"]) {
      if (target === "nextUp" && mode !== "duel") continue;
      const g = newGame(mode, [0, 1, 2]);
      if (target === "countdown") { for (const s of [0, 1, 2]) g.seats[s].ready = true; idle(g, 2); }
      else if (target !== "lobby") g.forceStart();
      if (target === "fight") toFight(g);
      if (target === "roundEnd") { toFight(g); koOthers(g, g.active[0]); }
      if (target === "matchEnd" || target === "nextUp") { toFight(g); winFor(g, g.active[0]); }
      if (target === "nextUp") runUntil(g, () => g.phase === "nextUp");
      assert(g.phase === target, `${mode}: wanted ${target}, at ${g.phase}`);
      for (const seat of [g.active[0] ?? 0, 2]) { g.unseat(seat); idle(g, SIM_HZ * 12); }
      assert(["lobby", "countdown", "intro", "fight", "roundEnd", "matchEnd", "nextUp"].includes(g.phase), `${mode}/${target}: phase ${g.phase}`);
      assert(says(g).length <= 2, `${mode}/${target}: says ${says(g).join(" | ")}`);
      assert(g.seated().length === 1 && g.phase === "lobby", `${mode}/${target}: one player left should be in the lobby, at ${g.phase}`);
    }
  }
});

test("the last human leaving a match against CPUs ends it", () => {
  const g = newGame("ffa", [0]);
  g.addCpu(); g.addCpu();
  g.forceStart(); toFight(g);
  g.unseat(0);
  assert(g.phase === "lobby", "phase " + g.phase);
});

test("reset during a match clears everything without a forfeit message", () => {
  const g = duel(0, 0);
  g.reset();
  idle(g, 5);
  assert(g.phase === "lobby" && g.seated().length === 0 && says(g).length === 0, `phase ${g.phase} says ${says(g).join(" | ")}`);
});

test("mode change during a match waits for the lobby", () => {
  const g = duel(0, 0);
  g.setMode("ffa");
  assert(g.mode === "duel" && g.pendingMode === "ffa", "pending");
  winMatch(g, 1);
  runUntil(g, () => g.phase === "lobby");
  assert(g.mode === "ffa" && !g.pendingMode, "mode " + g.mode);
});

test("joining mid-match: duel queues you, FFA seats you for the next one", () => {
  let g = duel(0, 0);
  g.seatHuman(2, "c", "C");
  assert(g.queue.includes(2) && !g.active.includes(2) && g.fighters[2].state === "waiting", "duel queue");
  g = newGame("ffa", [0, 1]); g.forceStart(); toFight(g);
  g.seatHuman(3, "d", "D");
  assert(!g.fighters[3].onStage && !g.active.includes(3), "ffa newcomer waits");
});

test("a human can take over a CPU that isn't fighting", () => {
  let g = newGame("duel", [0]);
  const cpu = g.addCpu();
  assert(g.takeOver(cpu, "x", "X") && g.seats[cpu].kind === "human" && !g.seats[cpu].ready, "lobby takeover");
  g = newGame("duel", [0, 1]);
  const waiting = g.addCpu();
  g.forceStart(); toFight(g);
  assert(!g.canTakeOver(0) && g.canTakeOver(waiting), "only the waiting CPU");
  const before = g.queue.indexOf(waiting);
  assert(g.takeOver(waiting, "y", "Y") && g.queue.indexOf(waiting) === before && g.phase === "fight", `queue ${g.queue}`);
});

test("lobby: pick, ready, un-ready, host changes mode and adds CPUs", () => {
  const g = newGame("duel", [0, 1]);
  const a = g.fighters[0];
  const c0 = a.charIdx;
  play(g, 0, [IN.RIGHT, 0]);
  assert(a.charIdx === (c0 + 1) % 4, "pick right");
  play(g, 0, [IN.PUNCH, 0]);
  assert(g.seats[0].ready, "ready");
  play(g, 0, [IN.KICK, 0]);
  assert(!g.seats[0].ready, "un-ready");
  play(g, 1, [IN.SPECIAL, 0]);
  assert(g.mode === "duel", "only the host changes mode");
  play(g, 0, [IN.SPECIAL, 0]);
  assert(g.mode === "teams", "host R cycles mode, got " + g.mode);
  play(g, 0, [IN.THROW, 0]);
  assert(g.seated().length === 3, "host F adds a CPU");
  for (const s of [0, 1]) g.seats[s].ready = true;
  runUntil(g, () => g.phase === "intro", SIM_HZ * 5);
});

test("CPUs sometimes break throws on hard, never all of them", () => {
  const g = newGame("duel", [0], { cpuLevel: 2 });
  g.addCpu(1);
  g.fighters[1].setCharacter(0);
  g.forceStart(); toFight(g);
  const [a, b] = g.fighters;
  let breaks = 0;
  for (let t = 0; t < 40; t++) {
    for (const [f, x] of [[a, -16], [b, 16]]) { f.x = x; f.y = 0; f.vx = 0; f.vy = 0; f.state = "idle"; f.move = null; f.hp = f.maxHp; f.invuln = 0; f.throwInvuln = 0; f.victim = null; f.thrower = null; }
    a.facing = 1; b.facing = -1;
    a.startThrow(b);
    idle(g, 24);
    if (b.hp === b.maxHp) breaks++;
    if (g.phase !== "fight") break;
  }
  assert(breaks >= 3 && breaks <= 30, "breaks " + breaks + "/40");
});

test("holding back walks back while guarding; down-back guards without moving", () => {
  let g = duel(0, 0, -100, 100);
  const b = g.fighters[1];
  for (let i = 0; i < 10; i++) frame(g, { 1: b.awayBit() });
  assert(b.state === "walk" && b.x > 105 && b.canBlock("high") && b.canBlock("mid") && !b.canBlock("low"), "state " + b.state + " x " + b.x);
  const x0 = b.x;
  for (let i = 0; i < 10; i++) frame(g, { 1: b.awayBit() | IN.DOWN });
  assert(b.state === "cblock" && Math.abs(b.x - x0) < 0.5 && b.canBlock("low") && !b.canBlock("high"), "down-back: " + b.state + " moved " + (b.x - x0));
  g = duel(0, 0, -100, 100, { backBlocks: false });
  const c = g.fighters[1];
  for (let i = 0; i < 10; i++) frame(g, { 1: c.awayBit() });
  assert(c.state === "walk" && c.x > 100 && !c.canBlock("mid"), "backBlocks off: walks without guarding");
});

test("after blocking while walking back, the guard holds still before walking on", () => {
  const g = duel(0, 0, -24, 24);
  const b = g.fighters[1];
  let blocked = -1, walkAgain = -1;
  for (let i = 0; i < 80; i++) {
    frame(g, { 0: i === 0 ? IN.PUNCH : 0, 1: b.awayBit() });
    if (b.state === "blockstun" && blocked < 0) blocked = i;
    if (blocked >= 0 && b.state === "walk" && walkAgain < 0) walkAgain = i;
  }
  assert(blocked >= 0, "the jab should be blocked by walking back");
  const stun = g.fighters[0].ch.moves.jab.hits[0].blockstun;
  assert(walkAgain - blocked >= stun + 10, "walked again " + (walkAgain - blocked) + " frames after the block");
});

test("hit zones come from where the hit lands: a sweep is low, a jab to the head is high", () => {
  const g = duel(0, 0, -24, 24);
  const d = g.fighters[1];
  const z = (y, level = "mid") => g.zoneOf({ level }, { x: 0, y }, d);
  assert(z(5) === "low" && z(45) === "mid" && z(85) === "high", "zones " + [z(5), z(45), z(85)]);
  assert(z(85, "low") === "low" && z(5, "over") === "high" && z(5, "air") === "high", "forced zones");
});

test("every fighter has a P,P and a K,K combo that comes out (hit or whiff)", () => {
  for (let c = 0; c < CHARACTERS.length; c++) {
    const ch = CHARACTERS[c];
    for (const [btn, first, fin] of [[IN.PUNCH, "jab", ch.combos.p], [IN.KICK, "kickMid", ch.combos.k]]) {
      for (const gap of [-24, -150]) {   // touching (hits) and far apart (whiffs)
        const g = duel(c, 0, gap, -gap > 0 ? 0 : 0);
        place(g, gap < -100 ? -150 : -26, gap < -100 ? 150 : 26);
        const a = g.fighters[0];
        let seen = "", started = false;
        for (let i = 0; i < 40; i++) {
          frame(g, { 0: i === 0 || i === 7 ? btn : 0 });
          if (a.move && a.move.id === first) started = true;
          if (a.move && a.move.id === fin) { seen = fin; break; }
        }
        assert(started && seen === fin, ch.name + " " + first + " -> " + fin + " (" + (gap < -100 ? "whiff" : "hit") + ") got " + (a.move ? a.move.id : a.state));
      }
    }
  }
});

test("combo strings: P,K gives the mix-up ender and P,P,K runs jab, finisher, kick finisher", () => {
  for (let c = 0; c < CHARACTERS.length; c++) {
    const ch = CHARACTERS[c];
    for (const [presses, want] of [[[[0, IN.PUNCH], [7, IN.KICK]], [ch.combos.mix]], [[[0, IN.PUNCH], [7, IN.PUNCH], [24, IN.KICK]], [ch.combos.p, ch.combos.k]]]) {
      const g = duel(c, 0, -26, 26);
      const a = g.fighters[0], seen = [];
      for (let i = 0; i < 90; i++) {
        const p = presses.find(([t]) => t === i);
        frame(g, { 0: p ? p[1] : 0 });
        if (a.move && !seen.includes(a.move.id)) seen.push(a.move.id);
      }
      for (const w of want) assert(seen.includes(w), ch.name + " expected " + w + " in " + seen.join(","));
    }
  }
});

test("every fighter has a low and a high of their own in their combo enders", () => {
  for (const ch of CHARACTERS) {
    const levels = Object.values(ch.combos).flatMap((id) => ch.moves[id].hits.map((h) => h.level));
    assert(levels.includes("low"), ch.name + " has no low ender: " + levels);
    assert(levels.some((l) => l === "high" || l === "over"), ch.name + " has no high ender: " + levels);
  }
});

test("combo finishers finish, and a jab then its finisher counts as a 2 hit combo", () => {
  for (let c = 0; c < CHARACTERS.length; c++) {
    const g = duel(c, 0, -26, 26);
    const a = g.fighters[0], b = g.fighters[1];
    for (let i = 0; i < 90; i++) frame(g, { 0: i === 0 || i === 6 ? IN.PUNCH : 0 });
    assert(NEUTRAL_OK(a.state), CHARACTERS[c].name + " stuck in " + a.state);
    assert(g.bestCombo[0] >= 2, CHARACTERS[c].name + " best combo " + g.bestCombo[0] + " (b hp " + b.hp + ")");
  }
});
function NEUTRAL_OK(s) { return ["idle", "walk", "crouch", "block", "cblock"].includes(s); }

test("perfect block: guard pressed just before the hit = no chip, short stun, health back", () => {
  // Haymaker has chip damage; press guard 3 frames before its first active frame
  const g = duel(0, 0, -60, 60);
  const a = g.fighters[0], b = g.fighters[1];
  b.hp = 50;
  a.startMove("haymaker");
  const hitF = a.move.hits[0].from;
  let blockedAt = -1, stunAt = 0;
  for (let i = 0; i < 40; i++) {
    const guard = i >= hitF - 3;
    frame(g, { 1: guard ? IN.BLOCK : 0 });
    if (b.state === "blockstun" && blockedAt < 0) { blockedAt = i; stunAt = b.stun; }
  }
  assert(blockedAt >= 0, "never blocked");
  assert(b.hp === 52 && b.perfects === 1, "hp " + b.hp + " perfects " + b.perfects);
  assert(g.log.some((e) => e.t === "perfect"), "perfect event");
  // held long before: an ordinary block with chip
  const g2 = duel(0, 0, -60, 60);
  const a2 = g2.fighters[0], b2 = g2.fighters[1];
  b2.hp = 50;
  for (let i = 0; i < 20; i++) frame(g2, { 1: IN.BLOCK });
  a2.startMove("haymaker");
  for (let i = 0; i < 40; i++) frame(g2, { 1: IN.BLOCK });
  assert(b2.hp < 50 && b2.perfects === 0, "plain block hp " + b2.hp + " perfects " + b2.perfects);
});

test("stopCpus ends a CPU-only match and empties the CPU seats", () => {
  const g = newGame("duel", []);
  g.cfg.needHuman = false; g.forceCpuMatch = true;
  while (g.addCpu() >= 0) { /* fill */ }
  g.forceStart();
  runUntil(g, () => g.phase === "fight");
  g.stopCpus();
  idle(g, 5);
  assert(g.phase === "lobby" && g.seated().length === 0 && !g.forceCpuMatch, "phase " + g.phase + " seated " + g.seated().length);
});

test("tag team: one fighter per team on stage, SHIFT+R swaps after the cooldown", () => {
  const g = newGame("teams", [0, 1, 2, 3]);
  assert(g.forceStart(), "forceStart");
  toFight(g);
  const on = () => g.fighters.filter((f) => f.active).map((f) => f.seat).sort().join();
  assert(on() === "0,2", "points " + on());
  idle(g, Math.round(SIM_HZ * 1.6));   // opening cooldown
  frame(g, { 0: IN.BLOCK }); frame(g, { 0: IN.BLOCK | IN.SPECIAL });
  idle(g, 2);
  assert(on() === "1,2", "after tag " + on());
  assert(g.fighters[0].background && g.fighters[0].state === "waiting", "benched " + g.fighters[0].state);
  frame(g, { 1: IN.BLOCK }); frame(g, { 1: IN.BLOCK | IN.SPECIAL });
  idle(g, 2);
  assert(on() === "1,2", "cooldown should stop an instant tag back: " + on());
});

test("tag team: a knocked-out point is replaced, and the round only ends when both are out", () => {
  const g = newGame("teams", [0, 1, 2, 3]);
  g.forceStart(); toFight(g);
  g.applyDamage(g.fighters[2], 99999, g.fighters[0]);
  runUntil(g, () => g.fighters[3].active, SIM_HZ * 5);
  assert(g.phase === "fight", "round ended early: " + g.phase);
  assert(g.fighters[2].background, "KO'd point should be benched");
  g.applyDamage(g.fighters[3], 99999, g.fighters[0]);
  runUntil(g, () => g.phase === "roundEnd", SIM_HZ * 5);
  assert(g.roundWinner === 0, "red should win the round, got " + g.roundWinner);
});

test("tag team: a benched partner wins back half the damage of their stint", () => {
  const g = newGame("teams", [0, 1, 2, 3]);
  g.forceStart(); toFight(g);
  const a = g.fighters[0];
  g.applyDamage(a, 40, g.fighters[2]);
  idle(g, Math.round(SIM_HZ * 1.6));
  frame(g, { 0: IN.BLOCK }); frame(g, { 0: IN.BLOCK | IN.SPECIAL });
  idle(g, SIM_HZ * 3);
  assert(a.background && a.hp === 80, "hp 60 -> " + a.hp);
});

console.log(failed ? `\n${failed} FAILED` : "\nALL PASSED");
process.exit(failed ? 1 : 0);
