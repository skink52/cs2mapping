// Track votes and the winners' glow on the pure game: who gets a ballot, vote weights, each new arena taking its own
// voters' pick, two arenas wanting the same track, leavers, bots, and the glow in the next round.
// usage: node test/vote_test.cjs   (needs build/core_test.cjs from tools/build.mjs)
const C = require('../build/core_test.cjs');
let fails = 0;
function ok(cond, what) { if (!cond) { fails++; console.log('FAIL ' + what); } else console.log('ok   ' + what); }

// a round where every race ends at once with the given finishing order (slots, best first)
function finishAll(rm, orders) {
  rm.arenas.forEach((a, i) => {
    const want = orders[i] || a.order.map((c) => c.slot);
    a.state = 'racing';
    a.order.forEach((c) => { c.state = 'racing'; c.total = 1000 - want.indexOf(c.slot); });
    a.end('time');
  });
  rm.tic();
}
function makeRm(nHumans, nBots, cfg) {
  C.seedRandom(5);
  const rm = new C.RoundManager(C.TRACKS, Object.assign({ staggerArenas: false, layout: '2x32' }, cfg || {}));
  for (let i = 0; i < nHumans + nBots; i++) rm.addPerson(i, (i < nHumans ? 'h' : 'b') + i, i % 2 ? 3 : 2, i >= nHumans);
  return rm;
}

// ---- one arena: the top 3 humans vote, weights 3 / 2 / 1
{
  const rm = makeRm(6, 4);
  rm.startRound();
  ok(rm.arenas.length === 1, 'one arena of 10');
  finishAll(rm, [[3, 1, 7, 0, 2, 4, 5, 6, 8, 9]]);      // 3rd place is a bot (slot 7): it doesn't vote
  const b = rm.arenas[0].ballot;
  ok(b && b.tracks.length === 4, 'ballot with 4 tracks');
  ok(!b.tracks.includes(rm.arenas[0].track.id), 'the track just raced is not on the ballot');
  ok(b.voters.size === 2 && b.voters.get(3).weight === 3 && b.voters.get(1).weight === 2, 'winner 3 votes, 2nd 2 votes, bot 3rd none');
  ok(rm.vote(rm.person(0), b.tracks[0]) === null, '4th place cannot vote');
  ok(rm.vote(rm.person(3), b.tracks[2]) === b.tracks[2], 'winner votes');
  ok(rm.vote(rm.person(1), 1) === b.tracks[0], '2nd steps onto the first track');
  ok(rm.vote(rm.person(1), 1) === b.tracks[1] && rm.vote(rm.person(1), -1) === b.tracks[0], 'W / S steps both ways');
  const t = rm.tally(b);
  ok(t.get(b.tracks[2]) === 3 && t.get(b.tracks[0]) === 2, 'tally 3 / 2');
  ok(rm.voteLeader().id === b.tracks[2], 'lobby shows the leader');
  ok(rm.glowNext.get(rm.person(3)) === 1 && rm.glowNext.get(rm.person(7)) === 3 && rm.glowNext.size === 3, 'top 3 (bot too) glow next round');
  rm.endRoundCleanup(); rm.state = 'idle';
  rm.startRound();
  ok(rm.arenas[0].track.id === b.tracks[2] && rm.plan[0].voted, 'next race is on the winner\'s track');
  ok(rm.arenas[0].cars.get(3).glow === 1 && rm.arenas[0].cars.get(1).glow === 2 && rm.arenas[0].cars.get(0).glow === 0, 'cars glow by last place');
  ok(rm.ballots.length === 0, 'ballots used up');
}

// ---- two arenas: each new arena takes its own voters' pick; a clash goes to the bigger vote
{
  const rm = makeRm(40, 0);
  rm.startRound();
  ok(rm.arenas.length === 2, 'two arenas of 20');
  finishAll(rm, []);
  const [b0, b1] = rm.arenas.map((a) => a.ballot);
  const v0 = [...b0.voters.values()], v1 = [...b1.voters.values()];
  ok(v0.length === 3 && v1.length === 3, 'three voters per arena');
  // arena 0's winner and arena 1's 2nd + 3rd want the same track that is on both ballots, if any
  const shared = b0.tracks.find((id) => b1.tracks.includes(id));
  if (shared) {
    rm.vote(v0[0].pe, shared);                 // 3 votes
    rm.vote(v1[1].pe, shared); rm.vote(v1[2].pe, shared);   // 2 + 1
    rm.vote(v1[0].pe, b1.tracks.find((id) => id !== shared));   // 3 for something else
  }
  // force the new arenas: arena A = arena 0's winner + others, arena B = arena 1's three voters
  const people = [...rm.people.values()];
  const gA = [v0[0].pe].concat(people.filter((p) => p !== v0[0].pe && p !== v1[0].pe && p !== v1[1].pe && p !== v1[2].pe)).slice(0, 20);
  const gB = people.filter((p) => !gA.includes(p));
  const plan = rm.assignTracks([gA, gB]);
  if (shared) {
    ok(plan[0].track.id === shared || plan[1].track.id === shared, 'the shared track is used once');
    ok(plan[0].track.id !== plan[1].track.id, 'no two arenas on one track');
    // B: 2 + 1 = 3 for `shared`, 3 for the other -> B's best is a tie at 3; A has 3 for shared. A (index 0) chooses
    // first on a tie, takes `shared`; B falls back to its other pick
    ok(plan[0].track.id === shared && plan[0].voted && plan[1].voted, 'clash: first arena keeps it, the other gets its next pick');
  } else ok(true, '(no shared track on these ballots)');
  // a voter who left doesn't count
  rm.removePerson(v0[0].pe.slot);
  const plan2 = rm.assignTracks([gA.filter((p) => p !== v0[0].pe), gB]);
  if (shared) ok(!plan2[0].voted && plan2[1].voted && plan2[0].track.id !== plan2[1].track.id, 'after the winner left, their vote is gone (arena A falls back to the rotation)');
}

// ---- no human in the top 3: no voters, normal rotation; bots vote when allowed
{
  const rm = makeRm(0, 12);
  rm.startRound();
  finishAll(rm, []);
  ok(rm.arenas[0].ballot.voters.size === 0, 'all-bot podium: nobody votes');
  const rm2 = makeRm(0, 12, { botsVote: true });
  rm2.startRound(); finishAll(rm2, []);
  const b = rm2.arenas[0].ballot;
  ok(b.voters.size === 3 && [...b.voters.values()].every((v) => b.tracks.includes(v.choice)), 'botsVote: bots vote at random');
  rm2.endRoundCleanup(); rm2.state = 'idle'; rm2.startRound();
  ok(rm2.plan[0].voted, 'and their pick is used');
}

// ---- votes off
{
  const rm = makeRm(6, 0, { votes: false });
  rm.startRound(); finishAll(rm, []);
  ok(rm.arenas[0].ballot.voters.size === 0, 'votes off: no voters');
}

// ---- the race itself is untouched by voting (ballots use their own random numbers)
{
  const run = (votes) => {
    C.seedRandom(9);
    const rm = new C.RoundManager(C.TRACKS, { staggerArenas: false, votes, botSkill: 0.5 });
    for (let i = 0; i < 16; i++) rm.addPerson(i, 'b' + i, i % 2 ? 3 : 2, true);
    rm.startRound();
    let s = 0;
    while (rm.state === 'running' && s < 64 * 200) { rm.tic(); s++; for (const a of rm.arenas) a.events.length = 0; rm.events.length = 0; }
    return rm.arenas[0].result.ranking.map((c) => c.slot + ':' + c.total.toFixed(3)).join(',');
  };
  ok(run(true) === run(false), 'same race with and without votes');
}

console.log(fails ? fails + ' FAILED' : 'all vote tests passed');
process.exit(fails ? 1 : 0);
