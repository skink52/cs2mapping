// ---------------------------------------------------------------- buying (1.6 rules: buy zone, buy time, 1.6 prices)
// CS2's own buy menu is switched off in the map (info_map_parameters "Nobody can buy"); everything is bought here.

// null when the player may buy now, otherwise the 1.6 message ('' = say nothing)
function canBuyNow(rec) {
  if (!rec.alive || !rec.map) return '';
  if (!rec.inBuy) return '';
  if (isWarmup()) return null;
  if (round.frozen || round.freezeEnd === null) return null;
  if (now() - round.freezeEnd > CONFIG.BUY_TIME) return Math.round(CONFIG.BUY_TIME) + ' seconds have passed.\nYou can\'t buy anything now!';
  return null;
}

// CS2 weapon -> 1.6 id (by its weapon data name, then its class name)
function weaponId(w) {
  if (!w) return null;
  let n = '';
  try { n = w.GetData().GetName(); } catch (err) { /* ignore */ }
  if (BY_CLASS[n]) return BY_CLASS[n];
  try { n = w.GetClassName(); } catch (err) { n = ''; }
  return BY_CLASS[n] || null;
}

function inventory(rec, pawn) {
  const prim = pawn.FindWeaponBySlot(CSGearSlot.RIFLE), sec = pawn.FindWeaponBySlot(CSGearSlot.PISTOL);
  const pid = weaponId(prim), sid = weaponId(sec);
  const ammoOf = (w, id) => (w && id && WEAPONS[id].ammo ? { reserve: w.GetReserveAmmo(), max: AMMO[WEAPONS[id].ammo].max, type: WEAPONS[id].ammo, w } : null);
  const has = (cls) => !!pawn.FindWeapon(cls);
  return {
    team: rec.team, money: rec.money, primary: pid, secondary: sid,
    armor: pawn.GetArmor(), helmet: pawn.HasHelmet(), defuser: pawn.HasDefuser(),
    nades: { hegrenade: has('weapon_hegrenade') ? 1 : 0, flashbang: has('weapon_flashbang') ? Math.max(1, rec.flashes) : 0, smokegrenade: has('weapon_smokegrenade') ? 1 : 0 },
    primaryAmmo: ammoOf(prim, pid), secondaryAmmo: ammoOf(sec, sid), primW: prim, secW: sec,
  };
}

function spend(rec, amount) {
  const c = controllerOf(rec.slot);
  if (!c || amount === 0) return;
  c.AddMoneySpendableNow(-amount);
  rec.money -= amount;
  showDelta(rec, -amount);
}
function showDelta(rec, d) {
  const t = now();
  rec.delta = t < rec.deltaUntil ? rec.delta + d : d;
  rec.deltaUntil = t + 2.5;
  rec.moneyHot = t + 1;
}

// buy one item (1.6 id, or ammo_primary / ammo_secondary). Returns true when something was bought.
function buy(rec, item, quiet) {
  const pawn = pawnOf(rec.slot);
  if (!pawn || !rec.alive) return false;
  const why = canBuyNow(rec);
  if (why !== null) { if (why && !quiet) message(rec, why, 3); return false; }
  const inv = inventory(rec, pawn);
  // a gun bought a moment ago that CS2 hasn't handed over yet: its ammo is the pending number
  for (const f of rec.ammoFix) {
    if (f.slot === 'primary' || f.slot === 'secondary') {
      const id = BY_CLASS[f.cls];
      inv[f.slot] = id;
      inv[f.slot + 'Ammo'] = { reserve: Math.max(0, f.reserve), max: AMMO[WEAPONS[id].ammo].max, type: WEAPONS[id].ammo, fix: f };
    }
  }
  /** @type {any} */
  let plan = planPurchase(inv, item);
  if (!plan.ok) { if (!quiet) message(rec, plan.msg, 3); return false; }
  if (plan.ammo) {
    // ammo: one pack per buy in 1.6 (the , and . keys); one click here keeps buying packs until full (CONFIG.AMMO_FILL)
    const a = plan.ammo === 'primary' ? inv.primaryAmmo : inv.secondaryAmmo;
    let total = 0, rounds = a.reserve;
    do {
      total += plan.price; rounds = Math.min(a.max, rounds + plan.rounds);
      inv.money -= plan.price; a.reserve = rounds;
      plan = CONFIG.AMMO_FILL ? planPurchase(inv, item) : { ok: false };
    } while (plan.ok);
    if (a.fix) a.fix.reserve = rounds; else a.w.SetReserveAmmo(rounds);
    spend(rec, total);
    playTo(rec, 'ammo');
    rec.bought.push(item);
    return true;
  }
  if (plan.armor) {
    pawn.SetArmor(plan.armor);
    if (plan.helmet) pawn.SetHasHelmet(true);
    if (plan.msg) message(rec, plan.msg, 3);
    spend(rec, plan.price);
    playTo(rec, 'kevlar');
  } else if (plan.helmet) {
    pawn.SetHasHelmet(true);
    spend(rec, plan.price);
    playTo(rec, 'kevlar');
  } else if (plan.defuser) {
    pawn.SetHasDefuser(true);
    spend(rec, plan.price);
    playTo(rec, 'gunpickup');
  } else if (plan.give) {
    const w = WEAPONS[plan.give];
    if (plan.drop) {
      const old = plan.drop === 'primary' ? inv.primW : inv.secW;
      if (old) guard('drop', () => pawn.DropWeapon(old));
    }
    pawn.GiveNamedItem(w.cls, w.slot !== 'grenade');
    if (plan.give === 'flashbang') rec.flashes = inv.nades.flashbang + 1;
    // 1.6: a bought gun comes with one magazine and no spare ammo (buy ammo separately)
    if ((w.slot === 'primary' || w.slot === 'secondary') && !CONFIG.SPARE_AMMO_ON_BUY) {
      rec.ammoFix = rec.ammoFix.filter((f) => f.slot !== w.slot);
      const got = pawn.FindWeapon(w.cls);
      if (got && got !== inv.primW && got !== inv.secW) got.SetReserveAmmo(0);
      else rec.ammoFix.push({ cls: w.cls, slot: w.slot, reserve: 0, until: now() + 1 });
    }
    spend(rec, plan.price);
    playTo(rec, 'gunpickup');
  }
  rec.bought.push(item);
  return true;
}

// the ammo a gun should have after it was given (applied once the gun exists)
function fixAmmo(rec, pawn) {
  if (!rec.ammoFix.length) return;
  const t = now();
  rec.ammoFix = rec.ammoFix.filter((f) => {
    if (t > f.until) return false;
    const w = pawn.FindWeapon(f.cls);
    if (!w) return true;
    if (f.reserve >= 0) w.SetReserveAmmo(f.reserve);
    return false;
  });
}

// the previous round's purchases again (1.6 "rebuy")
function rebuy(rec) {
  const list = rec.lastBuys.slice();
  let any = false;
  for (const it of list) if (buy(rec, it, true)) any = true;
  if (!any) message(rec, 'Nothing to re-buy', 2);
}

// "!buy ak47", "!ak47", "!vesthelm": the 1.6 console buy names
function buyByName(rec, name) {
  const id = BUY_ALIASES[name] || (WEAPONS[name] ? name : null);
  if (!id) return false;
  buy(rec, id);
  return true;
}
