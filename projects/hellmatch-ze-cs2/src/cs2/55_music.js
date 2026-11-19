// ---------------------------------------------------------------- music
// One point_soundevent per track (fdm_mus_<id>, a csgo_music sound: everyone hears it, at their own music volume).
// A round opens with the Hellmatch theme (pool "opener", see CONFIG.MUSIC_OPENER), then plays its pool in a shuffled
// order, one track after another, and stops when the round ends.

const music = { pool: "", level: "", list: [], cur: null, last: "", endsAt: 0, openedOnce: false, bossOpened: false };

function musicEnt(id) {
  const e = live(Entities.FindByName(CONFIG.MUSIC_PREFIX + id)[0]);
  if (!e) warnOnce("mus" + id, "no point_soundevent named " + CONFIG.MUSIC_PREFIX + id);
  return e;
}

// pool "level": the tracks made for this level (track.level = the ZE level id), else the "long" pool
function musicStart(pool, level) {
  musicStop();
  if (!CONFIG.MUSIC) return;
  if (pool === "level" && !MUSIC_TRACKS.some((t) => t.pool === "level" && (!t.level || t.level === level))) pool = "long";
  music.pool = pool; music.level = level || ""; music.list = [];
  const opener = MUSIC_TRACKS.find((t) => t.pool === "opener");
  const mode = CONFIG.MUSIC_OPENER;
  const boss = pool === "boss";
  // "first+boss": the map's first round, and its first Boss Battle round (once if they are the same round)
  if (opener && (mode === "every" || (mode === "first" && !music.openedOnce) || (mode === "first+boss" && (!music.openedOnce || (boss && !music.bossOpened))))) {
    music.openedOnce = true;
    if (boss) music.bossOpened = true;
    musicPlay(opener);
    return;
  }
  musicNext();
}

function musicPlay(t) {
  music.cur = t; music.last = t.id;
  music.endsAt = Instance.GetGameTime() + t.seconds + CONFIG.MUSIC_GAP;
  const e = musicEnt(t.id);
  if (!e) return;
  e.FireInput({ input: "StartSound" });
  log(`music: ${t.id.toUpperCase()} ${t.title}`);
}

function musicNext() {
  if (!music.list.length) {
    music.list = MUSIC_TRACKS.filter((t) => t.pool === music.pool && (music.pool !== "level" || !t.level || t.level === music.level));
    // a boss stage prefers the boss tracks made for this level (track.level: comma-separated ZE level ids), else any
    if (music.pool === "boss" && music.level) {
      const mine = music.list.filter((t) => String(t.level || "").split(",").map((x) => x.trim()).includes(music.level));
      if (mine.length) music.list = mine;
    }
    if (!music.list.length) { music.cur = null; return; }
    for (let i = music.list.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [music.list[i], music.list[j]] = [music.list[j], music.list[i]];
    }
    if (music.list.length > 1 && music.list[0].id === music.last) music.list.push(music.list.shift());
  }
  musicPlay(music.list.shift());
}

// a boss stage: the boss pool when the map has one (else the round's music plays on)
function musicBoss() {
  if (!CONFIG.MUSIC || music.pool === "boss" || !MUSIC_TRACKS.some((t) => t.pool === "boss")) return;
  musicStop();
  music.pool = "boss";
  musicNext();
}

function musicTick(now) {
  if (music.cur && now >= music.endsAt) musicNext();
}

function musicStop() {
  if (music.cur) {
    const e = live(Entities.FindByName(CONFIG.MUSIC_PREFIX + music.cur.id)[0]);
    if (e) e.FireInput({ input: "StopSound" });
  }
  music.pool = ""; music.list = []; music.cur = null;
}
