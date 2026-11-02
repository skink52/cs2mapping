// ---------------------------------------------------------------- sounds
// One point_soundevent per Doom sound (fdm_snd_<name>) placed in the map. A sound is played by
// pointing it at a source entity - the prop of the thing that made it, or an anchor prop moved
// to the spot - and firing StartSound (the same way Valve's chess demo does it).

const soundEnts = new Map();
let soundsThisTick = 0;

function soundEnt(sfx) {
  let e = live(soundEnts.get(sfx));
  if (!e) {
    e = live(Instance.FindEntityByName(CONFIG.SOUND_PREFIX + sfx));
    if (!e) { warnOnce("snd" + sfx, "no point_soundevent named " + CONFIG.SOUND_PREFIX + sfx); return undefined; }
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
    this.next = (this.next + 1) % 24;
    a.ent.Teleport({ position: pos });
    return a;
  }
  release() { for (const a of this.items) if (a) releaseProp(a); this.items = []; }
}

function playSound(view, e) {
  if (soundsThisTick >= CONFIG.MAX_SOUNDS_PER_TICK) return;
  const snd = soundEnt(e.sfx);
  if (!snd) return;
  let srcName = null;
  if (e.mo && !e.mo.removed) {
    const p = view.props.get(e.mo.id);
    if (p && live(p.ent)) srcName = p.name;
  }
  if (!srcName) {
    if (!view.anchors) view.anchors = new AnchorRing();
    const a = view.anchors.get(view.world(e.x, e.y, e.z));
    if (!a) return;
    srcName = a.name;
  }
  soundsThisTick++;
  Instance.EntFireAtTarget({ target: snd, input: "SetSourceEntity", value: srcName });
  Instance.EntFireAtTarget({ target: snd, input: "StartSound" });
}
