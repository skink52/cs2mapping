// ===================================================================================
// Part 4: players - movement, view, weapons and their action functions (p_user / p_pspr)
// ===================================================================================

function newPlayer(slot, name) {
  return {
    slot, name, team: -1, color: 0,
    mo: null, playerstate: 'reborn', spectating: false,
    cmd: { forwardmove: 0, sidemove: 0, angle: 0, buttons: 0 },
    pitch: 0, viewz: 0, viewheight: VIEWHEIGHT, deltaviewheight: 0, bob: 0,
    health: 100, armorpoints: 0, armortype: 0,
    powers: [0, 0, 0, 0, 0, 0], backpack: false,
    frags: 0, deaths: 0, killcount: 0,
    readyweapon: WP_PISTOL, pendingweapon: WP_NOCHANGE,
    weaponowned: new Array(NUMWEAPONS).fill(false),
    ammo: [0, 0, 0, 0], maxammo: MAXAMMO.slice(),
    attackdown: false, usedown: false, refire: 0,
    damagecount: 0, bonuscount: 0, attacker: null,
    psprites: [{ state: S_NULL, tics: 0, sx: 0, sy: 0 }, { state: S_NULL, tics: 0, sx: 0, sy: 0 }],
    deathTime: 0, spawnTime: 0, protectUntil: 0,
    message: '', messageTime: 0,
    stats: { damage: 0, pickups: 0 },
    switchLatch: 0,
    // set later by the arena, the HUD or the CS2 side; declared here so every player object has one shape (fast reads)
    arena: undefined, person: undefined, isBot: undefined, lives: undefined, frozen: undefined, pviewz: undefined,
    face: undefined, faceIdx: undefined, faceTic: undefined, extralight: undefined,
    respawnGate: undefined, respawnNow: undefined, bot: undefined, wantWeapon: undefined,
  };
}

function playerReborn(p) {
  p.health = 100; p.armorpoints = 0; p.armortype = 0;
  p.powers = [0, 0, 0, 0, 0, 0]; p.backpack = false;
  p.weaponowned.fill(false);
  p.weaponowned[WP_FIST] = true; p.weaponowned[WP_PISTOL] = true;
  p.readyweapon = WP_PISTOL; p.pendingweapon = WP_PISTOL;
  p.ammo = [50, 0, 0, 0]; p.maxammo = MAXAMMO.slice();
  p.attackdown = true; p.usedown = true; p.refire = 0;
  p.damagecount = 0; p.bonuscount = 0; p.attacker = null;
  p.viewheight = VIEWHEIGHT; p.deltaviewheight = 0;
  p.playerstate = 'live';
}

// round modifier: everyone (re)spawns with this weapon as well as the fist and pistol
const LOADOUTS = {
  shotgun: { name: 'PUMP-ACTION SHOTGUN START', weapon: WP_SHOTGUN, ammo: [50, 30, 0, 0] },
  ssg: { name: 'DOUBLE-BARRELLED SHOTGUN START', weapon: WP_SUPERSHOTGUN, ammo: [50, 30, 0, 0] },
  chaingun: { name: 'MINIGUN START', weapon: WP_CHAINGUN, ammo: [200, 0, 0, 0] },
  rocket: { name: 'MISSILE LAUNCHER START', weapon: WP_MISSILE, ammo: [50, 0, 0, 25] },
  plasma: { name: 'POLARIC ENERGY WEAPON START', weapon: WP_PLASMA, ammo: [50, 0, 200, 0] },
  chainsaw: { name: 'RIPSAW START', weapon: WP_CHAINSAW, ammo: [50, 0, 0, 0] },
  bfg: { name: 'SKAG 1337 START', weapon: WP_BFG, ammo: [50, 0, 200, 0] },
};

function applyLoadout(p, key) {
  const L = LOADOUTS[key];
  if (!L) return;
  p.weaponowned[L.weapon] = true;
  for (let i = 0; i < 4; i++) p.ammo[i] = Math.max(p.ammo[i], Math.min(L.ammo[i], p.maxammo[i]));
  p.readyweapon = L.weapon; p.pendingweapon = L.weapon;
}

function spawnPlayerAt(p, x, y, angle) {
  if (p.mo && !p.mo.removed) { p.mo.player = null; }
  const mo = spawnMobj(x, y, ONFLOORZ, MT.PLAYER);
  mo.angle = angle; mo.pangle = angle;
  mo.player = p; mo.health = p.health;
  p.mo = mo;
  p.psprites[0].state = S_NULL; p.psprites[1].state = S_NULL;
  p.viewz = mo.z + VIEWHEIGHT;
  p.spawnTime = G.leveltime;
  setupPsprites(p);
}

// ---------------------------------------------------------------- think
function thrust(p, angle, move) {
  p.mo.momx += move * Math.cos(angle * DEG);
  p.mo.momy += move * Math.sin(angle * DEG);
}

function calcHeight(p) {
  const mo = p.mo;
  p.bob = mo.momx * mo.momx + mo.momy * mo.momy;
  p.bob /= 4;
  if (p.bob > MAXBOB) p.bob = MAXBOB;
  const onground = mo.z <= mo.floorz;
  if (!onground) {
    p.viewz = mo.z + VIEWHEIGHT;
    if (p.viewz > mo.ceilingz - 4) p.viewz = mo.ceilingz - 4;
    p.viewz = mo.z + p.viewheight;
    return;
  }
  const angle = ((8192 / 20) * G.leveltime) % 8192;
  const bob = (p.bob / 2) * Math.sin(angle / 8192 * 2 * Math.PI);
  if (p.playerstate === 'live') {
    p.viewheight += p.deltaviewheight;
    if (p.viewheight > VIEWHEIGHT) { p.viewheight = VIEWHEIGHT; p.deltaviewheight = 0; }
    if (p.viewheight < VIEWHEIGHT / 2) {
      p.viewheight = VIEWHEIGHT / 2;
      if (p.deltaviewheight <= 0) p.deltaviewheight = 1;
    }
    if (p.deltaviewheight) {
      p.deltaviewheight += 0.25;
      if (!p.deltaviewheight) p.deltaviewheight = 1;
    }
  }
  p.viewz = mo.z + p.viewheight + (G.cfg.viewBob ? bob : 0);
  if (p.viewz > mo.ceilingz - 4) p.viewz = mo.ceilingz - 4;
}

function movePlayer(p) {
  const cmd = p.cmd, mo = p.mo;
  mo.angle = cmd.angle;
  const onground = mo.z <= mo.floorz;
  if (cmd.forwardmove && onground) thrust(p, mo.angle, cmd.forwardmove * 2048 / 65536);
  if (cmd.sidemove && onground) thrust(p, mo.angle - 90, cmd.sidemove * 2048 / 65536);
  if ((cmd.forwardmove || cmd.sidemove) && mo.state === SN('PLAY')) setMobjState(mo, SN('PLAY_RUN1'));
}

function deathThink(p) {
  movePsprites(p);
  if (p.viewheight > 6) p.viewheight -= 1;
  if (p.viewheight < 6) p.viewheight = 6;
  p.deltaviewheight = 0;
  calcHeight(p);
  const mo = p.mo;
  if (p.attacker && p.attacker !== mo && !p.attacker.removed) {
    const ang = pointToAngle(mo.x, mo.y, p.attacker.x, p.attacker.y);
    const d = angleDiff(mo.angle, ang);
    if (Math.abs(d) < 5) { mo.angle = ang; if (p.damagecount) p.damagecount--; }
    else mo.angle = normAngle(mo.angle + (d > 0 ? 5 : -5));
  } else if (p.damagecount) p.damagecount--;
}

const BT_ATTACK = 1, BT_USE = 2;

function playerThink(p) {
  const mo = p.mo;
  if (!mo || mo.removed) return;
  if (p.spectating) return;
  if (p.playerstate === 'dead') { deathThink(p); return; }
  const cmd = p.cmd;
  if (mo.reactiontime) mo.reactiontime--;
  else movePlayer(p);
  calcHeight(p);
  if (mo.sector.special) playerInSpecialSector(p);
  // weapon change requests from the input layer
  if (p.wantWeapon !== undefined && p.wantWeapon !== null) {
    const w = p.wantWeapon; p.wantWeapon = null;
    if (w !== p.readyweapon && p.weaponowned[w]) p.pendingweapon = w;
  }
  if (cmd.buttons & BT_USE) {
    if (!p.usedown) { useLines(p); p.usedown = true; }
  } else p.usedown = false;
  movePsprites(p);
  if (p.powers[PW_STRENGTH]) p.powers[PW_STRENGTH]++;
  if (p.powers[PW_INVULN]) p.powers[PW_INVULN]--;
  if (p.powers[PW_INVIS]) if (!--p.powers[PW_INVIS]) mo.flags &= ~MF_SHADOW;
  if (p.powers[PW_IRONFEET]) p.powers[PW_IRONFEET]--;
  if (p.damagecount) p.damagecount--;
  if (p.bonuscount) p.bonuscount--;
}

function cycleWeapon(p, dir) {
  // Doom slot order with the chainsaw/fist and SSG/shotgun pairs
  const order = [WP_FIST, WP_CHAINSAW, WP_PISTOL, WP_SHOTGUN, WP_SUPERSHOTGUN, WP_CHAINGUN, WP_MISSILE, WP_PLASMA, WP_BFG];
  let cur = p.pendingweapon !== WP_NOCHANGE ? p.pendingweapon : p.readyweapon;
  let i = order.indexOf(cur);
  for (let k = 0; k < order.length; k++) {
    i = (i + dir + order.length) % order.length;
    const w = order[i];
    if (!p.weaponowned[w]) continue;
    const am = WEAPONINFO[w].ammo;
    if (am !== AM_NOAMMO && p.ammo[am] < (w === WP_BFG ? 40 : w === WP_SUPERSHOTGUN ? 2 : 1)) continue;
    if (w !== p.readyweapon) p.pendingweapon = w;
    else p.pendingweapon = WP_NOCHANGE;
    return;
  }
}

function selectSlot(p, slot) {
  // Doom: 1 toggles fist/chainsaw, 3 toggles shotgun/super shotgun
  let w = [null, WP_FIST, WP_PISTOL, WP_SHOTGUN, WP_CHAINGUN, WP_MISSILE, WP_PLASMA, WP_BFG][slot];
  if (w === null || w === undefined) return;
  if (w === WP_FIST && p.weaponowned[WP_CHAINSAW] && !(p.readyweapon === WP_CHAINSAW && p.powers[PW_STRENGTH])) w = WP_CHAINSAW;
  if (w === WP_SHOTGUN && p.weaponowned[WP_SUPERSHOTGUN] && p.readyweapon !== WP_SUPERSHOTGUN) w = WP_SUPERSHOTGUN;
  if (p.weaponowned[w] && w !== p.readyweapon) p.pendingweapon = w;
}

// ---------------------------------------------------------------- psprites
function setPsprite(p, position, stnum) {
  const psp = p.psprites[position];
  let guard = 0;
  do {
    if (stnum === S_NULL) { psp.state = S_NULL; break; }
    const st = STATES[stnum];
    psp.state = stnum; psp.tics = st.tics;
    if (st.action) {
      const fn = WEAPON_ACTIONS[st.action];
      if (fn) fn(p, psp);
      if (psp.state === S_NULL) break;
    }
    stnum = STATES[psp.state].next;
  } while (!psp.tics && ++guard < 100);
}

function bringUpWeapon(p) {
  if (p.pendingweapon === WP_NOCHANGE) p.pendingweapon = p.readyweapon;
  if (p.pendingweapon === WP_CHAINSAW) startSound(p.mo, 'sawup');
  const newstate = WEAPONINFO[p.pendingweapon].up;
  p.pendingweapon = WP_NOCHANGE;
  p.psprites[0].sy = WEAPONBOTTOM;
  setPsprite(p, 0, newstate);
}

function checkAmmo(p) {
  const ammo = WEAPONINFO[p.readyweapon].ammo;
  let count = 1;
  if (p.readyweapon === WP_BFG) count = 40;
  else if (p.readyweapon === WP_SUPERSHOTGUN) count = 2;
  if (ammo === AM_NOAMMO || p.ammo[ammo] >= count) return true;
  do {
    if (p.weaponowned[WP_PLASMA] && p.ammo[AM_CELL]) p.pendingweapon = WP_PLASMA;
    else if (p.weaponowned[WP_SUPERSHOTGUN] && p.ammo[AM_SHELL] > 2) p.pendingweapon = WP_SUPERSHOTGUN;
    else if (p.weaponowned[WP_CHAINGUN] && p.ammo[AM_CLIP]) p.pendingweapon = WP_CHAINGUN;
    else if (p.weaponowned[WP_SHOTGUN] && p.ammo[AM_SHELL]) p.pendingweapon = WP_SHOTGUN;
    else if (p.ammo[AM_CLIP]) p.pendingweapon = WP_PISTOL;
    else if (p.weaponowned[WP_CHAINSAW]) p.pendingweapon = WP_CHAINSAW;
    else if (p.weaponowned[WP_MISSILE] && p.ammo[AM_MISL]) p.pendingweapon = WP_MISSILE;
    else if (p.weaponowned[WP_BFG] && p.ammo[AM_CELL] > 40) p.pendingweapon = WP_BFG;
    else p.pendingweapon = WP_FIST;
  } while (p.pendingweapon === WP_NOCHANGE);
  setPsprite(p, 0, WEAPONINFO[p.readyweapon].down);
  return false;
}

function fireWeapon(p) {
  if (!checkAmmo(p)) return;
  setMobjState(p.mo, SN('PLAY_ATK1'));
  noiseAlert(p.mo, p.mo);
  setPsprite(p, 0, WEAPONINFO[p.readyweapon].atk);
}

function setupPsprites(p) {
  for (const psp of p.psprites) psp.state = S_NULL;
  p.pendingweapon = p.readyweapon;
  bringUpWeapon(p);
}

function movePsprites(p) {
  for (let i = 0; i < 2; i++) {
    const psp = p.psprites[i];
    if (psp.state !== S_NULL && psp.tics !== -1) {
      psp.tics--;
      if (!psp.tics) setPsprite(p, i, STATES[psp.state].next);
    }
  }
  p.psprites[1].sx = p.psprites[0].sx;
  p.psprites[1].sy = p.psprites[0].sy;
}

function bulletSlope(mo) {
  let an = mo.angle;
  let slope = aimLineAttack(mo, an, 16 * 64);
  if (!AIM.linetarget) {
    an = normAngle(an + AIMSPREAD); slope = aimLineAttack(mo, an, 16 * 64);
    if (!AIM.linetarget) { an = normAngle(an - 2 * AIMSPREAD); slope = aimLineAttack(mo, an, 16 * 64); }
    if (!AIM.linetarget) slope = freeAimSlope(mo);
  }
  return slope;
}

function gunShot(mo, accurate, slope) {
  const damage = 5 * (P_Random() % 3 + 1);
  let angle = mo.angle;
  if (!accurate) angle += (P_Random() - P_Random()) * (360 / 16384);
  lineAttack(mo, angle, MISSILERANGE, slope, damage);
}

function flashState(p, offset) {
  setPsprite(p, 1, WEAPONINFO[p.readyweapon].flash + (offset || 0));
}

const WEAPON_ACTIONS = {
  A_WeaponReady(p, psp) {
    const mo = p.mo;
    if (mo.state === SN('PLAY_ATK1') || mo.state === SN('PLAY_ATK2')) setMobjState(mo, SN('PLAY'));
    if (p.readyweapon === WP_CHAINSAW && psp.state === SN('SAW')) startSound(mo, 'sawidl');
    if (p.pendingweapon !== WP_NOCHANGE || !p.health) {
      setPsprite(p, 0, WEAPONINFO[p.readyweapon].down);
      return;
    }
    if (p.cmd.buttons & BT_ATTACK) {
      if (!p.attackdown || (p.readyweapon !== WP_MISSILE && p.readyweapon !== WP_BFG)) {
        p.attackdown = true;
        fireWeapon(p);
        return;
      }
    } else p.attackdown = false;
    const angle = ((128 * G.leveltime) % 8192) / 8192 * 2 * Math.PI;
    psp.sx = 1 + p.bob * Math.cos(angle);
    psp.sy = WEAPONTOP + p.bob * Math.abs(Math.sin(angle));
  },
  A_ReFire(p) {
    if ((p.cmd.buttons & BT_ATTACK) && p.pendingweapon === WP_NOCHANGE && p.health) {
      p.refire++; fireWeapon(p);
    } else { p.refire = 0; checkAmmo(p); }
  },
  A_CheckReload(p) { checkAmmo(p); },
  A_Lower(p, psp) {
    psp.sy += LOWERSPEED;
    if (psp.sy < WEAPONBOTTOM) return;
    if (p.playerstate === 'dead') { psp.sy = WEAPONBOTTOM; return; }
    if (!p.health) { setPsprite(p, 0, S_NULL); return; }
    if (p.pendingweapon === WP_NOCHANGE || WEAPONINFO[p.pendingweapon] === undefined) p.pendingweapon = p.readyweapon;
    p.readyweapon = p.pendingweapon;
    bringUpWeapon(p);
  },
  A_Raise(p, psp) {
    psp.sy -= RAISESPEED;
    if (psp.sy > WEAPONTOP) return;
    psp.sy = WEAPONTOP;
    setPsprite(p, 0, WEAPONINFO[p.readyweapon].ready);
  },
  A_GunFlash(p) {
    setMobjState(p.mo, SN('PLAY_ATK2'));
    flashState(p, 0);
  },
  A_Punch(p) {
    const mo = p.mo;
    let damage = (P_Random() % 10 + 1) << 1;
    if (p.powers[PW_STRENGTH]) damage *= 10;
    const angle = mo.angle + (P_Random() - P_Random()) * (360 / 16384);
    const slope = aimLineAttack(mo, angle, MELEERANGE);
    lineAttack(mo, angle, MELEERANGE, slope, damage);
    if (AIM.linetarget) {
      startSound(mo, 'punch');
    }
  },
  A_Saw(p) {
    const mo = p.mo;
    const damage = 2 * (P_Random() % 10 + 1);
    const angle = mo.angle + (P_Random() - P_Random()) * (360 / 16384);
    const slope = aimLineAttack(mo, angle, MELEERANGE + 1);
    lineAttack(mo, angle, MELEERANGE + 1, slope, damage);
    if (!AIM.linetarget) { startSound(mo, 'sawful'); return; }
    startSound(mo, 'sawhit');
  },
  A_FirePistol(p) {
    startSound(p.mo, 'pistol');
    setMobjState(p.mo, SN('PLAY_ATK2'));
    p.ammo[AM_CLIP]--;
    flashState(p, 0);
    gunShot(p.mo, !p.refire, bulletSlope(p.mo));
  },
  A_FireShotgun(p) {
    startSound(p.mo, 'shotgn');
    setMobjState(p.mo, SN('PLAY_ATK2'));
    p.ammo[AM_SHELL]--;
    flashState(p, 0);
    const slope = bulletSlope(p.mo);
    for (let i = 0; i < 7; i++) gunShot(p.mo, false, slope);
  },
  A_FireShotgun2(p) {
    startSound(p.mo, 'dshtgn');
    setMobjState(p.mo, SN('PLAY_ATK2'));
    p.ammo[AM_SHELL] -= 2;
    flashState(p, 0);
    const slope = bulletSlope(p.mo);
    for (let i = 0; i < 20; i++) {
      const damage = 5 * (P_Random() % 3 + 1);
      const angle = p.mo.angle + (P_Random() - P_Random()) * (360 / 8192);
      lineAttack(p.mo, angle, MISSILERANGE, slope + (P_Random() - P_Random()) * 32 / 65536, damage);
    }
  },
  A_FireCGun(p, psp) {
    startSound(p.mo, 'pistol');
    if (!p.ammo[AM_CLIP]) return;
    setMobjState(p.mo, SN('PLAY_ATK2'));
    p.ammo[AM_CLIP]--;
    flashState(p, psp.state - SN('CHAIN1'));
    gunShot(p.mo, !p.refire, bulletSlope(p.mo));
  },
  A_FireMissile(p) { p.ammo[AM_MISL]--; spawnPlayerMissile(p.mo, MT.ROCKET); },
  A_FirePlasma(p) {
    p.ammo[AM_CELL]--;
    flashState(p, P_Random() & 1);
    spawnPlayerMissile(p.mo, MT.PLASMA);
  },
  A_FireBFG(p) { p.ammo[AM_CELL] -= 40; spawnPlayerMissile(p.mo, MT.BFG); },
  A_BFGsound(p) { startSound(p.mo, 'bfg'); },
  A_OpenShotgun2(p) { startSound(p.mo, 'dbopn'); },
  A_LoadShotgun2(p) { startSound(p.mo, 'dbload'); },
  A_CloseShotgun2(p) { startSound(p.mo, 'dbcls'); WEAPON_ACTIONS.A_ReFire(p); },
  A_Light0(p) { p.extralight = 0; },
  A_Light1(p) { p.extralight = 1; },
  A_Light2(p) { p.extralight = 2; },
};
