// ---------------------------------------------------------------- 1.6 damage
// CS2 still decides what was hit (its hit boxes, bullet penetration, who may hurt whom); this hook replaces the amount
// with the 1.6 value: 1.6 weapon damage and range falloff, 1.6 hit-group multipliers, 1.6 armour (applied here, so the
// hit is passed on with IGNORE_ARMOR), 1.6 knife, HE grenade and C4 blasts, and 1.6 fall damage (applied on landing).

let ownDamage = false;                 // true while the script deals damage itself (fall damage)
const knifeSwings = new Map();         // attacker slot -> { type, at, prevAt }

function onKnifeAttack(ev) {
  const w = ev.weapon;
  const owner = w ? w.GetOwner() : undefined;
  const s = slotOf(owner);
  if (s === undefined) return;
  const k = knifeSwings.get(s) || { type: 0, at: -9, prevPrimary: -9 };
  if (ev.attackType === CSWeaponAttackType.PRIMARY) { k.prevPrimary = k.type === CSWeaponAttackType.PRIMARY ? k.at : k.prevPrimary; }
  k.type = ev.attackType; k.at = now();
  knifeSwings.set(s, k);
}

function isKnife(w) {
  if (!w) return false;
  try { return w.GetData().GetType() === CSWeaponType.KNIFE; } catch (err) { return false; }
}

// armour + the result returned to CS2
function finish(ev, pawn, dmg16, ratioMul, armored, blast) {
  const armor = pawn.GetArmor();
  const r = armorAbsorb(dmg16, armor, ratioMul, armored, blast);
  if (r.armor !== armor) {
    const a = Math.max(0, Math.round(r.armor));
    pawn.SetArmor(a);
    if (a <= 0 && pawn.HasHelmet()) pawn.SetHasHelmet(false);
  }
  const health = Math.max(0, Math.floor(r.health));
  if (CONFIG.DEBUG_DAMAGE) log(`damage: cs2 ${ev.damage.toFixed(1)} -> 1.6 ${dmg16.toFixed(1)} (health ${health}, armour ${armor} -> ${Math.round(r.armor)}) hitgroup ${ev.hitGroup}`);
  if (health <= 0) return { abort: true };
  return { damage: health, damageFlags: ev.damageFlags | CSDamageFlags.IGNORE_ARMOR };
}

function onModifyDamage(ev) {
  if (ownDamage || !CONFIG.DAMAGE_16) return undefined;
  const pawn = ev.player;
  if (!live(pawn)) return undefined;
  const types = ev.damageTypes;
  // falling: the script deals the 1.6 amount itself when the player lands (onLand)
  if (types & CSDamageTypes.FALL) return CONFIG.FALL_DAMAGE_16 ? { abort: true } : undefined;
  const hg = ev.hitGroup < 0 ? 0 : ev.hitGroup;
  const victimPos = pawn.GetAbsOrigin();
  // explosions: HE grenade (100 damage, 350 units) or the C4 (the map's bomb radius, 3.5 x that in units), linear falloff
  if (types & CSDamageTypes.BLAST) {
    const inf = live(ev.inflictor);
    if (!inf) return undefined;
    const cls = inf.GetClassName();
    const centre = { x: victimPos.x, y: victimPos.y, z: victimPos.z + 36 };
    const at = inf.GetAbsOrigin();
    let dmg;
    if (cls === 'planted_c4') {
      const key = mapAt(at);
      const rec = recs.get(slotOf(pawn));
      if (rec && key && rec.map && rec.map !== key) return { abort: true };     // a bomb on another map
      const m = MAP_BY_KEY[key] || MAPS[0];
      dmg = blastDamage16(m.bombradius, dist3(at, centre));
    } else if (cls === 'hegrenade_projectile') {
      dmg = blastDamage16(100, dist3(at, centre));
    } else return undefined;
    if (dmg <= 0) return { abort: true };
    return finish(ev, pawn, dmg, 1, true, true);
  }
  const w = live(ev.weapon);
  if (!w) return undefined;
  const att = live(ev.attacker);
  // knife: 1.6 slash 20 (15 straight after another slash), stab 65, x3 from behind (stab only); hit groups apply
  if (isKnife(w)) {
    const s = slotOf(att);
    const k = s !== undefined ? knifeSwings.get(s) : undefined;
    let stab;
    if (k && now() - k.at < 0.6) stab = k.type === CSWeaponAttackType.SECONDARY;
    else stab = ev.damage >= 55 && hg !== 1;     // (no swing seen: CS2's heavy hit is 65+)
    const chained = !stab && !!k && k.at - k.prevPrimary < 0.8;
    let back = false;
    if (stab && att) {
      // 1.6: from behind when the attacker looks the same way the victim faces (2D dot > 0.8)
      const a = att.GetEyeAngles().yaw * Math.PI / 180, v = pawn.GetAbsAngles().yaw * Math.PI / 180;
      back = Math.cos(a) * Math.cos(v) + Math.sin(a) * Math.sin(v) > 0.8;
    }
    let dmg = knifeDamage16(stab, chained, back) * (HIT_MULT[hg] ?? 1);
    if (CONFIG.CS2_REAPPLIES_HITGROUP) dmg /= (HIT_MULT[hg] ?? 1);
    return finish(ev, pawn, dmg, WEAPONS.knife.armor, isArmored(hg, pawn.HasHelmet()), false);
  }
  // bullets
  const id = weaponId(w);
  if (!id || !WEAPONS[id] || !WEAPONS[id].dmg) return undefined;
  const W = WEAPONS[id];
  let silenced = false;
  try { silenced = w.IsSilencerOn(); } catch (err) { /* ignore */ }
  const from = att ? att.GetEyePosition() : w.GetAbsOrigin();
  const to = { x: victimPos.x, y: victimPos.y, z: victimPos.z + (hg === 1 ? 64 : hg >= 6 && hg <= 7 ? 20 : 44) };
  const d = dist3(from, to);
  // what CS2 would have done without walls in the way: the difference is penetration (or CS2's team-damage cut),
  // which carries over to the 1.6 number
  let pen = 1;
  try {
    const data = w.GetData();
    const expect = data.GetDamage() * Math.pow(data.GetRangeModifier(), d / 500) * (HIT_MULT[hg] ?? 1);
    if (expect > 0) pen = clamp(ev.damage / expect, 0, 1);
    if (pen > 0.9) pen = 1;
  } catch (err) { /* ignore */ }
  let dmg = bulletDamage16(W, silenced, d, hg) * pen;
  if (CONFIG.CS2_REAPPLIES_HITGROUP) dmg /= (HIT_MULT[hg] ?? 1);
  return finish(ev, pawn, dmg, W.armor, isArmored(hg, pawn.HasHelmet()), false);
}

// 1.6 fall damage: from the falling speed just before landing (tracked every tick in the main loop)
function onLand(pawn) {
  if (!CONFIG.DAMAGE_16 || !CONFIG.FALL_DAMAGE_16) return;
  const rec = recs.get(slotOf(pawn));
  if (!rec || !rec.alive) return;
  const speed = -rec.vz;
  rec.vz = 0;
  const dmg = fallDamage16(speed);
  if (dmg < 1) return;
  ownDamage = true;
  try {
    pawn.TakeDamage({ damage: dmg, damageTypes: CSDamageTypes.FALL, damageFlags: CSDamageFlags.IGNORE_ARMOR });
  } finally { ownDamage = false; }
}
