// ---------------------------------------------------------------- 1.6 rules as pure functions (no engine calls)

// 1.6 armour (CBasePlayer::TakeDamage): part of the damage goes to the vest. ratio = 0.5 x the weapon's armour
// multiplier (explosions: 0.5), bonus 0.5. When the vest runs out, bullets lose 2 x the armour left, explosions 1 x.
// Returns { health, armor } (health = damage taken by health, armor = armour left).
function armorAbsorb(damage, armor, ratioMul, armored, blast) {
  if (armor <= 0 || !armored) return { health: damage, armor };
  const ratio = ARMOR_RATIO * (blast ? 1 : ratioMul);
  const fNew = damage * ratio;
  let fArmor = (damage - fNew) * ARMOR_BONUS;
  if (fArmor > armor) return { health: damage - (blast ? armor : armor / ARMOR_BONUS), armor: 0 };
  if (fArmor < 0) fArmor = 1;
  return { health: fNew, armor: armor - fArmor };
}

// hit groups the vest covers (1.6 CBasePlayer::IsArmored): everything but the legs; the head only with a helmet
function isArmored(hitGroup, helmet) {
  if (hitGroup === 1) return helmet;                 // head
  return hitGroup !== 6 && hitGroup !== 7;           // left/right leg
}

// bullet damage for a 1.6 weapon at distance d (units), before armour
function bulletDamage16(w, silenced, dist, hitGroup) {
  const mult = HIT_MULT[hitGroup] ?? 1;
  // shotguns: each pellet does 20 x (1 - distance / range), whole numbers (CBaseEntity::FireBullets, buckshot)
  if (w.shotgun) return Math.floor(Math.max(0, 1 - dist / w.shotRange) * w.dmg) * mult;
  const base = silenced && w.dmgSil ? w.dmgSil : w.dmg;
  const range = silenced && w.rangeSil ? w.rangeSil : w.range;
  return base * Math.pow(range, dist / 500) * mult;
}

// 1.6 explosions: linear falloff, radius = 3.5 x damage (RadiusDamage). HE: damage 100.
function blastDamage16(damage, dist) {
  const radius = damage * 3.5;
  if (dist >= radius) return 0;
  return damage - dist * (damage / radius);
}

// 1.6 fall damage from the landing speed (CHalfLifeMultiplay::FlPlayerFallDamage)
function fallDamage16(speed) {
  if (speed <= FALL_SAFE_16) return 0;
  return (speed - FALL_SAFE_16) * (100 / (FALL_FATAL_16 - FALL_SAFE_16)) * 1.25;
}

// 1.6 knife: stab 65 (x3 from behind), slash 20, or 15 when chained straight after another slash
function knifeDamage16(stab, chained, backstab) {
  if (stab) return 65 * (backstab ? 3 : 1);
  return chained ? 15 : 20;
}

// ---------------------------------------------------------------- round money (multiplay_gamerules.cpp, bomb maps)
// result: { winner: TEAM_T | TEAM_CT | 0, reason: 'bombed' | 'defused' | 'saved' | 'elim' | 'draw' }
function teamRewards(result) {
  const r = { [TEAM_T]: 0, [TEAM_CT]: 0 };
  switch (result.reason) {
    case 'bombed': r[TEAM_T] += REWARD.TARGET_BOMBED; break;
    case 'defused': r[TEAM_CT] += REWARD.BOMB_DEFUSED; r[TEAM_T] += REWARD.BOMB_PLANTED; break;
    case 'saved': r[TEAM_CT] += REWARD.TARGET_SAVED; break;
    case 'elim': r[result.winner] += result.winner === TEAM_T ? REWARD.T_ELIM : REWARD.CT_ELIM; break;
  }
  return r;
}

// the losing streak bonus: one shared value per map, exactly as 1.6 keeps it per server
class LossBonus {
  constructor() { this.bonus = REWARD.LOSER_DEFAULT; this.tLoses = 0; this.ctLoses = 0; }
  // returns the bonus the losing team gets this round (0 for a draw)
  apply(winner) {
    if (winner === TEAM_T) {
      if (this.tLoses > 1) this.bonus = REWARD.LOSER_MIN;
      this.tLoses = 0; this.ctLoses++;
    } else if (winner === TEAM_CT) {
      if (this.ctLoses > 1) this.bonus = REWARD.LOSER_MIN;
      this.ctLoses = 0; this.tLoses++;
    } else return 0;
    if (this.tLoses > 1 && this.bonus < REWARD.LOSER_MAX) this.bonus += REWARD.LOSER_ADD;
    else if (this.ctLoses > 1 && this.bonus < REWARD.LOSER_MAX) this.bonus += REWARD.LOSER_ADD;
    return this.bonus;
  }
}

// ---------------------------------------------------------------- buying
// inv: { team, money, primary (1.6 id | null), secondary, armor, helmet, defuser, nades: {hegrenade, flashbang, smokegrenade},
//        primaryAmmo: {reserve, max, type} | null, secondaryAmmo: same }
// returns { ok, price, msg, give?: id, armor?, helmet?, defuser?, ammo?: 'primary'|'secondary', drop?: 'primary'|'secondary' }
function planPurchase(inv, item) {
  if (item === 'ammo_primary' || item === 'ammo_secondary') {
    const which = item === 'ammo_primary' ? 'primary' : 'secondary';
    const a = inv[which + 'Ammo'];
    if (!a) return { ok: false, msg: 'You have no weapon for that ammo' };
    const A = AMMO[a.type];
    if (!A || a.reserve >= a.max) return { ok: false, msg: 'You cannot carry any more ammo' };
    if (inv.money < A.price) return { ok: false, msg: 'You have insufficient funds!' };
    return { ok: true, price: A.price, ammo: which, rounds: Math.min(A.buy, a.max - a.reserve) };
  }
  if (item === 'kevlar') {
    if (inv.armor >= 100) return { ok: false, msg: 'You already have Kevlar!' };
    if (inv.money < EQUIP.kevlar.price) return { ok: false, msg: 'You have insufficient funds!' };
    return { ok: true, price: EQUIP.kevlar.price, armor: 100 };
  }
  if (item === 'vesthelm') {
    if (inv.armor >= 100 && inv.helmet) return { ok: false, msg: 'You already have Kevlar and a helmet!' };
    if (inv.armor >= 100) {
      if (inv.money < EQUIP.vesthelm.helmetOnly) return { ok: false, msg: 'You have insufficient funds!' };
      return { ok: true, price: EQUIP.vesthelm.helmetOnly, helmet: true, armor: 100, msg: 'You already have Kevlar. Helmet purchased.' };
    }
    if (inv.money < EQUIP.vesthelm.price) return { ok: false, msg: 'You have insufficient funds!' };
    return { ok: true, price: EQUIP.vesthelm.price, armor: 100, helmet: true };
  }
  if (item === 'defuser') {
    if (inv.team !== TEAM_CT) return { ok: false, msg: 'Only Counter-Terrorists can buy defusal kits' };
    if (inv.defuser) return { ok: false, msg: 'You already have a defusal kit!' };
    if (inv.money < EQUIP.defuser.price) return { ok: false, msg: 'You have insufficient funds!' };
    return { ok: true, price: EQUIP.defuser.price, defuser: true };
  }
  if (item === 'nvg') return { ok: false, msg: 'Night vision is not available here' };
  const w = WEAPONS[item];
  if (!w) return { ok: false, msg: 'Unknown item' };
  if (w.team && w.team !== inv.team) return { ok: false, msg: 'Your team cannot buy that' };
  if (inv.money < w.price) return { ok: false, msg: 'You have insufficient funds!' };
  if (w.slot === 'grenade') {
    const have = inv.nades[item] || 0;
    if (have >= w.max) return { ok: false, msg: 'You cannot carry any more' };
    return { ok: true, price: w.price, give: item };
  }
  if (w.slot === 'primary') {
    if (inv.primary === item) return { ok: false, msg: 'You already have one' };
    return { ok: true, price: w.price, give: item, drop: inv.primary ? 'primary' : undefined };
  }
  if (w.slot === 'secondary') {
    if (inv.secondary === item) return { ok: false, msg: 'You already have one' };
    return { ok: true, price: w.price, give: item, drop: inv.secondary ? 'secondary' : undefined };
  }
  return { ok: false, msg: 'Unknown item' };
}

// 1.6 console buy aliases (and a few extra spellings) -> item ids
const BUY_ALIASES = {
  glock: 'glock18', glock18: 'glock18', '9x19mm': 'glock18', usp: 'usp', km45: 'usp', p228: 'p228', '228compact': 'p228', deagle: 'deagle',
  nighthawk: 'deagle', elites: 'elite', elite: 'elite', fiveseven: 'fiveseven', fn57: 'fiveseven', m3: 'm3', '12gauge': 'm3', xm1014: 'xm1014',
  autoshotgun: 'xm1014', mac10: 'mac10', tmp: 'tmp', mp: 'tmp', mp5: 'mp5navy', mp5navy: 'mp5navy', smg: 'mp5navy', ump45: 'ump45', p90: 'p90',
  c90: 'p90', galil: 'galil', defender: 'galil', famas: 'famas', clarion: 'famas', ak47: 'ak47', cv47: 'ak47', ak: 'ak47', scout: 'scout',
  m4a1: 'm4a1', m4: 'm4a1', sg552: 'sg552', krieg552: 'sg552', aug: 'aug', bullpup: 'aug', sg550: 'sg550', krieg550: 'sg550', awp: 'awp',
  magnum: 'awp', g3sg1: 'g3sg1', d3au1: 'g3sg1', m249: 'm249', vest: 'kevlar', kevlar: 'kevlar', vesthelm: 'vesthelm', vesthelmet: 'vesthelm',
  flash: 'flashbang', flashbang: 'flashbang', hegren: 'hegrenade', he: 'hegrenade', hegrenade: 'hegrenade', sgren: 'smokegrenade',
  smoke: 'smokegrenade', defuser: 'defuser', kit: 'defuser', nvgs: 'nvg', primammo: 'ammo_primary', buyammo1: 'ammo_primary',
  secammo: 'ammo_secondary', buyammo2: 'ammo_secondary',
};
