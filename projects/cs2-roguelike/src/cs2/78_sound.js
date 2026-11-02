// ===================================================================================
// CS2 adapter, part 3c: sounds. One point_soundevent per event in the map (nt_snd_nt_<name>, hot ones have _b/_c copies); a sound at a
// point borrows a pooled null prop as its source (SetSourceEntity takes an entity name; the pool props are named nt_pool_<i>).
// UI stingers (nt.ui.*) are flat events started without a source. Capped per tick; a dry pool drops the sound rather than spawning.
// ===================================================================================
const SND = { ev: new Map(), ui: new Map(), live: [], perTick: 0, rr: new Map(), ready: false };
const SND_HOT = new Set(['enemy_hit', 'enemy_die', 'sentinel_shot', 'bolt_hit', 'drone_lunge']);

function sndInit() {
  SND.ev.clear(); SND.ui.clear();
  for (const name of SOUNDS.sfx) {
    const list = [];
    for (const suf of ['', '_b', '_c']) { const e = Instance.FindEntityByName(`nt_snd_nt_${name}${suf}`); if (e) list.push(e); }
    if (list.length) SND.ev.set(name, list); else E.missing.push(`nt_snd_nt_${name}`);
  }
  for (const name of SOUNDS.ui) { const e = Instance.FindEntityByName(`nt_snd_nt_ui_${name}`); if (e) SND.ui.set(name, e); else E.missing.push(`nt_snd_nt_ui_${name}`); }
  SND.live.length = 0; SND.ready = SND.ev.size > 0;
}

function sfx(name, pos, hold) {
  const list = SND.ev.get(name); if (!list || SND.perTick >= 16) return null;
  const k = (SND.rr.get(name) || 0) % list.length; SND.rr.set(name, k + 1);
  const snd = list[k];
  // a held sound (the exit beacon loop) keeps a pool prop as its source; one-shots use the anchor ring
  const anchor = hold ? poolTake(NULL_MODEL, { x: pos.x, y: pos.y, z: pos.z }) : anchorAt(pos); if (!anchor) return null;
  try {
    Instance.EntFireAtTarget({ target: snd, input: 'SetSourceEntity', value: hold ? `${CONFIG.TAG}_pool_${anchor.id}` : anchor.name });
    Instance.EntFireAtTarget({ target: snd, input: 'StartSound' });
  } catch (e) { if (hold) poolGive(anchor, false); return null; }
  SND.perTick++;
  if (!hold) return { anchor: null, snd, until: 0 };
  const h = { anchor, snd, until: Infinity };
  SND.live.push(h); return h;
}
function sfxStop(h) {
  if (!h) return;
  try { Instance.EntFireAtTarget({ target: h.snd, input: 'StopSound' }); } catch (e) { /* */ }
  h.until = -1;
}
function ui(name) {
  const e = SND.ui.get(name); if (!e) return;
  try { Instance.EntFireAtTarget({ target: e, input: 'StartSound' }); } catch (e2) { /* */ }
}
function sndTick() {
  SND.perTick = 0;
  for (let i = SND.live.length - 1; i >= 0; i--) {
    const h = SND.live[i];
    if (E.now > h.until) { if (h.anchor) poolGive(h.anchor, false); SND.live.splice(i, 1); }
  }
}
function sndReset() { SND.live.length = 0; }
