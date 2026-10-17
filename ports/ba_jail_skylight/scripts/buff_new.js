// buff_new.js  --  ba_jail_skylight
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
//   1. Put this file in  content/csgo_addons/ba_jail_skylight/scripts/
//   2. Add a point_script entity with "cs_script" = scripts/buff_new.vjs
//   3. Name the map's weapons in Hammer to match the keys in BUFFS below.

import { Instance, CSInputs, CSGearSlot } from "cs_script/point_script";

// ----- config ---------------------------------------------------------------
// Keyed by the weapon's targetname in Hammer.
const BUFFS = {
  invisscout: { classname: "weapon_ssg08", invisible: true },
  speedmp5:   { classname: "weapon_mp5sd", speedMult: 2.5 },
};

const DEBUG        = true;   // set false once it's working
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

function applyInvisible(entry, pawn, now) {
  hide(pawn);
  if (!HIDE_WEAPONS) return;

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
    if (!entry.holder) continue;

    const pawn = entry.holder.pawn;
    const gone = !pawn.IsValid() || !pawn.IsAlive()
              || (DROP_ENDS_BUFF && !stillCarrying(pawn, buff.classname));

    if (gone) {
      const where = pawn.IsValid() ? pawn.GetAbsOrigin() : undefined;
      if (buff.invisible) clearInvisible(entry, pawn);
      log(`"${targetname}" released by ${nameOf(pawn)}`);
      entry.holder = undefined;
      rearm(targetname, entry, buff.classname, where);
      continue;
    }

    if (buff.invisible) applyInvisible(entry, pawn, now);
    if (buff.speedMult && dt > 0) applySpeed(pawn, buff.speedMult, dt);
  }
});

function start() {
  lastThink = 0;
  for (const [targetname, buff] of Object.entries(BUFFS)) {
    const entry = entryFor(targetname);
    if (entry.holder && buff.invisible) clearInvisible(entry, entry.holder.pawn);
    entry.holder = undefined;
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
