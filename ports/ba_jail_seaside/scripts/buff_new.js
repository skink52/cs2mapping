// buff_new.js  --  ba_jail_seaside
//
// Weapon buffs, identified by the MAP ENTITY rather than by the weapon class.
//
// THE IDEA
// Naming the weapons in Hammer doesn't let us recognise them after pickup - CS2
// doesn't preserve a weapon's targetname through being picked up (tested). But
// it doesn't need to. Instead of asking "is the weapon in this player's hands
// the special one?", this script watches the named entity while it is still
// lying on the ground and notes WHO TAKES IT. From then on the buff belongs to
// that player, and what they're carrying stops mattering.
//
// That removes the need for the whole apparatus the old script had grown: no
// pickup-zone trigger, no stripping loadout copies, no claim queue, no
// eligibility windows. A Last Request scout, an admin handout or a loadout copy
// simply never enters the picture, because nobody ever took the map's entity.
//
// Setup:
//   1. Put this file in  content/csgo_addons/ba_jail_seaside/scripts/
//   2. Add a point_script entity with "cs_script" = scripts/buff_new.vjs
//   3. Name the map's weapons in Hammer to match the keys in BUFFS below.
//   4. Remove the old buff_weapons point_script, or the two will fight.

import { Instance, CSInputs, CSGearSlot } from "cs_script/point_script";

// ----- config ---------------------------------------------------------------
// Keyed by the weapon's targetname in Hammer.
//   invisible     : hide the player model
//   hideHolstered : false = only the weapon in their hands is hidden; anything
//                   holstered on their body stays visible. true (or left out)
//                   = hide everything they carry.
//   glow          : { color, range } - an outline glow on the invisible player,
//                   only drawn for viewers within `range` units. Leave out for
//                   no glow.
//   speedMult     : movement speed multiplier
//   disguise      : a prop that follows the holder around. It's a prop_dynamic
//                   you place in Hammer (see DISGUISE SETUP below); the script
//                   just moves it onto the player and parks it back afterwards.
//       prop      : the prop's targetname
//       offset    : { x, y, z } from the player's feet, in world units
//       behind    : units straight behind the player, turning with their view
//       mode      : "parent" (smooth, the engine carries it) or "follow" (the
//                   script moves it every tick - fallback if parenting fails)
//       hideWhenUnused : alpha it out while nobody has the buff
//
// DISGUISE SETUP (Hammer):
//   prop_dynamic, model models/props_foliage/urban_palm01.vmdl
//   Name: seasidesecret_palm     Solid: Not Solid (the script also fires
//   DisableCollision at it, belt and braces). Put it anywhere out of the way -
//   a closed-off room is ideal. That spot is where it returns between uses.
//
// 1 Hammer unit = 1 inch, so 20 m = 787 units.
const BUFFS = {
  seasidesecret: {
    classname: "weapon_mac10",
    invisible: true,
    hideHolstered: true,
    // A dark green reads as a faint glow. Brighter = "0 255 0".
    glow: { color: "0 110 0", range: 787 },
    speedMult: 2.5,
    disguise: {
      prop: "seasidesecret_palm",
      offset: { x: 0, y: 0, z: 0 },
      behind: 10,   // units straight behind the player (180 degrees from their view)
      // "follow" = script moves it every tick (known to show up).
      // "parent" = attach to the player - smoother in theory, but it went
      // missing in testing, so it's opt-in until disguise_dump shows why.
      mode: "follow",
      hideWhenUnused: true,
    },
  },
  // Old skylight weapons, kept for reference:
  // invisscout: { classname: "weapon_ssg08", invisible: true },
  // speedmp5:   { classname: "weapon_mp5sd", speedMult: 2.5 },
};

const DEBUG        = false;   // set false once it's working
const HIDE_WEAPONS = true;   // hide held and holstered weapons, not just the player
const GROUND_ONLY  = false;  // don't boost mid-air
const USE_TELEPORT = false;  // if Move() looks rubber-bandy, try Teleport()

// Keep the buff alive while the holder still carries a weapon of that class.
// false = the buff sticks to them for the round no matter what they drop.
const DROP_ENDS_BUFF = true;

// When the holder loses it, adopt the dropped weapon so the next person to take
// it inherits the buff. Looks for an ownerless weapon of the right class near
// where the holder was standing.
const REARM_ON_DROP  = false;
const REARM_RADIUS   = 300;

const BASE_RUN_SPEED = 250;
const RAMP           = 1.10;
// ----------------------------------------------------------------------------

function log(text) { if (DEBUG) Instance.Msg(`[buffs] ${text}`); }

log("script loaded");

const GEAR_SLOTS = [
  CSGearSlot.RIFLE, CSGearSlot.PISTOL, CSGearSlot.KNIFE,
  CSGearSlot.GRENADES, CSGearSlot.C4, CSGearSlot.BOOSTS,
];

// FindWeaponBySlot returns only one weapon per slot, so things sharing a slot
// get missed - the medi-shot and spare grenades especially.
const EXTRA_HIDE = [
  "weapon_healthshot", "weapon_flashbang", "weapon_hegrenade", "weapon_smokegrenade",
  "weapon_molotov", "weapon_incgrenade", "weapon_decoy", "weapon_taser", "weapon_c4",
];

const OPAQUE = { r: 255, g: 255, b: 255, a: 255 };
const CLEAR  = { r: 255, g: 255, b: 255, a: 0 };

// The player's own alpha while invisible. 0 is fully invisible, but if the
// engine skips drawing a fully transparent model it may skip its glow too - if
// the glow doesn't show up in testing, try 1..5 here (still effectively unseen).
const INVISIBLE_PLAYER_ALPHA = 0;
const PLAYER_CLEAR = { r: 255, g: 255, b: 255, a: INVISIBLE_PLAYER_ALPHA };

// targetname -> { entity, lastSeenAt, holder, hidden, sweepAt }
//   entity  : the weapon on the ground we're watching, while nobody has it
//   holder  : { slot, pawn } once someone has taken it
//   hidden  : Map<classname, weapon> of things we alpha'd out, so we can restore
const state = new Map();

let lastThink = 0;

function show(ent) { if (ent && ent.IsValid()) ent.SetColor(OPAQUE); }
function hide(ent) { if (ent && ent.IsValid()) ent.SetColor(CLEAR); }

function slotOf(pawn) {
  const controller = pawn.GetPlayerController();
  return controller ? controller.GetPlayerSlot() : undefined;
}

function nameOf(pawn) {
  const controller = pawn.GetPlayerController();
  return controller ? controller.GetPlayerName() : "?";
}

function entryFor(targetname) {
  let entry = state.get(targetname);
  if (!entry) {
    entry = { entity: undefined, holder: undefined, hidden: new Map(), sweepAt: 0 };
    state.set(targetname, entry);
  }
  return entry;
}

/** Everyone alive who is carrying this weapon class right now. */
function holdersOf(classname) {
  const found = [];
  for (const controller of Instance.GetAllPlayerControllers()) {
    if (!controller.IsConnected()) continue;
    const pawn = controller.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) continue;
    const weapon = pawn.FindWeapon(classname);
    if (weapon && weapon.IsValid()) found.push({ slot: controller.GetPlayerSlot(), pawn });
  }
  return found;
}

function stillCarrying(pawn, classname) {
  const weapon = pawn.FindWeapon(classname);
  return !!weapon && weapon.IsValid();
}

// ----- effects --------------------------------------------------------------

function hideOne(entry, weapon) {
  if (!weapon || !weapon.IsValid()) return;
  hide(weapon);
  entry.hidden.set(weapon.GetClassName(), weapon);
}

// ----- glow -----------------------------------------------------------------
// Uses the model-entity glow inputs. The range is enforced by the engine per
// viewer, which is what lets it be visible nearby and nothing further out.

function startGlow(entry, pawn, glow) {
  if (!glow || entry.glowing || !pawn.IsValid()) return;
  Instance.EntFireAtTarget({ target: pawn, input: "SetGlowOverride", value: glow.color });
  Instance.EntFireAtTarget({ target: pawn, input: "SetGlowRange", value: String(glow.range) });
  Instance.EntFireAtTarget({ target: pawn, input: "StartGlowing" });
  entry.glowing = true;
  log(`glow on ${nameOf(pawn)} (${glow.color}, ${glow.range} units)`);
}

function stopGlow(entry, pawn) {
  if (!entry.glowing) return;
  entry.glowing = false;
  if (pawn && pawn.IsValid()) Instance.EntFireAtTarget({ target: pawn, input: "StopGlowing" });
}

// ----- disguise prop --------------------------------------------------------
// Parented to the player where possible (see "parent mode" below), with a
// per-tick Teleport follow as the fallback.

function disguiseEntity(entry, disguise) {
  if (entry.disguiseEnt && entry.disguiseEnt.IsValid()) return entry.disguiseEnt;

  const ent = Instance.FindEntityByName(disguise.prop);
  if (!ent || !ent.IsValid()) {
    if (!entry.disguiseWarned) {
      Instance.Msg(`[buffs] disguise prop "${disguise.prop}" not found in the map`);
      entry.disguiseWarned = true;
    }
    return undefined;
  }

  entry.disguiseEnt = ent;
  entry.disguiseWarned = false;
  // Remember where it was placed, so it can go back there between uses.
  const o = ent.GetAbsOrigin();
  const a = ent.GetAbsAngles();
  entry.disguiseHome = {
    position: { x: o.x, y: o.y, z: o.z },
    angles: { pitch: a.pitch, yaw: a.yaw, roll: a.roll },
  };
  Instance.EntFireAtTarget({ target: ent, input: "DisableCollision" });
  return ent;
}

/** Nobody has the buff: make sure the prop is parked and (optionally) hidden. */
function parkDisguise(entry, disguise) {
  if (!disguise || entry.disguiseParked) return;
  const ent = disguiseEntity(entry, disguise);
  if (!ent) return;
  if (disguise.hideWhenUnused) ent.SetColor(CLEAR);
  entry.disguiseParked = true;
}

// Where the prop sits relative to the player, in the player's own frame:
// +x forward, +y left, +z up. "behind" is simply negative x.
function localOffset(disguise) {
  const off = disguise.offset || { x: 0, y: 0, z: 0 };
  return { x: off.x - (disguise.behind || 0), y: off.y, z: off.z };
}

/** The world position/angles the prop should have for a given facing. */
function worldPlacement(pawn, disguise, yaw) {
  const o = pawn.GetAbsOrigin();
  const local = localOffset(disguise);
  const r = (yaw * Math.PI) / 180;
  const cos = Math.cos(r);
  const sin = Math.sin(r);
  return {
    position: {
      x: o.x + local.x * cos - local.y * sin,
      y: o.y + local.x * sin + local.y * cos,
      z: o.z + local.z,
    },
    angles: { pitch: 0, yaw, roll: 0 },
  };
}

// ---- parent mode -----------------------------------------------------------
// Parenting is what makes it smooth: the engine carries the prop with the
// player every frame on the client, instead of the script chasing them a tick
// late. The catch is how SetParent treats the prop's current position - either
// it keeps the world position (normal) or re-reads it as a local offset (what
// the bumper cars saw with players). Rather than guess, the script tries one,
// checks where the prop actually ended up on the next tick, and switches to the
// other if it's wrong. Whichever works is remembered for the rest of the map.
let parentMethod = "local";   // "local" or "world" - first guess
let parentMethodConfirmed = false;

function attachByParent(ent, pawn, disguise, method) {
  ent.SetParent(undefined);
  if (method === "local") {
    // Handed over as world coords, re-read as local = exactly the offset we want.
    ent.Teleport({ position: localOffset(disguise), angles: { pitch: 0, yaw: 0, roll: 0 } });
  } else {
    ent.Teleport(worldPlacement(pawn, disguise, pawn.GetAbsAngles().yaw));
  }
  ent.SetParent(pawn);
}

/** Is the prop where it should be? Called the tick after parenting. */
function parentLooksRight(ent, pawn, disguise) {
  const want = worldPlacement(pawn, disguise, pawn.GetAbsAngles().yaw).position;
  const got = ent.GetAbsOrigin();
  return Math.hypot(got.x - want.x, got.y - want.y, got.z - want.z) < 16;
}

function applyDisguise(entry, pawn, disguise) {
  const ent = disguiseEntity(entry, disguise);
  if (!ent) return;

  if (!entry.disguised) {
    ent.SetColor(OPAQUE);
    entry.disguised = true;
    entry.disguiseParked = false;
    entry.parentState = undefined;
    log(`${nameOf(pawn)} is now a palm tree`);
  }

  const mode = entry.parentFailed ? "follow" : (disguise.mode || "parent");

  if (mode === "parent") {
    if (!entry.parentState) {
      attachByParent(ent, pawn, disguise, parentMethod);
      entry.parentState = { checking: true, triedOther: false };
      return;
    }
    if (!entry.parentState.checking) return;   // parented and verified - engine does the rest

    if (parentLooksRight(ent, pawn, disguise)) {
      entry.parentState.checking = false;
      if (!parentMethodConfirmed) log(`disguise parented (SetParent method: ${parentMethod})`);
      parentMethodConfirmed = true;
      return;
    }

    if (!entry.parentState.triedOther && !parentMethodConfirmed) {
      parentMethod = parentMethod === "local" ? "world" : "local";
      log(`disguise landed in the wrong place - retrying with SetParent method "${parentMethod}"`);
      attachByParent(ent, pawn, disguise, parentMethod);
      entry.parentState.triedOther = true;
      return;
    }

    // Neither worked. Fall back to chasing the player every tick.
    Instance.Msg(`[buffs] couldn't parent the disguise cleanly - falling back to follow mode`);
    ent.SetParent(undefined);
    entry.parentFailed = true;
  }

  // ---- follow mode (fallback) ----------------------------------------------
  // Teleported every tick to 180 degrees from the camera. Leads by one tick of
  // the player's velocity so it doesn't trail behind them when they run.
  const place = worldPlacement(pawn, disguise, pawn.GetEyeAngles().yaw);
  const v = pawn.GetAbsVelocity();
  const lead = 1 / 64;
  place.position.x += v.x * lead;
  place.position.y += v.y * lead;
  place.position.z += v.z * lead;
  ent.Teleport(place);
}

function clearDisguise(entry, disguise) {
  if (!disguise || !entry.disguised) return;
  entry.disguised = false;
  entry.parentState = undefined;

  const ent = entry.disguiseEnt;
  if (ent && ent.IsValid()) {
    ent.SetParent(undefined);
    if (entry.disguiseHome) ent.Teleport(entry.disguiseHome);
  }
  parkDisguise(entry, disguise);
}

function applyInvisible(entry, pawn, now, buff) {
  if (pawn.IsValid()) pawn.SetColor(PLAYER_CLEAR);
  startGlow(entry, pawn, buff.glow);
  if (!HIDE_WEAPONS) return;

  if (buff.hideHolstered === false) {
    // Only the weapon in their hands is hidden. Anything we hid earlier that is
    // no longer in hand (switched away, holstered, dropped) is made visible
    // again, so a holstered gun never stays invisible on their back. Compared by
    // class rather than entity handle, so a re-deploy can't make it flicker.
    const active = pawn.GetActiveWeapon();
    const activeClass = active && active.IsValid() ? active.GetClassName() : "";
    for (const [classname, weapon] of entry.hidden) {
      if (classname === activeClass) continue;
      show(weapon);
      entry.hidden.delete(classname);
    }
    hideOne(entry, active);
    return;
  }

  // The weapon in their hands is re-hidden every tick because deploying one
  // spawns a fresh visible entity; the rest is swept at 10Hz, which is far
  // faster than anything in a holster can visibly change.
  hideOne(entry, pawn.GetActiveWeapon());
  if (now < entry.sweepAt) return;
  entry.sweepAt = now + 0.1;

  for (const gearSlot of GEAR_SLOTS) hideOne(entry, pawn.FindWeaponBySlot(gearSlot));
  for (const classname of EXTRA_HIDE) hideOne(entry, pawn.FindWeapon(classname));
}

function clearInvisible(entry, pawn) {
  stopGlow(entry, pawn);
  show(pawn);
  for (const weapon of entry.hidden.values()) show(weapon);
  entry.hidden.clear();
}

function isMoving(pawn) {
  return pawn.IsInputPressed(CSInputs.FORWARD)
      || pawn.IsInputPressed(CSInputs.BACK)
      || pawn.IsInputPressed(CSInputs.LEFT)
      || pawn.IsInputPressed(CSInputs.RIGHT);
}

function applySpeed(pawn, mult, dt) {
  if (!isMoving(pawn)) return;
  if (GROUND_ONLY && !pawn.GetGroundEntity()) return;

  const v = pawn.GetAbsVelocity();
  const speed = Math.hypot(v.x, v.y);
  if (speed <= 1) return;

  // CS2 re-clamps horizontal ground velocity to the weapon's max speed every
  // tick, so extra velocity evaporates. Add distance instead, hull-traced so it
  // can never push anyone through geometry.
  const extra = (mult - 1) * speed * dt;
  const origin = pawn.GetAbsOrigin();
  const end = {
    x: origin.x + (v.x / speed) * extra,
    y: origin.y + (v.y / speed) * extra,
    z: origin.z,
  };

  const trace = Instance.TracePlayer({ start: origin, end, player: pawn });
  if (trace.startedInSolid) return;
  if (USE_TELEPORT) pawn.Teleport({ position: trace.end });
  else pawn.Move({ position: trace.end });
}

// ----- watching the map's weapon --------------------------------------------

/** Re-find the named weapon lying in the map. */
function acquire(targetname, entry) {
  const found = Instance.FindEntityByName(targetname);
  if (found && found.IsValid()) {
    entry.entity = found;
    log(`watching "${targetname}" (${found.GetClassName()})`);
    return true;
  }
  return false;
}

/**
 * After the holder loses it, adopt the weapon they dropped so it can be picked
 * up again. The dropped entity has no targetname, so it's found by being an
 * ownerless weapon of the right class near where the holder was.
 */
function rearm(targetname, entry, classname, near) {
  if (!REARM_ON_DROP || !near) return;

  let best;
  let bestDistance = REARM_RADIUS;
  for (const candidate of Instance.FindEntitiesByClass(classname)) {
    if (!candidate.IsValid() || candidate.GetOwner()) continue;
    const p = candidate.GetAbsOrigin();
    const distance = Math.hypot(p.x - near.x, p.y - near.y, p.z - near.z);
    if (distance < bestDistance) { bestDistance = distance; best = candidate; }
  }

  if (best) {
    entry.entity = best;
    log(`"${targetname}" re-armed from the dropped weapon`);
  }
}

function updateWatch(targetname, buff, entry) {
  if (entry.holder) return;

  // Still on the ground and untouched.
  if (entry.entity && entry.entity.IsValid()) {
    const owner = entry.entity.GetOwner();
    if (!owner) return;

    const slot = slotOf(owner);
    if (slot === undefined) return;
    entry.holder = { slot, pawn: owner };
    entry.entity = undefined;
    log(`"${targetname}" taken by ${nameOf(owner)}`);
    return;
  }

  // The entity is gone. Either it hasn't spawned yet, or somebody took it in the
  // same tick it was destroyed and we never saw an owner on it. If exactly one
  // player is carrying that class, it was unambiguously them.
  const hadEntity = entry.entity !== undefined;
  entry.entity = undefined;

  if (acquire(targetname, entry)) return;

  if (hadEntity) {
    const carrying = holdersOf(buff.classname);
    if (carrying.length === 1) {
      entry.holder = carrying[0];
      log(`"${targetname}" vanished; ${nameOf(carrying[0].pawn)} is the only ${buff.classname} holder`);
    } else if (carrying.length > 1) {
      Instance.Msg(`[buffs] "${targetname}" vanished but ${carrying.length} players hold` +
                   ` ${buff.classname} - can't tell who took it, buff not granted`);
    }
  }
}

// ----- main loop ------------------------------------------------------------

Instance.SetThink(() => {
  const now = Instance.GetGameTime();
  Instance.SetNextThink(now);
  const dt = lastThink > 0 ? Math.min(now - lastThink, 0.25) : 0;
  lastThink = now;

  for (const [targetname, buff] of Object.entries(BUFFS)) {
    const entry = entryFor(targetname);

    updateWatch(targetname, buff, entry);
    if (!entry.holder) { parkDisguise(entry, buff.disguise); continue; }

    const pawn = entry.holder.pawn;
    const gone = !pawn.IsValid() || !pawn.IsAlive()
              || (DROP_ENDS_BUFF && !stillCarrying(pawn, buff.classname));

    if (gone) {
      const where = pawn.IsValid() ? pawn.GetAbsOrigin() : undefined;
      if (buff.invisible) clearInvisible(entry, pawn);
      clearDisguise(entry, buff.disguise);
      log(`"${targetname}" released by ${nameOf(pawn)}`);
      entry.holder = undefined;
      rearm(targetname, entry, buff.classname, where);
      continue;
    }

    if (buff.invisible) applyInvisible(entry, pawn, now, buff);
    if (buff.disguise) applyDisguise(entry, pawn, buff.disguise);
    if (buff.speedMult && dt > 0) applySpeed(pawn, buff.speedMult, dt);
  }
});

function start() {
  lastThink = 0;
  for (const [targetname, buff] of Object.entries(BUFFS)) {
    const entry = entryFor(targetname);
    if (entry.holder && buff.invisible) clearInvisible(entry, entry.holder.pawn);
    entry.holder = undefined;
    // Round start recreates map entities, so drop the cached prop and re-find
    // it (and its placed position) fresh.
    if (entry.disguiseEnt && entry.disguiseEnt.IsValid()) entry.disguiseEnt.SetParent(undefined);
    entry.disguised = false;
    entry.disguiseParked = false;
    entry.parentState = undefined;
    entry.parentFailed = false;
    entry.disguiseEnt = undefined;
    entry.disguiseHome = undefined;
    entry.entity = undefined;
    if (!acquire(targetname, entry)) {
      // Entity spawn order isn't guaranteed; updateWatch retries every tick.
      log(`"${targetname}" not found yet - will keep looking`);
    }
  }
  Instance.SetNextThink(Instance.GetGameTime());
}

Instance.OnActivate(start);
Instance.OnScriptReload({ after: start });
Instance.OnRoundStart(start);   // map entities are recreated, so re-find them

// Console command (needs sv_cheats 1).
Instance.RegisterCheatCommand("buffs_dump", () => {
  for (const [targetname, buff] of Object.entries(BUFFS)) {
    const entry = entryFor(targetname);
    const where = entry.entity && entry.entity.IsValid() ? "on the ground" : "not found";
    const who = entry.holder
      ? `${nameOf(entry.holder.pawn)} (slot ${entry.holder.slot})`
      : `nobody - entity ${where}`;
    Instance.Msg(`[buffs] ${targetname} (${buff.classname}): ${who}`);
  }
  for (const [targetname, buff] of Object.entries(BUFFS)) {
    const carrying = holdersOf(buff.classname).map((h) => nameOf(h.pawn)).join(", ");
    Instance.Msg(`[buffs]   carrying ${buff.classname}: ${carrying || "nobody"}`);
  }
});
