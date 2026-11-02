// ---------------------------------------------------------------- CS2 pawns: parking, chase camera, input
// While the map runs, every CS2 pawn stands frozen and invisible in a sealed booth. The script reads its
// buttons; the view is a custom camera the script places behind the player's car (or the car they watch).

const parked = new Map();     // slot -> { pawn, cam, booth, camMode, camYaw, lastYaw, lastPitch }
let boothEnt;

function boothPos(slot) {
  boothEnt = live(boothEnt) || live(Instance.FindEntityByName(CONFIG.BOOTH));
  const o = boothEnt ? boothEnt.GetAbsOrigin() : { x: 0, y: 0, z: -14000 };
  const col = slot % 8, row = Math.floor(slot / 8) % 8;
  return { x: o.x + (col - 3.5) * 80, y: o.y + (row - 3.5) * 80, z: o.z + 4 };
}

// park(slot, verify): the parked entry for a player, parking their pawn first if needed. The entry is trusted between
// checks - CS2's events (respawn, death, team change, disconnect) drop it, and an engine call that fails on it drops it
// too - so the pawn and camera are only looked up again when verify is set (every 8th tick per player, see
// verifyTurn) or when there is no entry. After a failed lookup (no pawn: spectator team, not spawned) the next one
// waits 8 ticks; a spawn parks at once through OnPlayerReset.
const noPawnUntil = new Map();   // slot -> tickNo of the next lookup
function verifyTurn(slot) { return ((tickNo + slot) & 7) === 0; }
function park(slot, verify) {
  let pk = parked.get(slot);
  if (pk && !verify) return pk;
  if (!pk && !verify && (noPawnUntil.get(slot) || 0) > tickNo) return undefined;
  const pawn = pawnOf(slot);
  if (!pawn) { noPawnUntil.set(slot, tickNo + 8); return undefined; }
  noPawnUntil.delete(slot);
  if (pk && pk.pawn === pawn && live(pk.cam)) return pk;
  const booth = boothPos(slot);
  guard('park', () => {
    pawn.Teleport({ position: booth, velocity: { x: 0, y: 0, z: 0 } });
    pawn.SetMoveType(CSMoveType.NONE);
    pawn.DestroyWeapons();
  });
  if (CONFIG.HIDE_OWN_BODY) guard('hidebody', () => pawn.SetColor({ r: 255, g: 255, b: 255, a: 0 }));
  let cam;
  guard('camera', () => {
    cam = live(pawn.GetCustomCamera());
    if (cam) { cam.SetParent(undefined); cam.SetMode(CustomCameraMode.CONTROLLED); }
  });
  if (!cam) warnOnce('nocam', 'GetCustomCamera returned nothing - players will see their pawn in the booth');
  const eye = guard('eye', () => pawn.GetEyeAngles()) || { yaw: 0, pitch: 0 };
  pk = { pawn, cam, booth, camMode: CustomCameraMode.CONTROLLED, camYaw: null, lastYaw: eye.yaw, lastPitch: eye.pitch, edges: {},
    shakeUntil: 0, shakeLen: 0, shakeAmp: 0, tubeK: 0, bankRoll: 0, flyH: undefined, camKey: null };
  parked.set(slot, pk);
  return pk;
}

function unpark(slot) {
  const pk = parked.get(slot);
  parked.delete(slot);
  hudOff(slot);
  if (!pk) return;
  guard('unpark', () => {
    if (live(pk.cam)) { pk.cam.SetMode(CustomCameraMode.DISABLED); if (live(pk.pawn)) pk.cam.SetParent(pk.pawn); }
    if (live(pk.pawn) && pk.pawn.IsAlive()) pk.pawn.SetMoveType(CSMoveType.WALK);
    if (CONFIG.HIDE_OWN_BODY && live(pk.pawn)) pk.pawn.SetColor({ r: 255, g: 255, b: 255, a: 255 });
  });
}

// racing input -> the car's command; returns true when the player did anything (AFK tracking)
// (each read is a call into CS2: BACK is only read when W isn't held, the view angles only when no key is - they are
// only there to notice someone idle)
function sampleInput(slot, car, pk) {
  const pawn = pk.pawn;
  const fwd = pawn.IsInputPressed(CSInputs.FORWARD), back = !fwd && pawn.IsInputPressed(CSInputs.BACK);
  const left = pawn.IsInputPressed(CSInputs.LEFT), right = pawn.IsInputPressed(CSInputs.RIGHT);
  const c = car.cmd;
  c.throttle = fwd ? 1 : back ? -1 : 0;
  c.steer = (left ? 1 : 0) - (right ? 1 : 0);      // + = turn left (yaw grows anticlockwise, seen from above)
  c.boost = pawn.IsInputPressed(CSInputs.ATTACK);
  c.drift = pawn.IsInputPressed(CSInputs.JUMP) || pawn.IsInputPressed(CSInputs.DUCK);
  if (pawn.WasInputJustPressed(CSInputs.ATTACK2)) c.spin = true;
  if (pawn.WasInputJustPressed(CSInputs.USE)) c.ability = true;          // the car's E ability
  // the clean start: say why a spin (or a Meteor's Shockwave) does nothing yet
  if (car.lock > 0 && car.racing && (c.spin || (c.ability && car.spec.ability === 'quake'))) bottom(slot, 'ATTACKS UNLOCK IN ' + Math.ceil(car.lock), 1);
  if (fwd || back || left || right || c.boost || c.drift || c.spin || c.ability) return true;
  return looked(pk, true);
}
// the view turned (or tilted) more than 2 degrees since the last look: someone is there
function looked(pk, pitchToo) {
  const ang = pk.pawn.GetEyeAngles();
  const moved = Math.abs(angleDiff(pk.lastYaw, ang.yaw)) > 2 || (pitchToo && Math.abs(ang.pitch - pk.lastPitch) > 2);
  pk.lastYaw = ang.yaw; pk.lastPitch = ang.pitch;
  return moved;
}

// Keys pressed this tick, as a bitmask of CSInputs. CS2 lets one call ask about several keys at once; it almost
// certainly means "any of them", but that isn't documented, so the script finds out from the first single key press
// it sees (one key down: the call for all the keys says whether "any" is what it does). Until then, and for good if
// it means something else, each key is asked about on its own. Once known, an idle player costs one call a tick
// instead of one per key.
let maskAny = null;            // null = not known yet, true = a mask means "any of these", false = it doesn't
function justPressed(pawn, keys, mask) {
  if (maskAny === true && !pawn.WasInputJustPressed(mask)) return 0;
  let m = 0;
  for (const k of keys) if (pawn.WasInputJustPressed(k)) m |= k;
  if (maskAny === null && m && (m & (m - 1)) === 0) {
    maskAny = !!pawn.WasInputJustPressed(mask);
    log('CS2 input masks mean ' + (maskAny ? '"any of these keys"' : 'something else') + (maskAny ? ' - idle players now cost one input call a tick' : ' - keys are read one at a time'));
  }
  return m;
}
// any of these keys held (the same check, for IsInputPressed)
function anyPressed(pawn, keys, mask) {
  if (maskAny !== false) return pawn.IsInputPressed(mask);
  for (const k of keys) if (pawn.IsInputPressed(k)) return true;
  return false;
}
const PICK_KEYS = [CSInputs.LEFT, CSInputs.RIGHT, CSInputs.USE, CSInputs.RELOAD];
const PICK_MASK = CSInputs.LEFT | CSInputs.RIGHT | CSInputs.USE | CSInputs.RELOAD;
const SPEC_KEYS = [CSInputs.ATTACK, CSInputs.ATTACK2, CSInputs.USE, CSInputs.JUMP, CSInputs.LEFT, CSInputs.RIGHT, CSInputs.RELOAD];
const SPEC_MASK = CSInputs.ATTACK | CSInputs.ATTACK2 | CSInputs.USE | CSInputs.JUMP | CSInputs.LEFT | CSInputs.RIGHT | CSInputs.RELOAD;
const BUSY_KEYS = [CSInputs.FORWARD, CSInputs.BACK, CSInputs.ATTACK, CSInputs.JUMP, CSInputs.USE];
const BUSY_MASK = CSInputs.FORWARD | CSInputs.BACK | CSInputs.ATTACK | CSInputs.JUMP | CSInputs.USE;

// The car picker. It comes up by itself only for someone who has not confirmed a car yet and has not raced (in the
// lobby and on the grid). A / D move through the cars, E confirms and the cards go away; after that they stay away -
// so they never cover the results - until R (or !car) brings them back. hudPicker notes in pe.pickShown whether the
// cards are on screen; A / D and E only work on them while they are.
function pickerAuto(pe) { return !pe.picked && !pe.raced; }
function pickerOpen(pe, now) { return (pe.pickUntil || 0) > now; }

// A / D / E on the picker, R to bring it back; returns true on any input (AFK tracking)
function pickerInput(pe, pk, jp) {
  const pawn = pk.pawn;
  const m = jp === undefined ? justPressed(pawn, PICK_KEYS, PICK_MASK) : jp;
  const l = (m & CSInputs.LEFT) !== 0, r = (m & CSInputs.RIGHT) !== 0, use = (m & CSInputs.USE) !== 0, reload = (m & CSInputs.RELOAD) !== 0;
  const any = l || r || use || reload;
  const now = gameTime();
  if (pe.pickShown) {
    if (l || r) { rm.cycleCar(pe, l ? -1 : 1); pe.pickUntil = now + CONFIG.PICK_SHOW; }   // still choosing: keep them up
    if (use) {
      pe.picked = true; pe.pickUntil = 0; pe.pickShown = false;
      const car = CARS[pe.carChoice] || CARS.hornet;
      bottom(pe.slot, 'YOUR CAR: ' + car.name + ' - E ' + car.abilityName, 3);
    }
  } else if (reload) pe.pickUntil = now + CONFIG.PICK_SHOW;
  if (any || anyPressed(pawn, BUSY_KEYS, BUSY_MASK)) return true;
  return looked(pk, false);
}

function spectatorInput(pe, pk) {
  const m = justPressed(pk.pawn, SPEC_KEYS, SPEC_MASK);
  let any = false;
  if (m & CSInputs.ATTACK) { rm.fixSpectate(pe, 1); any = true; }
  if (m & CSInputs.ATTACK2) { rm.fixSpectate(pe, -1); any = true; }
  // E is the picker's confirm while the cards are up (Space still changes arena)
  if (((m & CSInputs.USE) && !pe.pickShown) || (m & CSInputs.JUMP)) { rm.fixSpectate(pe, 'arena'); any = true; }
  return pickerInput(pe, pk, m) || any;
}

// W / S move a voter's pick on their ballot (the top places of a finished race); true on a press
const VOTE_KEYS = [CSInputs.FORWARD, CSInputs.BACK];
const VOTE_MASK = CSInputs.FORWARD | CSInputs.BACK;
function voteInput(pe, pk) {
  if (!rm.ballotOf(pe)) return false;
  const m = justPressed(pk.pawn, VOTE_KEYS, VOTE_MASK);
  if (m & CSInputs.FORWARD) rm.vote(pe, -1);
  if (m & CSInputs.BACK) rm.vote(pe, 1);
  return m !== 0;
}

// camera shake (hits, landings, wrecks): a few units of jitter that dies away
function shake(slot, secs, amp) {
  const pk = parked.get(slot);
  if (!pk || !CONFIG.CAM_SHAKE) return;
  const now = gameTime();
  if (pk.shakeUntil && now < pk.shakeUntil && pk.shakeAmp > amp) return;
  pk.shakeUntil = now + secs; pk.shakeLen = secs; pk.shakeAmp = amp * CONFIG.CAM_SHAKE;
}
function shakeOffset(pk) {
  if (!pk.shakeUntil) return null;
  const now = gameTime();
  const left = pk.shakeUntil - now;
  if (left <= 0) { pk.shakeUntil = 0; return null; }
  const k = pk.shakeAmp * (left / pk.shakeLen);
  return { x: Math.sin(now * 91) * k, y: Math.sin(now * 77 + 1) * k, z: Math.sin(now * 103 + 2) * k * 0.7 };
}

// chase camera behind a car (own or watched). The yaw eases towards the car's heading, turned a little into the bend
// ahead so the upcoming track stays in view; it pulls back at speed; a little roll in corners.
function placeCamera(pk, car, view, dt, preset, tilt) {
  if (!pk.cam) return;
  const cp = CONFIG.CAMERAS[preset] || CONFIG.CAMERAS[CONFIG.CAM_DEFAULT] || { back: 300, up: 175, pitch: 16, speedBack: 70 };
  const T = view.arena.track;
  const ahead = T.point(car.s + 500 + car.speed * 0.5);
  const toAhead = Math.atan2(ahead.y - car.y, ahead.x - car.x);
  const target = car.state === 'falling' ? car.yaw : car.yaw + normRad(toAhead - car.yaw) * CONFIG.CAM_LOOKAHEAD;
  if (pk.camYaw === null || car.fx & 128 || car.state === 'grid') pk.camYaw = target;
  else pk.camYaw += normRad(target - pk.camYaw) * Math.min(1, CONFIG.CAM_TURN * dt);
  const cy = pk.camYaw;
  const sp = clamp(car.speed / Math.max(1, car.spec.maxSpeed), 0, 1.5);
  let back = cp.back + cp.speedBack * sp, up = cp.up;
  // inside a tube the camera drops and closes in so it stays under the roof
  const inTube = T.tube[car.seg] || T.tube[(car.seg + T.n - 4) % T.n];
  pk.tubeK = (pk.tubeK || 0) + ((inTube ? 1 : 0) - (pk.tubeK || 0)) * Math.min(1, dt * 3);
  if (pk.tubeK > 0.001) { up = lerp(up, Math.min(up, CONFIG.CAM_TUBE_UP), pk.tubeK); back = lerp(back, Math.min(back, CONFIG.CAM_TUBE_BACK), pk.tubeK); }
  // in the air the camera follows the car's height but not its bounces
  const cz = car.air && !car.fly ? Math.max(car.tz, car.z - 40) : car.z;
  const pos = view.world(car.x - Math.cos(cy) * back, car.y - Math.sin(cy) * back, cz + up);
  const sh = shakeOffset(pk);
  if (sh) { pos.x += sh.x; pos.y += sh.y; pos.z += sh.z; }
  // lean (+ = tilt right): a share of a banked road's angle plus a little into the turn, smoothed; !tilt turns it off
  const lean = car.air || car.state === 'falling' || car.spinTimer > 0 || tilt === false ? 0
    : -deg(Math.atan(car.bank)) * CONFIG.CAM_BANK + clamp(-(car.yawRate || 0) * CONFIG.CAM_LEAN, -CONFIG.CAM_ROLL, CONFIG.CAM_ROLL);
  pk.bankRoll = (pk.bankRoll || 0) + (lean - (pk.bankRoll || 0)) * Math.min(1, dt * 4);
  const roll = pk.bankRoll * CONFIG.CAM_ROLL_SIGN;
  const pitch = cp.pitch + (car.state === 'falling' ? Math.min(40, car.stateTime * 30) : 0);
  if (pk.camMode !== CustomCameraMode.CONTROLLED) { pk.cam.SetMode(CustomCameraMode.CONTROLLED); pk.camMode = CustomCameraMode.CONTROLLED; }
  pk.cam.Move({ position: pos, angles: { pitch, yaw: deg(cy), roll } });
}

// grid flyover: before the last seconds of the countdown the camera swoops low along the track towards the grid,
// looking back at the waiting field, then cuts to the chase camera
function placeFlyover(pk, arena, view, now) {
  if (!pk.cam) return;
  const T = arena.track;
  const total = arena.cfg.countdownTics, left = arena.countdown;
  const span = total - CONFIG.FLYOVER_CUT * TICRATE;
  const t = clamp((total - left) / Math.max(1, span), 0, 1);
  const e = 1 - (1 - t) * (1 - t) * (1 - t);             // ease out: fast at first, settling over the grid
  const s = CONFIG.FLYOVER_FROM * (1 - e) + 250;         // progress ahead of the start line
  const p = T.point(s), q = T.point(s - 600);
  let hT = 160 + 520 * (1 - e);
  // stay under the roof where the road runs through a tube
  for (let k = -10; k <= 10; k += 2) if (T.tube[((p.i + k) % T.n + T.n) % T.n]) { hT = Math.min(hT, 170); break; }
  if (pk.flyH === undefined || left >= total - 1) pk.flyH = hT;
  pk.flyH += (hT - pk.flyH) * 0.12;
  const h = pk.flyH;
  const pos = view.world(p.x, p.y, p.z + h);
  const look = Math.atan2(q.y - p.y, q.x - p.x);
  const pitch = deg(Math.atan2(h - 40, 900));
  if (pk.camMode !== CustomCameraMode.CONTROLLED) { pk.cam.SetMode(CustomCameraMode.CONTROLLED); pk.camMode = CustomCameraMode.CONTROLLED; }
  pk.cam.Move({ position: pos, angles: { pitch, yaw: deg(look), roll: Math.sin(now * 0.7) * 3 } });
  pk.camYaw = null;
}

// results / nothing to follow: a slow circle round the start gantry, high enough to see the field warp out, rising
// over any road the circle passes (Crosswire's loop is close to its start). Heights per track, worked out once.
const OV_R = 1500, OV_N = 64;
const ovHeights = new Map();
function overviewHeights(T) {
  let hs = ovHeights.get(T.id);
  if (hs) return hs;
  const p = T.point(0);
  hs = [];
  for (let k = 0; k < OV_N; k++) {
    const a = 2 * Math.PI * k / OV_N, cx = p.x + Math.cos(a) * OV_R, cy = p.y + Math.sin(a) * OV_R;
    let h = 650;
    for (let i = 0; i < T.n; i++) if (Math.hypot(T.x[i] - cx, T.y[i] - cy) - T.hw[i] < 500) h = Math.max(h, T.z[i] - p.z + 380);
    hs.push(h);
  }
  // widen the rises a little, then smooth them so the camera eases up and down
  hs = hs.map((_, k) => Math.max(hs[(k + OV_N - 2) % OV_N], hs[(k + OV_N - 1) % OV_N], hs[k], hs[(k + 1) % OV_N], hs[(k + 2) % OV_N]));
  for (let pass = 0; pass < 4; pass++) hs = hs.map((v, k) => (hs[(k + OV_N - 1) % OV_N] + 2 * v + hs[(k + 1) % OV_N]) / 4);
  ovHeights.set(T.id, hs);
  return hs;
}
function placeOverviewCamera(pk, arena, view) {
  if (!pk.cam) return;
  const T = arena.track;
  const p = T.point(0);
  const ang = gameTime() * 0.12;
  const hs = overviewHeights(T);
  const f = (((ang / (2 * Math.PI)) % 1) + 1) % 1 * OV_N, k0 = Math.floor(f) % OV_N, w = f - Math.floor(f);
  const h = hs[k0] + (hs[(k0 + 1) % OV_N] - hs[k0]) * w;
  const r = OV_R;
  const pos = view.world(p.x + Math.cos(ang) * r, p.y + Math.sin(ang) * r, p.z + h);
  if (pk.camMode !== CustomCameraMode.CONTROLLED) { pk.cam.SetMode(CustomCameraMode.CONTROLLED); pk.camMode = CustomCameraMode.CONTROLLED; }
  pk.cam.Move({ position: pos, angles: { pitch: deg(Math.atan2(h - 250, r)), yaw: deg(ang + Math.PI), roll: 0 } });
  pk.camYaw = null;
}
