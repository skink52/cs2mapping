// ---------------------------------------------------------------- sounds
// One point_soundevent per sound (spr_snd_<name>) in the map. A sound is played by pointing it at a source entity
// (a car's prop, or an anchor prop moved to the spot) and firing StartSound.

const soundEnts = new Map();
let soundsThisTick = 0;

const soundChecked = new Map();   // sfx -> tick its entity was last checked
function soundEnt(sfx) {
  let e = soundEnts.get(sfx);
  if (e && soundChecked.get(sfx) === tickNo) return e;
  e = live(e);
  soundChecked.set(sfx, tickNo);
  if (!e) {
    e = live(Instance.FindEntityByName(CONFIG.SOUND_PREFIX + sfx));
    if (!e) { warnOnce('snd' + sfx, 'no point_soundevent named ' + CONFIG.SOUND_PREFIX + sfx); return undefined; }
    soundEnts.set(sfx, e);
  }
  return e;
}

class AnchorRing {
  constructor() { this.items = []; this.next = 0; }
  get(pos) {
    let a = this.items[this.next];
    if (!a || !live(a.ent)) {
      a = takeProp();
      if (!a) return undefined;
      a.hidden = false;
      try { a.ent.SetModel(NULL_MODEL); } catch (err) { /* ignore */ }
      this.items[this.next] = a;
    }
    this.next = (this.next + 1) % 16;
    a.ent.Teleport({ position: pos });
    return a;
  }
  release() { for (const a of this.items) if (a) releaseProp(a); this.items = []; }
}

// play `sfx` at a car (its prop is the source) or at a track-local point
function playSound(view, sfx, car, x, y, z) {
  if (soundsThisTick >= CONFIG.MAX_SOUNDS_PER_TICK) return;
  const snd = soundEnt(sfx);
  if (!snd) return;
  let srcName = null;
  if (car) {
    const p = view.props.get(car.slot);
    if (p && !p.hidden) srcName = p.name;      // (the renderer keeps its props checked)
    else { x = car.x; y = car.y; z = car.z; }
  }
  if (!srcName) {
    if (!view.anchors) view.anchors = new AnchorRing();
    const a = view.anchors.get(view.world(x, y, z + 20));
    if (!a) return;
    srcName = a.name;
  }
  soundsThisTick++;
  Instance.EntFireAtTarget({ target: snd, input: 'SetSourceEntity', value: srcName });
  Instance.EntFireAtTarget({ target: snd, input: 'StartSound' });
}
