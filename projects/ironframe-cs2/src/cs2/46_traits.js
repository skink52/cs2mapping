// ===================================================================================================================
// IRONFRAME CS2 adapter: frame traits (core rules in src/core/87_traits.js). Reads the held F key (Legion gun shield, Warden
// aegis pulse, Bastion siege mode; the core also sees the Ctrl double-tap and JUMP edges from the normal input) and turns
// {t:'trait'} events into a HUD line, a tone and a spark / boom pulse. Spotter marks show on allies' radars through
// 45_features.js featPinged (m.markT / m.markTeam); the marked pilot and the shielded allies get a line of their own. Hooks: 45_features.js featInput -> traitInput(pe, input); 90_main.js handleEvent -> traitEvent(ev).
// ===================================================================================================================
const TRAIT_LINES = {
  krasnaya: { fire: 'OPENER: +20% hit' },
  lisa: { fire: 'DOUBLE JUMP' },
  atlas: { on: 'FIELD REPAIR ON', off: 'FIELD REPAIR OFF' },
  barbatos: { fire: 'LIFESTEAL' },
  mule: { on: 'BRACED: -30% damage', off: '' },
  legion: { on: 'GUN SHIELD UP', off: 'GUN SHIELD DOWN' },
  ronin: { on: 'PHASE DASH', off: '' },
  me3atlas: { on: 'HARDENED: stagger immune 3 s', off: '' },
  sandviper: { on: 'TARGET MARKED: +10% damage', off: '' },
  kestrel: { fire: 'SLIPSTREAM: -35% damage' },
  warden: { on: 'AEGIS PULSE', off: '' },
  bastion: { on: 'SIEGE MODE: +20% damage', off: 'SIEGE MODE OFF' },
};
const TRAIT_QUIET = { atlas: 1, kestrel: 1 };   // no pulse / tone (they fire often or are passive)
const traitLast = new Map();   // slot -> gameTime of the last HUD line (lifesteal / opener fire often)

function traitInput(pe, input) {
  const pawn = /** @type {any} */ (pe).pawn;
  input.cycleHeld = !!(pawn && pawn.IsInputPressed(KEYS.cycle));
}

function traitEvent(ev) {
  if (ev.t !== 'trait') return;
  const t = TRAIT_LINES[ev.key], line = t && t[ev.phase];
  const m = game.mechs.get(ev.slot); if (!m) return;
  const now = gameTime();
  if (line) {
    const last = traitLast.get(ev.slot) || -9;
    if (now - last > 0.8 || ev.phase !== 'fire') { reply(ev.slot, line, 2); traitLast.set(ev.slot, now); }
  }
  if (ev.key === 'sandviper' && ev.phase === 'on' && ev.target >= 0) { const t = game.mechs.get(ev.target); if (t && t.human) { reply(ev.target, 'MARKED: the enemy team sees you', 2); sndTone(ev.target, 'ui_capture'); } }
  if (ev.key === 'warden' && ev.phase === 'on' && ev.allies) for (const s of ev.allies) reply(s, 'AEGIS: barrier from a Warden', 2);
  const c = v3(m.pos.x, m.pos.y, m.pos.z + 120);
  if (ev.phase === 'on' || ev.phase === 'fire') {
    if (TRAIT_QUIET[ev.key]) return;
    const big = ev.key === 'legion' || ev.key === 'mule' || ev.key === 'warden' || ev.key === 'bastion';
    pfxBurst(big ? 'boom' : 'spark', c, ev.key === 'legion' || ev.key === 'warden' ? 0.8 : 0.5);
    if (ev.key !== 'barbatos' && ev.key !== 'krasnaya') sndTone(ev.slot, 'ui_capture');
  }
}
