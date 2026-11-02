// ---------------------------------------------------------------- 1.6 radio and item sounds
// One point_soundevent per sound (cs16_snd_<name>) in the map, playing the 1.6 wav (tools/sounds.py). A sound meant for
// one player plays at their own pawn with a short reach (heard there at full volume, gone within a few metres).
// Players standing together share one copy, so a crowd at spawn doesn't hear the radio ten times over.

const SND_ALIAS = { ammo: '9mmclip1', kevlar: 'tr_kevlar', gunpickup: 'gunpickup2' };
const soundEnts = new Map();
const soundChecked = new Map();
let soundsThisTick = 0;

function soundEnt(name) {
  let e = soundEnts.get(name);
  if (e && soundChecked.get(name) === tickNo) return e;
  e = live(e);
  soundChecked.set(name, tickNo);
  if (!e) {
    e = live(Instance.FindEntityByName(CONFIG.SOUND_PREFIX + name));
    if (!e) { warnOnce('snd' + name, 'no point_soundevent named ' + CONFIG.SOUND_PREFIX + name); return undefined; }
    soundEnts.set(name, e);
  }
  return e;
}

function pawnName(slot) { return 'cs16_pawn_' + slot; }

const soundQueue = [];          // [list, name] that didn't fit in a tick
function flushSounds() {
  const q = soundQueue.splice(0);
  for (const [list, name] of q) playToMany(list, name);
}
function playToMany(list, name) {
  if (!CONFIG.SOUNDS) return;
  const snd = soundEnt(SND_ALIAS[name] || name);
  if (!snd) return;
  const near = CONFIG.SOUND_SHARE * CONFIG.SOUND_SHARE;
  const used = [];
  for (const rec of list) {
    if (!rec.alive || !rec.pos || !rec.pawn) continue;
    if (soundsThisTick >= CONFIG.MAX_SOUNDS_PER_TICK) { soundQueue.push([list.slice(list.indexOf(rec)), name]); return; }
    let shared = false;
    for (const p of used) {
      const dx = p.x - rec.pos.x, dy = p.y - rec.pos.y, dz = p.z - rec.pos.z;
      if (dx * dx + dy * dy + dz * dz < near) { shared = true; break; }
    }
    if (shared) continue;
    used.push(rec.pos);
    soundsThisTick++;
    Instance.EntFireAtTarget({ target: snd, input: 'SetSourceEntity', value: pawnName(rec.slot) });
    Instance.EntFireAtTarget({ target: snd, input: 'StartSound' });
  }
}
function playTo(rec, name) { playToMany([rec], name); }
