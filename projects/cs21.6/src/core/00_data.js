// CS 1.6 game data. Numbers are the 1.6 values (as reimplemented by ReGameDLL_CS, which matches the original game).
// Each 1.6 weapon is played with the closest CS2 weapon class; damage, armour, prices and ammo follow 1.6.

const TEAM_T = 2, TEAM_CT = 3;

// slot: primary | secondary | knife | grenade.  team: 0 both, 2 T only, 3 CT only.
// dmg/dmgSil: damage per bullet; range: 1.6 range modifier; armor: 1.6 armour-ratio multiplier (x0.5 = health share)
const WEAPONS = {
  glock18:   { name: '9X19mm Sidearm', cls: 'weapon_glock', slot: 'secondary', cat: 'pistol', team: 0, price: 400, dmg: 25, range: 0.75, armor: 1.05, clip: 20, ammo: '9mm', speed: 250, spawnMags: 2 },
  usp:       { name: 'K&M .45 Tactical', cls: 'weapon_usp_silencer', slot: 'secondary', cat: 'pistol', team: 0, price: 500, dmg: 34, dmgSil: 30, range: 0.79, armor: 1, clip: 12, ammo: '45acp', speed: 250, spawnMags: 2 },
  p228:      { name: '228 Compact', cls: 'weapon_p250', slot: 'secondary', cat: 'pistol', team: 0, price: 600, dmg: 32, range: 0.8, armor: 1.25, clip: 13, ammo: '357sig', speed: 250 },
  deagle:    { name: 'Night Hawk .50C', cls: 'weapon_deagle', slot: 'secondary', cat: 'pistol', team: 0, price: 650, dmg: 54, range: 0.81, armor: 1.5, clip: 7, ammo: '50ae', speed: 250 },
  elite:     { name: '.40 Dual Elites', cls: 'weapon_elite', slot: 'secondary', cat: 'pistol', team: TEAM_T, price: 800, dmg: 36, range: 0.75, armor: 1.05, clip: 30, ammo: '9mm', speed: 250 },
  fiveseven: { name: 'ES Five-Seven', cls: 'weapon_fiveseven', slot: 'secondary', cat: 'pistol', team: TEAM_CT, price: 750, dmg: 20, range: 0.885, armor: 1.5, clip: 20, ammo: '57mm', speed: 250 },
  m3:        { name: 'Leone 12 Gauge Super', cls: 'weapon_nova', slot: 'primary', cat: 'shotgun', team: 0, price: 1700, dmg: 20, range: 1, armor: 1, clip: 8, ammo: 'buckshot', speed: 230, shotgun: true, shotRange: 3000 },
  xm1014:    { name: 'Leone YG1265 Auto Shotgun', cls: 'weapon_xm1014', slot: 'primary', cat: 'shotgun', team: 0, price: 3000, dmg: 20, range: 1, armor: 1, clip: 7, ammo: 'buckshot', speed: 240, shotgun: true, shotRange: 3048 },
  mac10:     { name: 'Ingram MAC-10', cls: 'weapon_mac10', slot: 'primary', cat: 'smg', team: TEAM_T, price: 1400, dmg: 29, range: 0.82, armor: 0.95, clip: 30, ammo: '45acp', speed: 250 },
  tmp:       { name: 'Schmidt Machine Pistol', cls: 'weapon_mp9', slot: 'primary', cat: 'smg', team: TEAM_CT, price: 1250, dmg: 20, range: 0.85, armor: 1, clip: 30, ammo: '9mm', speed: 250 },
  mp5navy:   { name: 'K&M Sub-Machine Gun', cls: 'weapon_mp5sd', slot: 'primary', cat: 'smg', team: 0, price: 1500, dmg: 26, range: 0.84, armor: 1, clip: 30, ammo: '9mm', speed: 250 },
  ump45:     { name: 'K&M UMP45', cls: 'weapon_ump45', slot: 'primary', cat: 'smg', team: 0, price: 1700, dmg: 30, range: 0.82, armor: 1, clip: 25, ammo: '45acp', speed: 250 },
  p90:       { name: 'ES C90', cls: 'weapon_p90', slot: 'primary', cat: 'smg', team: 0, price: 2350, dmg: 21, range: 0.885, armor: 1.5, clip: 50, ammo: '57mm', speed: 245 },
  galil:     { name: 'IDF Defender', cls: 'weapon_galilar', slot: 'primary', cat: 'rifle', team: TEAM_T, price: 2000, dmg: 30, range: 0.98, armor: 1.55, clip: 35, ammo: '556nato', speed: 240 },
  famas:     { name: 'Clarion 5.56', cls: 'weapon_famas', slot: 'primary', cat: 'rifle', team: TEAM_CT, price: 2250, dmg: 30, range: 0.96, armor: 1.4, clip: 25, ammo: '556nato', speed: 240 },
  ak47:      { name: 'CV-47', cls: 'weapon_ak47', slot: 'primary', cat: 'rifle', team: TEAM_T, price: 2500, dmg: 36, range: 0.98, armor: 1.55, clip: 30, ammo: '762nato', speed: 221 },
  m4a1:      { name: 'Maverick M4A1 Carbine', cls: 'weapon_m4a1_silencer', slot: 'primary', cat: 'rifle', team: TEAM_CT, price: 3100, dmg: 32, dmgSil: 33, range: 0.97, rangeSil: 0.95, armor: 1.4, clip: 30, ammo: '556nato', speed: 230 },
  sg552:     { name: 'Krieg 552', cls: 'weapon_sg556', slot: 'primary', cat: 'rifle', team: TEAM_T, price: 3500, dmg: 33, range: 0.955, armor: 1.4, clip: 30, ammo: '556nato', speed: 235 },
  aug:       { name: 'Bullpup', cls: 'weapon_aug', slot: 'primary', cat: 'rifle', team: TEAM_CT, price: 3500, dmg: 32, range: 0.96, armor: 1.4, clip: 30, ammo: '556nato', speed: 240 },
  scout:     { name: 'Schmidt Scout', cls: 'weapon_ssg08', slot: 'primary', cat: 'rifle', team: 0, price: 2750, dmg: 75, range: 0.98, armor: 1.7, clip: 10, ammo: '762nato', speed: 260 },
  awp:       { name: 'Magnum Sniper Rifle', cls: 'weapon_awp', slot: 'primary', cat: 'rifle', team: 0, price: 4750, dmg: 115, range: 0.99, armor: 1.95, clip: 10, ammo: '338magnum', speed: 210 },
  g3sg1:     { name: 'D3/AU-1', cls: 'weapon_g3sg1', slot: 'primary', cat: 'rifle', team: TEAM_T, price: 5000, dmg: 80, range: 0.98, armor: 1.65, clip: 20, ammo: '762nato', speed: 210 },
  sg550:     { name: 'Krieg 550 Commando', cls: 'weapon_scar20', slot: 'primary', cat: 'rifle', team: TEAM_CT, price: 4200, dmg: 70, range: 0.98, armor: 1.45, clip: 30, ammo: '556nato', speed: 210 },
  m249:      { name: 'ES M249 Para', cls: 'weapon_m249', slot: 'primary', cat: 'mg', team: 0, price: 5750, dmg: 32, range: 0.97, armor: 1.5, clip: 100, ammo: '556natobox', speed: 220 },
  knife:     { name: 'Knife', cls: 'weapon_knife', slot: 'knife', cat: 'knife', team: 0, price: 0, armor: 1.7, speed: 250 },
  hegrenade: { name: 'HE Grenade', cls: 'weapon_hegrenade', slot: 'grenade', cat: 'equip', team: 0, price: 300, max: 1, speed: 250 },
  flashbang: { name: 'Flashbang', cls: 'weapon_flashbang', slot: 'grenade', cat: 'equip', team: 0, price: 200, max: 2, speed: 250 },
  smokegrenade: { name: 'Smoke Grenade', cls: 'weapon_smokegrenade', slot: 'grenade', cat: 'equip', team: 0, price: 300, max: 1, speed: 250 },
};

// ammo type -> price per purchase, rounds per purchase, carry limit
const AMMO = {
  '9mm':        { price: 20, buy: 30, max: 120 },
  '45acp':      { price: 25, buy: 12, max: 100 },
  '357sig':     { price: 50, buy: 13, max: 52 },
  '50ae':       { price: 40, buy: 7, max: 35 },
  '57mm':       { price: 50, buy: 50, max: 100 },
  'buckshot':   { price: 65, buy: 8, max: 32 },
  '556nato':    { price: 60, buy: 30, max: 90 },
  '556natobox': { price: 60, buy: 30, max: 200 },
  '762nato':    { price: 80, buy: 30, max: 90 },
  '338magnum':  { price: 125, buy: 10, max: 30 },
};

const EQUIP = {
  kevlar:   { name: 'Kevlar Vest', price: 650 },
  vesthelm: { name: 'Kevlar Vest & Helmet', price: 1000, helmetOnly: 350 },
  defuser:  { name: 'Defusal Kit', price: 200, team: TEAM_CT },
  nvg:      { name: 'NightVision Goggles', price: 1250, unavailable: true },
};

// 1.6 buy menu, in its own order. Team-only entries are filtered per team.
const BUY_MENU = [
  { id: 'pistol', title: 'Handgun', items: ['glock18', 'usp', 'p228', 'deagle', 'elite', 'fiveseven'] },
  { id: 'shotgun', title: 'Shotgun', items: ['m3', 'xm1014'] },
  { id: 'smg', title: 'Sub-Machine Gun', items: ['mac10', 'tmp', 'mp5navy', 'ump45', 'p90'] },
  { id: 'rifle', title: 'Rifle', itemsT: ['galil', 'ak47', 'scout', 'sg552', 'awp', 'g3sg1'], itemsCT: ['famas', 'scout', 'm4a1', 'aug', 'sg550', 'awp'] },
  { id: 'mg', title: 'Machine Gun', items: ['m249'] },
  { id: 'ammo1', title: 'Primary weapon ammo', action: 'ammo_primary' },
  { id: 'ammo2', title: 'Secondary weapon ammo', action: 'ammo_secondary' },
  { id: 'equip', title: 'Equipment', items: ['kevlar', 'vesthelm', 'flashbang', 'hegrenade', 'smokegrenade', 'nvg', 'defuser'] },
];

// round-end money (gamerules.h REWARD_*); a bomb map pays the bomb values for elimination wins too (Round_Ts / Round_Cts)
const REWARD = {
  TARGET_BOMBED: 3500, BOMB_DEFUSED: 3250, BOMB_PLANTED: 800, TARGET_SAVED: 3250,
  T_ELIM: 3250, CT_ELIM: 3250, KILL: 300, TEAMKILL: -3300,
  LOSER_DEFAULT: 1400, LOSER_MIN: 1500, LOSER_MAX: 3000, LOSER_ADD: 500,
};

const ARMOR_RATIO = 0.5, ARMOR_BONUS = 0.5;
const HIT_MULT = [1, 4, 1, 1.25, 1, 1, 0.75, 0.75, 1];   // by CSHitGroup: generic head chest stomach larm rarm lleg rleg neck
const FALL_SAFE_16 = 500, FALL_FATAL_16 = 1100;          // 1.6: damage = (v - 500) * 100 / 600 * 1.25
const FALL_SAFE_CS2 = 580, FALL_FATAL_CS2 = 1024;        // CS2 (CS:GO) curve, used to recover the landing speed

// CS2 class -> 1.6 id (knives are matched by weapon type instead)
const BY_CLASS = {};
for (const id in WEAPONS) BY_CLASS[WEAPONS[id].cls] = id;
BY_CLASS.weapon_hkp2000 = 'usp';          // a P2000 from someone's loadout counts as the USP
BY_CLASS.weapon_m4a1 = 'm4a1';
BY_CLASS.weapon_cz75a = 'p228';
BY_CLASS.weapon_tec9 = 'glock18';
BY_CLASS.weapon_mp7 = 'mp5navy';
BY_CLASS.weapon_mag7 = 'm3';
BY_CLASS.weapon_sawedoff = 'm3';
BY_CLASS.weapon_revolver = 'deagle';

// player classes (1.6 class menu)
const CLASSES = {
  [TEAM_T]: [
    { id: 'terror', name: 'Phoenix Connexion' }, { id: 'leet', name: 'Elite Crew' },
    { id: 'arctic', name: 'Arctic Avengers' }, { id: 'guerilla', name: 'Guerilla Warfare' }],
  [TEAM_CT]: [
    { id: 'urban', name: 'Seal Team 6' }, { id: 'gsg9', name: 'GSG-9' },
    { id: 'sas', name: 'SAS' }, { id: 'gign', name: 'GIGN' }],
};

function teamName(t) { return t === TEAM_T ? 'Terrorists' : t === TEAM_CT ? 'Counter-Terrorists' : 'Spectators'; }
function otherTeam(t) { return t === TEAM_T ? TEAM_CT : TEAM_T; }
