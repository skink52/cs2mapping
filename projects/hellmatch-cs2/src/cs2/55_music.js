// ---------------------------------------------------------------- music
// One point_soundevent per track (fdm_mus_<id>, a csgo_music sound: everyone hears it, at their own music volume).
// A round opens with the Hellmatch theme (pool "opener", see CONFIG.MUSIC_OPENER), then plays its pool in a shuffled
// order, one track after another, and stops when the round ends.

const music = { pool: "", list: [], cur: null, last: "", endsAt: 0, openedOnce: false, bossOpened: false };

function musicEnt(id) {
  const e = live(Instance.FindEntityByName(CONFIG.MUSIC_PREFIX + id));
  if (!e) warnOnce("mus" + id, "no point_soundevent named " + CONFIG.MUSIC_PREFIX + id);
  return e;
}

function musicStart(pool) {
  musicStop();
  if (!CONFIG.MUSIC) return;
  music.pool = pool; music.list = [];
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
  Instance.EntFireAtTarget({ target: e, input: "StartSound" });
  log(`music: ${t.id.toUpperCase()} ${t.title}`);
}

function musicNext() {
  if (!music.list.length) {
    music.list = MUSIC_TRACKS.filter((t) => t.pool === music.pool);
    if (!music.list.length) { music.cur = null; return; }
    for (let i = music.list.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [music.list[i], music.list[j]] = [music.list[j], music.list[i]];
    }
    if (music.list.length > 1 && music.list[0].id === music.last) music.list.push(music.list.shift());
  }
  musicPlay(music.list.shift());
}

function musicTick(now) {
  if (music.cur && now >= music.endsAt) musicNext();
}

function musicStop() {
  if (music.cur) {
    const e = live(Instance.FindEntityByName(CONFIG.MUSIC_PREFIX + music.cur.id));
    if (e) Instance.EntFireAtTarget({ target: e, input: "StopSound" });
  }
  music.pool = ""; music.list = []; music.cur = null;
}
