// ===================================================================================
// FreeDM for CS2 - Doom deathmatch playsim. Part 0: constants, states, thing types.
// Faithful to the Doom 1.9 / Freedoom behaviour; angles are in degrees, units in map units.
// ===================================================================================

const TICRATE = 35;
const DEG = Math.PI / 180;
const MAXRADIUS = 32;
const MAXMOVE = 30;
const STOPSPEED = 0x1000 / 65536;
const FRICTION = 0xe800 / 65536;
const GRAVITY = 1;
const VIEWHEIGHT = 41;
const MAXBOB = 16;
const USERANGE = 64;
const MELEERANGE = 64;
const MISSILERANGE = 32 * 64;
const MAXSTEP = 24;
const BLOCKSIZE = 128;
const ONFLOORZ = -1e9, ONCEILINGZ = 1e9;
const WEAPONTOP = 32, WEAPONBOTTOM = 128, LOWERSPEED = 6, RAISESPEED = 6;
const BONUSADD = 6;
const ANG90 = 90;
const AIMSPREAD = 360 / 64; // 1<<26 BAM

// mobj flags
const MF_SPECIAL = 1, MF_SOLID = 2, MF_SHOOTABLE = 4, MF_NOSECTOR = 8, MF_NOBLOCKMAP = 16, MF_AMBUSH = 32,
  MF_JUSTHIT = 64, MF_JUSTATTACKED = 128,
  MF_SPAWNCEILING = 256, MF_NOGRAVITY = 512, MF_DROPOFF = 0x400, MF_PICKUP = 0x800, MF_NOCLIP = 0x1000,
  MF_FLOAT = 0x4000, MF_INFLOAT = 0x8000, MF_MISSILE = 0x10000, MF_DROPPED = 0x20000, MF_SHADOW = 0x40000, MF_NOBLOOD = 0x80000,
  MF_CORPSE = 0x100000, MF_COUNTKILL = 0x400000, MF_COUNTITEM = 0x800000, MF_SKULLFLY = 0x1000000, MF_NOTDMATCH = 0x2000000;
const MF_BY_NAME = { MF_SPECIAL, MF_SOLID, MF_SHOOTABLE, MF_NOSECTOR, MF_NOBLOCKMAP, MF_AMBUSH, MF_JUSTHIT, MF_JUSTATTACKED,
  MF_SPAWNCEILING, MF_NOGRAVITY, MF_DROPOFF, MF_PICKUP, MF_NOCLIP, MF_FLOAT, MF_INFLOAT, MF_MISSILE, MF_DROPPED, MF_SHADOW,
  MF_NOBLOOD, MF_CORPSE, MF_COUNTKILL, MF_COUNTITEM, MF_SKULLFLY, MF_NOTDMATCH };
function parseFlags(s) { let f = 0; for (const k of String(s || '').split('|')) if (k.trim()) f |= MF_BY_NAME[k.trim()] || 0; return f; }
const FLOATSPEED = 4;
const BASETHRESHOLD = 100;

// line flags
const ML_BLOCKING = 1, ML_BLOCKMONSTERS = 2, ML_TWOSIDED = 4, ML_DONTPEGTOP = 8, ML_DONTPEGBOTTOM = 16, ML_SOUNDBLOCK = 64;

// weapons / ammo
const WP_FIST = 0, WP_PISTOL = 1, WP_SHOTGUN = 2, WP_CHAINGUN = 3, WP_MISSILE = 4, WP_PLASMA = 5, WP_BFG = 6,
  WP_CHAINSAW = 7, WP_SUPERSHOTGUN = 8, NUMWEAPONS = 9, WP_NOCHANGE = 10;
const AM_CLIP = 0, AM_SHELL = 1, AM_CELL = 2, AM_MISL = 3, AM_NOAMMO = 5;
const MAXAMMO = [200, 50, 300, 50];
const CLIPAMMO = [10, 4, 20, 1];
const PW_INVULN = 0, PW_STRENGTH = 1, PW_INVIS = 2, PW_IRONFEET = 3, PW_ALLMAP = 4, PW_INFRARED = 5;
const POWER_TICS = [30 * TICRATE, 1, 60 * TICRATE, 60 * TICRATE, 0, 120 * TICRATE];

// ---------------------------------------------------------------- states
// name: [sprite, frame letter, tics, action, next, bright]
const STATE_DEFS = {
  NULL: ['TROO', 'A', -1, null, 'NULL'],
  LIGHTDONE: ['SHTG', 'E', 0, 'A_Light0', 'NULL'],
  PUNCH: ['PUNG', 'A', 1, 'A_WeaponReady', 'PUNCH'],
  PUNCHDOWN: ['PUNG', 'A', 1, 'A_Lower', 'PUNCHDOWN'],
  PUNCHUP: ['PUNG', 'A', 1, 'A_Raise', 'PUNCHUP'],
  PUNCH1: ['PUNG', 'B', 4, null, 'PUNCH2'],
  PUNCH2: ['PUNG', 'C', 4, 'A_Punch', 'PUNCH3'],
  PUNCH3: ['PUNG', 'D', 5, null, 'PUNCH4'],
  PUNCH4: ['PUNG', 'C', 4, null, 'PUNCH5'],
  PUNCH5: ['PUNG', 'B', 5, 'A_ReFire', 'PUNCH'],
  PISTOL: ['PISG', 'A', 1, 'A_WeaponReady', 'PISTOL'],
  PISTOLDOWN: ['PISG', 'A', 1, 'A_Lower', 'PISTOLDOWN'],
  PISTOLUP: ['PISG', 'A', 1, 'A_Raise', 'PISTOLUP'],
  PISTOL1: ['PISG', 'A', 4, null, 'PISTOL2'],
  PISTOL2: ['PISG', 'B', 6, 'A_FirePistol', 'PISTOL3'],
  PISTOL3: ['PISG', 'C', 4, null, 'PISTOL4'],
  PISTOL4: ['PISG', 'B', 5, 'A_ReFire', 'PISTOL'],
  PISTOLFLASH: ['PISF', 'A', 7, 'A_Light1', 'LIGHTDONE', 1],
  SGUN: ['SHTG', 'A', 1, 'A_WeaponReady', 'SGUN'],
  SGUNDOWN: ['SHTG', 'A', 1, 'A_Lower', 'SGUNDOWN'],
  SGUNUP: ['SHTG', 'A', 1, 'A_Raise', 'SGUNUP'],
  SGUN1: ['SHTG', 'A', 3, null, 'SGUN2'],
  SGUN2: ['SHTG', 'A', 7, 'A_FireShotgun', 'SGUN3'],
  SGUN3: ['SHTG', 'B', 5, null, 'SGUN4'],
  SGUN4: ['SHTG', 'C', 5, null, 'SGUN5'],
  SGUN5: ['SHTG', 'D', 4, null, 'SGUN6'],
  SGUN6: ['SHTG', 'C', 5, null, 'SGUN7'],
  SGUN7: ['SHTG', 'B', 5, null, 'SGUN8'],
  SGUN8: ['SHTG', 'A', 3, null, 'SGUN9'],
  SGUN9: ['SHTG', 'A', 7, 'A_ReFire', 'SGUN'],
  SGUNFLASH1: ['SHTF', 'A', 4, 'A_Light1', 'SGUNFLASH2', 1],
  SGUNFLASH2: ['SHTF', 'B', 3, 'A_Light2', 'LIGHTDONE', 1],
  DSGUN: ['SHT2', 'A', 1, 'A_WeaponReady', 'DSGUN'],
  DSGUNDOWN: ['SHT2', 'A', 1, 'A_Lower', 'DSGUNDOWN'],
  DSGUNUP: ['SHT2', 'A', 1, 'A_Raise', 'DSGUNUP'],
  DSGUN1: ['SHT2', 'A', 3, null, 'DSGUN2'],
  DSGUN2: ['SHT2', 'A', 7, 'A_FireShotgun2', 'DSGUN3'],
  DSGUN3: ['SHT2', 'B', 7, null, 'DSGUN4'],
  DSGUN4: ['SHT2', 'C', 7, 'A_CheckReload', 'DSGUN5'],
  DSGUN5: ['SHT2', 'D', 7, 'A_OpenShotgun2', 'DSGUN6'],
  DSGUN6: ['SHT2', 'E', 7, null, 'DSGUN7'],
  DSGUN7: ['SHT2', 'F', 7, 'A_LoadShotgun2', 'DSGUN8'],
  DSGUN8: ['SHT2', 'G', 6, null, 'DSGUN9'],
  DSGUN9: ['SHT2', 'H', 6, 'A_CloseShotgun2', 'DSGUN10'],
  DSGUN10: ['SHT2', 'A', 5, 'A_ReFire', 'DSGUN'],
  DSNR1: ['SHT2', 'B', 7, null, 'DSNR2'],
  DSNR2: ['SHT2', 'A', 3, null, 'DSGUNDOWN'],
  DSGUNFLASH1: ['SHT2', 'I', 4, 'A_Light1', 'DSGUNFLASH2', 1],
  DSGUNFLASH2: ['SHT2', 'J', 3, 'A_Light2', 'LIGHTDONE', 1],
  CHAIN: ['CHGG', 'A', 1, 'A_WeaponReady', 'CHAIN'],
  CHAINDOWN: ['CHGG', 'A', 1, 'A_Lower', 'CHAINDOWN'],
  CHAINUP: ['CHGG', 'A', 1, 'A_Raise', 'CHAINUP'],
  CHAIN1: ['CHGG', 'A', 4, 'A_FireCGun', 'CHAIN2'],
  CHAIN2: ['CHGG', 'B', 4, 'A_FireCGun', 'CHAIN3'],
  CHAIN3: ['CHGG', 'B', 0, 'A_ReFire', 'CHAIN'],
  CHAINFLASH1: ['CHGF', 'A', 5, 'A_Light1', 'LIGHTDONE', 1],
  CHAINFLASH2: ['CHGF', 'B', 5, 'A_Light2', 'LIGHTDONE', 1],
  MISSILE: ['MISG', 'A', 1, 'A_WeaponReady', 'MISSILE'],
  MISSILEDOWN: ['MISG', 'A', 1, 'A_Lower', 'MISSILEDOWN'],
  MISSILEUP: ['MISG', 'A', 1, 'A_Raise', 'MISSILEUP'],
  MISSILE1: ['MISG', 'B', 8, 'A_GunFlash', 'MISSILE2'],
  MISSILE2: ['MISG', 'B', 12, 'A_FireMissile', 'MISSILE3'],
  MISSILE3: ['MISG', 'B', 0, 'A_ReFire', 'MISSILE'],
  MISSILEFLASH1: ['MISF', 'A', 3, 'A_Light1', 'MISSILEFLASH2', 1],
  MISSILEFLASH2: ['MISF', 'B', 4, null, 'MISSILEFLASH3', 1],
  MISSILEFLASH3: ['MISF', 'C', 4, 'A_Light2', 'MISSILEFLASH4', 1],
  MISSILEFLASH4: ['MISF', 'D', 4, 'A_Light2', 'LIGHTDONE', 1],
  SAW: ['SAWG', 'C', 4, 'A_WeaponReady', 'SAWB'],
  SAWB: ['SAWG', 'D', 4, 'A_WeaponReady', 'SAW'],
  SAWDOWN: ['SAWG', 'C', 1, 'A_Lower', 'SAWDOWN'],
  SAWUP: ['SAWG', 'C', 1, 'A_Raise', 'SAWUP'],
  SAW1: ['SAWG', 'A', 4, 'A_Saw', 'SAW2'],
  SAW2: ['SAWG', 'B', 4, 'A_Saw', 'SAW3'],
  SAW3: ['SAWG', 'B', 0, 'A_ReFire', 'SAW'],
  PLASMA: ['PLSG', 'A', 1, 'A_WeaponReady', 'PLASMA'],
  PLASMADOWN: ['PLSG', 'A', 1, 'A_Lower', 'PLASMADOWN'],
  PLASMAUP: ['PLSG', 'A', 1, 'A_Raise', 'PLASMAUP'],
  PLASMA1: ['PLSG', 'A', 3, 'A_FirePlasma', 'PLASMA2'],
  PLASMA2: ['PLSG', 'B', 20, 'A_ReFire', 'PLASMA'],
  PLASMAFLASH1: ['PLSF', 'A', 4, 'A_Light1', 'LIGHTDONE', 1],
  PLASMAFLASH2: ['PLSF', 'B', 4, 'A_Light1', 'LIGHTDONE', 1],
  BFG: ['BFGG', 'A', 1, 'A_WeaponReady', 'BFG'],
  BFGDOWN: ['BFGG', 'A', 1, 'A_Lower', 'BFGDOWN'],
  BFGUP: ['BFGG', 'A', 1, 'A_Raise', 'BFGUP'],
  BFG1: ['BFGG', 'A', 20, 'A_BFGsound', 'BFG2'],
  BFG2: ['BFGG', 'B', 10, 'A_GunFlash', 'BFG3'],
  BFG3: ['BFGG', 'B', 10, 'A_FireBFG', 'BFG4'],
  BFG4: ['BFGG', 'B', 20, 'A_ReFire', 'BFG'],
  BFGFLASH1: ['BFGF', 'A', 11, 'A_Light1', 'BFGFLASH2', 1],
  BFGFLASH2: ['BFGF', 'B', 6, 'A_Light2', 'LIGHTDONE', 1],

  BLOOD1: ['BLUD', 'C', 8, null, 'BLOOD2'],
  BLOOD2: ['BLUD', 'B', 8, null, 'BLOOD3'],
  BLOOD3: ['BLUD', 'A', 8, null, 'NULL'],
  PUFF1: ['PUFF', 'A', 4, null, 'PUFF2', 1],
  PUFF2: ['PUFF', 'B', 4, null, 'PUFF3'],
  PUFF3: ['PUFF', 'C', 4, null, 'PUFF4'],
  PUFF4: ['PUFF', 'D', 4, null, 'NULL'],
  ROCKET: ['MISL', 'A', 1, null, 'ROCKET', 1],
  EXPLODE1: ['MISL', 'B', 8, 'A_Explode', 'EXPLODE2', 1],
  EXPLODE2: ['MISL', 'C', 6, null, 'EXPLODE3', 1],
  EXPLODE3: ['MISL', 'D', 4, null, 'NULL', 1],
  PLASBALL: ['PLSS', 'A', 6, null, 'PLASBALL2', 1],
  PLASBALL2: ['PLSS', 'B', 6, null, 'PLASBALL', 1],
  PLASEXP: ['PLSE', 'A', 4, null, 'PLASEXP2', 1],
  PLASEXP2: ['PLSE', 'B', 4, null, 'PLASEXP3', 1],
  PLASEXP3: ['PLSE', 'C', 4, null, 'PLASEXP4', 1],
  PLASEXP4: ['PLSE', 'D', 4, null, 'PLASEXP5', 1],
  PLASEXP5: ['PLSE', 'E', 4, null, 'NULL', 1],
  BFGSHOT: ['BFS1', 'A', 4, null, 'BFGSHOT2', 1],
  BFGSHOT2: ['BFS1', 'B', 4, null, 'BFGSHOT', 1],
  BFGLAND: ['BFE1', 'A', 8, null, 'BFGLAND2', 1],
  BFGLAND2: ['BFE1', 'B', 8, null, 'BFGLAND3', 1],
  BFGLAND3: ['BFE1', 'C', 8, 'A_BFGSpray', 'BFGLAND4', 1],
  BFGLAND4: ['BFE1', 'D', 8, null, 'BFGLAND5', 1],
  BFGLAND5: ['BFE1', 'E', 8, null, 'BFGLAND6', 1],
  BFGLAND6: ['BFE1', 'F', 8, null, 'NULL', 1],
  BFGEXP: ['BFE2', 'A', 8, null, 'BFGEXP2', 1],
  BFGEXP2: ['BFE2', 'B', 8, null, 'BFGEXP3', 1],
  BFGEXP3: ['BFE2', 'C', 8, null, 'BFGEXP4', 1],
  BFGEXP4: ['BFE2', 'D', 8, null, 'NULL', 1],

  PLAY: ['PLAY', 'A', -1, null, 'NULL'],
  PLAY_RUN1: ['PLAY', 'A', 4, null, 'PLAY_RUN2'],
  PLAY_RUN2: ['PLAY', 'B', 4, null, 'PLAY_RUN3'],
  PLAY_RUN3: ['PLAY', 'C', 4, null, 'PLAY_RUN4'],
  PLAY_RUN4: ['PLAY', 'D', 4, null, 'PLAY_RUN1'],
  PLAY_ATK1: ['PLAY', 'E', 12, null, 'PLAY'],
  PLAY_ATK2: ['PLAY', 'F', 6, null, 'PLAY_ATK1', 1],
  PLAY_PAIN: ['PLAY', 'G', 4, null, 'PLAY_PAIN2'],
  PLAY_PAIN2: ['PLAY', 'G', 4, 'A_Pain', 'PLAY'],
  PLAY_DIE1: ['PLAY', 'H', 10, null, 'PLAY_DIE2'],
  PLAY_DIE2: ['PLAY', 'I', 10, 'A_PlayerScream', 'PLAY_DIE3'],
  PLAY_DIE3: ['PLAY', 'J', 10, 'A_Fall', 'PLAY_DIE4'],
  PLAY_DIE4: ['PLAY', 'K', 10, null, 'PLAY_DIE5'],
  PLAY_DIE5: ['PLAY', 'L', 10, null, 'PLAY_DIE6'],
  PLAY_DIE6: ['PLAY', 'M', 10, null, 'PLAY_DIE7'],
  PLAY_DIE7: ['PLAY', 'N', -1, null, 'NULL'],
  PLAY_XDIE1: ['PLAY', 'O', 5, null, 'PLAY_XDIE2'],
  PLAY_XDIE2: ['PLAY', 'P', 5, 'A_XScream', 'PLAY_XDIE3'],
  PLAY_XDIE3: ['PLAY', 'Q', 5, 'A_Fall', 'PLAY_XDIE4'],
  PLAY_XDIE4: ['PLAY', 'R', 5, null, 'PLAY_XDIE5'],
  PLAY_XDIE5: ['PLAY', 'S', 5, null, 'PLAY_XDIE6'],
  PLAY_XDIE6: ['PLAY', 'T', 5, null, 'PLAY_XDIE7'],
  PLAY_XDIE7: ['PLAY', 'U', 5, null, 'PLAY_XDIE8'],
  PLAY_XDIE8: ['PLAY', 'V', 5, null, 'PLAY_XDIE9'],
  PLAY_XDIE9: ['PLAY', 'W', -1, null, 'NULL'],
  GIBS: ['POL5', 'A', -1, null, 'GIBS'],

  TFOG: ['TFOG', 'A', 6, null, 'TFOG01', 1],
  TFOG01: ['TFOG', 'B', 6, null, 'TFOG02', 1],
  TFOG02: ['TFOG', 'A', 6, null, 'TFOG2', 1],
  TFOG2: ['TFOG', 'B', 6, null, 'TFOG3', 1],
  TFOG3: ['TFOG', 'C', 6, null, 'TFOG4', 1],
  TFOG4: ['TFOG', 'D', 6, null, 'TFOG5', 1],
  TFOG5: ['TFOG', 'E', 6, null, 'TFOG6', 1],
  TFOG6: ['TFOG', 'F', 6, null, 'TFOG7', 1],
  TFOG7: ['TFOG', 'G', 6, null, 'TFOG8', 1],
  TFOG8: ['TFOG', 'H', 6, null, 'TFOG9', 1],
  TFOG9: ['TFOG', 'I', 6, null, 'TFOG10', 1],
  TFOG10: ['TFOG', 'J', 6, null, 'NULL', 1],
  IFOG: ['IFOG', 'A', 6, null, 'IFOG01', 1],
  IFOG01: ['IFOG', 'B', 6, null, 'IFOG02', 1],
  IFOG02: ['IFOG', 'A', 6, null, 'IFOG2', 1],
  IFOG2: ['IFOG', 'B', 6, null, 'IFOG3', 1],
  IFOG3: ['IFOG', 'C', 6, null, 'IFOG4', 1],
  IFOG4: ['IFOG', 'D', 6, null, 'IFOG5', 1],
  IFOG5: ['IFOG', 'E', 6, null, 'NULL', 1],

  BAR1: ['BAR1', 'A', 6, null, 'BAR2'],
  BAR2: ['BAR1', 'B', 6, null, 'BAR1'],
  BEXP: ['BEXP', 'A', 5, null, 'BEXP2', 1],
  BEXP2: ['BEXP', 'B', 5, 'A_Scream', 'BEXP3', 1],
  BEXP3: ['BEXP', 'C', 5, null, 'BEXP4', 1],
  BEXP4: ['BEXP', 'D', 10, 'A_Explode', 'BEXP5', 1],
  BEXP5: ['BEXP', 'E', 10, null, 'NULL', 1],
};

// Simple looping animations for items and decorations: [sprite, frames, tics, bright]
// Each generates states NAME_0..NAME_n.
const LOOP_DEFS = {
  // items
  ARM1: ['ARM1', 'AB', [6, 7], [0, 1]], ARM2: ['ARM2', 'AB', [6, 6], [0, 1]],
  BON1: ['BON1', 'ABCDCB', 6, 0], BON2: ['BON2', 'ABCDCB', 6, 0],
  SOUL: ['SOUL', 'ABCDCB', 6, 1], MEGA: ['MEGA', 'ABCD', 6, 1],
  PINV: ['PINV', 'ABCD', 6, 1], PSTR: ['PSTR', 'A', -1, 1], PINS: ['PINS', 'ABCD', 6, 1],
  STIM: ['STIM', 'A', -1, 0], MEDI: ['MEDI', 'A', -1, 0],
  CLIP: ['CLIP', 'A', -1, 0], AMMO: ['AMMO', 'A', -1, 0], ROCK: ['ROCK', 'A', -1, 0], BROK: ['BROK', 'A', -1, 0],
  CELL: ['CELL', 'A', -1, 0], CELP: ['CELP', 'A', -1, 0], SHEL: ['SHEL', 'A', -1, 0], SBOX: ['SBOX', 'A', -1, 0],
  BPAK: ['BPAK', 'A', -1, 0],
  SHOT: ['SHOT', 'A', -1, 0], SGN2: ['SGN2', 'A', -1, 0], MGUN: ['MGUN', 'A', -1, 0], LAUN: ['LAUN', 'A', -1, 0],
  PLAS: ['PLAS', 'A', -1, 0], BFUG: ['BFUG', 'A', -1, 0], CSAW: ['CSAW', 'A', -1, 0],
  // decorations
  CAND: ['CAND', 'A', -1, 1], CBRA: ['CBRA', 'A', -1, 1], COLU: ['COLU', 'A', -1, 1],
  TLMP: ['TLMP', 'ABCD', 4, 1], TLP2: ['TLP2', 'ABCD', 4, 1], ELEC: ['ELEC', 'A', -1, 0],
  COL1: ['COL1', 'A', -1, 0], COL5: ['COL5', 'AB', 14, 0], CEYE: ['CEYE', 'ABCB', 6, 1], FSKU: ['FSKU', 'ABC', 6, 1],
  TRE1: ['TRE1', 'A', -1, 0], TRE2: ['TRE2', 'A', -1, 0], TBLU: ['TBLU', 'ABCD', 4, 1], TGRN: ['TGRN', 'ABCD', 4, 1],
  TRED: ['TRED', 'ABCD', 4, 1], SMBT: ['SMBT', 'ABCD', 4, 1], SMGT: ['SMGT', 'ABCD', 4, 1], SMRT: ['SMRT', 'ABCD', 4, 1],
  SMIT: ['SMIT', 'A', -1, 0], POL5: ['POL5', 'A', -1, 0], POL1: ['POL1', 'A', -1, 0], POL4: ['POL4', 'A', -1, 0],
  POL2: ['POL2', 'A', -1, 0], POL3: ['POL3', 'AB', 6, 1], DEADPLAY: ['PLAY', 'N', -1, 0], DEADPOSS: ['POSS', 'L', -1, 0],
  DEADSARG: ['SARG', 'N', -1, 0], GIBPLAY: ['PLAY', 'W', -1, 0],
  GOR2: ['GOR2', 'A', -1, 0], GOR4: ['GOR4', 'A', -1, 0], GOR5: ['GOR5', 'A', -1, 0], GOR1: ['GOR1', 'ABCB', [10, 15, 8, 6], 0],
  HDB1: ['HDB1', 'A', -1, 0], HDB3: ['HDB3', 'A', -1, 0], HDB6: ['HDB6', 'A', -1, 0], POB1: ['POB1', 'A', -1, 0],
  POB2: ['POB2', 'A', -1, 0], BRS1: ['BRS1', 'A', -1, 0],
};
// monster states (00_a_monsters.js, generated from the Doom tables)
Object.assign(STATE_DEFS, MONSTER_STATE_DEFS);
for (const [name, def] of Object.entries(LOOP_DEFS)) {
  const spr = /** @type {string} */ (def[0]), frames = /** @type {string} */ (def[1]), tics = /** @type {any} */ (def[2]), bright = /** @type {any} */ (def[3]);
  const n = frames.length;
  for (let i = 0; i < n; i++) {
    const t = Array.isArray(tics) ? tics[i] : tics;
    const b = Array.isArray(bright) ? bright[i] : bright;
    STATE_DEFS[name + '_' + i] = [spr, frames[i], n === 1 ? -1 : t, null, n === 1 ? name + '_0' : name + '_' + ((i + 1) % n), b];
  }
}

const STATE_INDEX = {};
const STATES = [];
for (const [name, d] of Object.entries(STATE_DEFS)) {
  STATE_INDEX[name] = STATES.length;
  STATES.push({ name, sprite: /** @type {string} */ (d[0]), frame: String(d[1]).charCodeAt(0) - 65, tics: d[2], action: d[3], nextName: d[4], bright: !!d[5], next: 0 });
}
for (const s of STATES) s.next = STATE_INDEX[s.nextName];
const S_NULL = STATE_INDEX.NULL;
function SN(name) {
  const i = STATE_INDEX[name];
  if (i === undefined) throw new Error('no state ' + name);
  return i;
}

// ---------------------------------------------------------------- thing types
// kind: player | missile | fx | item | decor | barrel | teleportdest
const MT = {};
const MOBJINFO = [];
function defMobj(key, o) {
  o.key = key;
  o.id = MOBJINFO.length;
  o.radius = o.radius || 20; o.height = o.height || 16; o.mass = o.mass || 100;
  o.spawnhealth = o.spawnhealth || 1000; o.speed = o.speed || 0; o.damage = o.damage || 0;
  o.flags = o.flags || 0;
  o.spawnstate = o.spawnstate !== undefined ? SN(o.spawnstate) : S_NULL;
  for (const k of ['seestate', 'painstate', 'meleestate', 'missilestate', 'deathstate', 'xdeathstate', 'raisestate'])
    o[k] = o[k] ? SN(o[k]) : S_NULL;
  o.painchance = o.painchance || 0;
  o.reactiontime = o.reactiontime || 0;
  MT[key] = o.id; MOBJINFO.push(o);
  return o;
}
defMobj('PLAYER', { kind: 'player', spawnstate: 'PLAY', spawnhealth: 100, seestate: 'PLAY_RUN1', painstate: 'PLAY_PAIN',
  painchance: 255, missilestate: 'PLAY_ATK1', deathstate: 'PLAY_DIE1', xdeathstate: 'PLAY_XDIE1', radius: 16, height: 56,
  mass: 100, flags: MF_SOLID | MF_SHOOTABLE | MF_DROPOFF | MF_PICKUP | MF_NOTDMATCH, painsound: 'plpain', deathsound: 'pldeth' });
defMobj('BARREL', { kind: 'barrel', doomednum: 2035, spawnstate: 'BAR1', spawnhealth: 20, deathstate: 'BEXP', radius: 10,
  height: 42, flags: MF_SOLID | MF_SHOOTABLE | MF_NOBLOOD, deathsound: 'barexp' });
defMobj('ROCKET', { kind: 'missile', spawnstate: 'ROCKET', deathstate: 'EXPLODE1', seesound: 'rlaunc', deathsound: 'barexp',
  speed: 20, radius: 11, height: 8, damage: 20, flags: MF_NOBLOCKMAP | MF_MISSILE | MF_DROPOFF | MF_NOGRAVITY });
defMobj('PLASMA', { kind: 'missile', spawnstate: 'PLASBALL', deathstate: 'PLASEXP', seesound: 'plasma', deathsound: 'firxpl',
  speed: 25, radius: 13, height: 8, damage: 5, flags: MF_NOBLOCKMAP | MF_MISSILE | MF_DROPOFF | MF_NOGRAVITY });
defMobj('BFG', { kind: 'missile', spawnstate: 'BFGSHOT', deathstate: 'BFGLAND', seesound: 'bfg', deathsound: 'rxplod',
  speed: 25, radius: 13, height: 8, damage: 100, flags: MF_NOBLOCKMAP | MF_MISSILE | MF_DROPOFF | MF_NOGRAVITY });
defMobj('PUFF', { kind: 'fx', spawnstate: 'PUFF1', flags: MF_NOBLOCKMAP | MF_NOGRAVITY });
defMobj('BLOOD', { kind: 'fx', spawnstate: 'BLOOD1', flags: MF_NOBLOCKMAP });
defMobj('TFOG', { kind: 'fx', spawnstate: 'TFOG', flags: MF_NOBLOCKMAP | MF_NOGRAVITY });
defMobj('IFOG', { kind: 'fx', spawnstate: 'IFOG', flags: MF_NOBLOCKMAP | MF_NOGRAVITY });
defMobj('EXTRABFG', { kind: 'fx', spawnstate: 'BFGEXP', flags: MF_NOBLOCKMAP | MF_NOGRAVITY });
defMobj('TELEPORTMAN', { kind: 'teleportdest', doomednum: 14, flags: MF_NOBLOCKMAP | MF_NOSECTOR });

function defItem(key, num, loop, pickup, extra) {
  return defMobj(key, Object.assign({ kind: 'item', doomednum: num, spawnstate: loop + '_0', flags: MF_SPECIAL, pickup }, extra || {}));
}
defItem('SHOTGUN', 2001, 'SHOT', 'weapon:' + WP_SHOTGUN);
defItem('SUPERSHOTGUN', 82, 'SGN2', 'weapon:' + WP_SUPERSHOTGUN);
defItem('CHAINGUN', 2002, 'MGUN', 'weapon:' + WP_CHAINGUN);
defItem('MISSILELAUNCHER', 2003, 'LAUN', 'weapon:' + WP_MISSILE);
defItem('PLASMAGUN', 2004, 'PLAS', 'weapon:' + WP_PLASMA);
defItem('CHAINSAW', 2005, 'CSAW', 'weapon:' + WP_CHAINSAW);
defItem('BFG9000', 2006, 'BFUG', 'weapon:' + WP_BFG);
defItem('CLIP', 2007, 'CLIP', 'ammo:0:1');
defItem('CLIPBOX', 2048, 'AMMO', 'ammo:0:5');
defItem('SHELL', 2008, 'SHEL', 'ammo:1:1');
defItem('SHELLBOX', 2049, 'SBOX', 'ammo:1:5');
defItem('ROCKETAMMO', 2010, 'ROCK', 'ammo:3:1');
defItem('ROCKETBOX', 2046, 'BROK', 'ammo:3:5');
defItem('CELL', 2047, 'CELL', 'ammo:2:1');
defItem('CELLPACK', 17, 'CELP', 'ammo:2:5');
defItem('BACKPACK', 8, 'BPAK', 'backpack');
defItem('STIMPACK', 2011, 'STIM', 'stim');
defItem('MEDIKIT', 2012, 'MEDI', 'medi');
defItem('HEALTHBONUS', 2014, 'BON1', 'hbonus', { flags: MF_SPECIAL | MF_COUNTITEM });
defItem('ARMORBONUS', 2015, 'BON2', 'abonus', { flags: MF_SPECIAL | MF_COUNTITEM });
defItem('GREENARMOR', 2018, 'ARM1', 'armor:1');
defItem('BLUEARMOR', 2019, 'ARM2', 'armor:2');
defItem('SOULSPHERE', 2013, 'SOUL', 'soul', { flags: MF_SPECIAL | MF_COUNTITEM });
defItem('MEGASPHERE', 83, 'MEGA', 'mega', { flags: MF_SPECIAL | MF_COUNTITEM });
defItem('INVULN', 2022, 'PINV', 'invuln', { flags: MF_SPECIAL | MF_COUNTITEM });
defItem('BERSERK', 2023, 'PSTR', 'berserk', { flags: MF_SPECIAL | MF_COUNTITEM });
defItem('INVIS', 2024, 'PINS', 'invis', { flags: MF_SPECIAL | MF_COUNTITEM });

function defDecor(key, num, loop, solid, extra) {
  return defMobj(key, Object.assign({ kind: 'decor', doomednum: num, spawnstate: loop + '_0', radius: 16, height: 16,
    flags: solid ? MF_SOLID : 0 }, extra || {}));
}
const HANG = { flags: MF_SOLID | MF_SPAWNCEILING | MF_NOGRAVITY };
const HANGNB = { flags: MF_SPAWNCEILING | MF_NOGRAVITY };
defDecor('CANDLE', 34, 'CAND', false);
defDecor('CANDELABRA', 35, 'CBRA', true);
defDecor('FLOORLAMP', 2028, 'COLU', true);
defDecor('TECHLAMP', 85, 'TLMP', true);
defDecor('TECHLAMP2', 86, 'TLP2', true);
defDecor('TECHPILLAR', 48, 'ELEC', true);
defDecor('TALLGRNCOL', 30, 'COL1', true);
defDecor('HEARTCOL', 36, 'COL5', true);
defDecor('EVILEYE', 41, 'CEYE', true);
defDecor('FLOATSKULL', 42, 'FSKU', true);
defDecor('TORCHTREE', 43, 'TRE1', true);
defDecor('BIGTREE', 54, 'TRE2', true, { radius: 32 });
defDecor('BLUETORCH', 44, 'TBLU', true);
defDecor('GREENTORCH', 45, 'TGRN', true);
defDecor('REDTORCH', 46, 'TRED', true);
defDecor('SHRTBLUTORCH', 55, 'SMBT', true);
defDecor('SHRTGRNTORCH', 56, 'SMGT', true);
defDecor('SHRTREDTORCH', 57, 'SMRT', true);
defDecor('STALAGTITE', 47, 'SMIT', true);
defDecor('GIBS', 24, 'POL5', false);
defDecor('MEAT2', 25, 'POL1', true);
defDecor('HEADONASTICK', 27, 'POL4', true);
defDecor('HEADSONSTICK', 28, 'POL2', true);
defDecor('HEADCANDLES', 29, 'POL3', true);
defDecor('DEADMARINE', 15, 'DEADPLAY', false);
defDecor('DEADZOMBIE', 18, 'DEADPOSS', false);
defDecor('DEADDEMON', 21, 'DEADSARG', false);
defDecor('GIBBEDMARINE', 10, 'GIBPLAY', false);
defDecor('GIBBEDMARINE2', 12, 'GIBPLAY', false);
defDecor('HANGNOGUTS', 52, 'GOR4', true, Object.assign({ height: 52 }, HANG));
defDecor('HANG2', 59, 'GOR2', false, Object.assign({ height: 84 }, HANGNB));
defDecor('HANG4', 60, 'GOR4', false, Object.assign({ height: 68 }, HANGNB));
defDecor('HANG5', 62, 'GOR5', false, Object.assign({ height: 52 }, HANGNB));
defDecor('HANG1', 63, 'GOR1', false, Object.assign({ height: 68 }, HANGNB));
defDecor('HANGBNOBRAIN', 73, 'HDB1', true, Object.assign({ height: 88 }, HANG));
defDecor('HANGTLOOKDN', 75, 'HDB3', true, Object.assign({ height: 64 }, HANG));
defDecor('HANGTSKULL2', 78, 'HDB6', true, Object.assign({ height: 64 }, HANG));
defDecor('COLONGIBS', 79, 'POB1', false);
defDecor('SMALLPOOL', 80, 'POB2', false);
defDecor('BRAINSTEM', 81, 'BRS1', false);

// monsters and what they shoot (00_a_monsters.js); their behaviour is in 35_enemy.js
for (const [key, def] of Object.entries(MONSTER_DEFS)) defMobj(key, Object.assign({}, def, { flags: parseFlags(def.flags) }));
const MONSTER_TYPES = Object.keys(MONSTER_DEFS).filter((k) => MONSTER_DEFS[k].kind === 'monster');

const DOOMEDNUM = {};
for (const m of MOBJINFO) if (m.doomednum) DOOMEDNUM[m.doomednum] = m.id;

// ---------------------------------------------------------------- weapons
const WEAPONINFO = [
  { ammo: AM_NOAMMO, up: 'PUNCHUP', down: 'PUNCHDOWN', ready: 'PUNCH', atk: 'PUNCH1', flash: 'NULL' },
  { ammo: AM_CLIP, up: 'PISTOLUP', down: 'PISTOLDOWN', ready: 'PISTOL', atk: 'PISTOL1', flash: 'PISTOLFLASH' },
  { ammo: AM_SHELL, up: 'SGUNUP', down: 'SGUNDOWN', ready: 'SGUN', atk: 'SGUN1', flash: 'SGUNFLASH1' },
  { ammo: AM_CLIP, up: 'CHAINUP', down: 'CHAINDOWN', ready: 'CHAIN', atk: 'CHAIN1', flash: 'CHAINFLASH1' },
  { ammo: AM_MISL, up: 'MISSILEUP', down: 'MISSILEDOWN', ready: 'MISSILE', atk: 'MISSILE1', flash: 'MISSILEFLASH1' },
  { ammo: AM_CELL, up: 'PLASMAUP', down: 'PLASMADOWN', ready: 'PLASMA', atk: 'PLASMA1', flash: 'PLASMAFLASH1' },
  { ammo: AM_CELL, up: 'BFGUP', down: 'BFGDOWN', ready: 'BFG', atk: 'BFG1', flash: 'BFGFLASH1' },
  { ammo: AM_NOAMMO, up: 'SAWUP', down: 'SAWDOWN', ready: 'SAW', atk: 'SAW1', flash: 'NULL' },
  { ammo: AM_SHELL, up: 'DSGUNUP', down: 'DSGUNDOWN', ready: 'DSGUN', atk: 'DSGUN1', flash: 'DSGUNFLASH1' },
];
for (const w of WEAPONINFO) for (const k of ['up', 'down', 'ready', 'atk', 'flash']) w[k] = SN(w[k]);
// keyboard slot of each weapon (Doom's 1..7)
const WEAPON_SLOT = [1, 2, 3, 4, 5, 6, 7, 1, 3];
const WEAPON_NAMES = ['fist', 'pistol', 'shotgun', 'chaingun', 'rocket launcher', 'plasma rifle', 'BFG 9000', 'chainsaw', 'super shotgun'];

// pickup messages (Freedoom/FreeDM strings)
const MSG = {
  GOTARMOR: 'Put on a force field vest.', GOTMEGA: 'Put on the attuned force field armor!', GOTHTHBONUS: 'Health boosted!',
  GOTARMBONUS: 'Armor boosted!', GOTSUPER: 'Ectoplasmic surge!', GOTMSPHERE: 'Negentropic surge!',
  GOTSTIM: 'Took a health refill.', GOTMEDINEED: 'Took a large health refill. Never give up!', GOTMEDIKIT: 'Took a large health refill.',
  GOTINVUL: 'Vanguard of the gods!', GOTBERSERK: 'Smash them to pieces!', GOTINVIS: 'Invisibility!',
  GOTCLIP: 'Picked up some bullets.', GOTCLIPBOX: 'Picked up a case of bullets.', GOTROCKET: 'Picked up a missile.',
  GOTROCKBOX: 'Picked up a crate of missiles.', GOTCELL: 'Picked up an energy recharge.', GOTCELLBOX: 'Picked up a large energy recharge.',
  GOTSHELLS: 'Picked up some shotgun shells.', GOTSHELLBOX: 'Picked up a box of shotgun shells.', GOTBACKPACK: 'A backpack for all your ammo storage needs!',
  GOTBFG9000: 'Got the SKAG 1337... time to kick some ass!', GOTCHAINGUN: 'Got the minigun!', GOTCHAINSAW: 'Got the ripsaw!',
  GOTLAUNCHER: 'Got the missile launcher!', GOTPLASMA: 'Got the polaric energy weapon!', GOTSHOTGUN: 'Got the pump-action shotgun!',
  GOTSHOTGUN2: 'Got the double-barrelled shotgun!',
};
