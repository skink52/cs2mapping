// =====================================================================================
//  PUPPET BRAWL core - part 2: pose library and move table
//  Poses are authored for standard proportions and rescaled per character.
// =====================================================================================

const STANCE = {
  hy: 44, tl: 10, hd: 4,
  fa: { x: 19, y: 7 }, ba: { x: 14, y: 8 },
  fl: { x: 12, y: 2 }, bl: { x: -14, y: 2 },
};
const CROUCH = {
  hy: 22, tl: 34, hd: 14,
  fa: { x: 19, y: 6 }, ba: { x: 14, y: 6 },
  fl: { x: 15, y: 2 }, bl: { x: -13, y: 2 },
};
const AIR = {
  tl: 6, hd: 2,
  fa: { x: 10, y: 9 }, ba: { x: 3, y: 6 },
  fl: [72, 108], bl: [14, 96], ff: { rel: 95 }, bf: { rel: 95 },
};
function P(base, over) { return Object.assign({}, base, over || {}); }

// Static poses used by the procedural animator.
const POSES = {
  stance: STANCE,
  crouch: CROUCH,
  air: AIR,
  airRise: P(AIR, { fl: [50, 80], bl: [0, 60], fa: { x: 8, y: 14 }, ba: { x: 2, y: 12 } }),
  squat: P(STANCE, { hy: 36, tl: 18, fl: { x: 12, y: 2 }, bl: { x: -13, y: 2 } }),
  land: P(STANCE, { hy: 38, tl: 16, fl: { x: 13, y: 2 }, bl: { x: -14, y: 2 } }),
  block: P(STANCE, { tl: 4, hd: 10, fa: { x: 17, y: 13 }, ba: { x: 14, y: 14 }, hx: -1 }),
  cblock: P(CROUCH, { tl: 18, hd: 12, fa: { x: 17, y: 11 }, ba: { x: 14, y: 12 } }),
  hitHigh: P(STANCE, { tl: -14, hd: -26, hx: -3, fa: [-15, 55], ba: [-35, 40], fl: { x: 13, y: 2 }, bl: { x: -15, y: 2 } }),
  hitMid: P(STANCE, { hy: 40, tl: 34, hd: 18, fa: { x: 7, y: -7 }, ba: { x: 3, y: -9 }, fl: { x: 12, y: 2 }, bl: { x: -15, y: 2 } }),
  hitCrouch: P(CROUCH, { tl: 34, hd: 22, fa: { x: 6, y: -4 }, ba: { x: 2, y: -6 } }),
  tumble: { tl: -10, hd: -20, fa: [-60, 30], ba: [-100, 40], fl: [50, 50], bl: [10, 40], ff: { rel: 100 }, bf: { rel: 100 } },
  down: { rot: -90, tl: 0, hd: -6, fa: [-50, 30], ba: [-20, 40], fl: [62, 74], bl: [38, 52], ff: { rel: 95 }, bf: { rel: 95 } },
  downKO: { rot: -90, tl: 0, hd: -24, fa: [-80, 10], ba: [-110, 20], fl: [30, 20], bl: [12, 8], ff: { rel: 70 }, bf: { rel: 80 } },
  kneel: P(CROUCH, { hy: 22, tl: 30, hd: 10, fa: { x: 10, y: -12 }, ba: { x: 4, y: -16 }, fl: { x: 16, y: 2 }, bl: { x: -16, y: 2 } }),
  dashF: P(STANCE, { tl: 26, hd: 8, hx: 3, fl: { x: 20, y: 6 }, bl: { x: -22, y: 3 } }),
  dashB: P(STANCE, { tl: -10, hd: -4, hx: -2, fl: { x: 6, y: 2 }, bl: { x: -20, y: 9 } }),
  waiting: P(STANCE, { hy: 46, tl: 2, hd: 0, fa: [12, 18], ba: [-6, 16], fl: { x: 6, y: 2 }, bl: { x: -8, y: 2 } }),
  cheer: P(STANCE, { hy: 46, tl: -4, hd: -8, fa: [170, 10], ba: [-6, 16], fl: { x: 6, y: 2 }, bl: { x: -8, y: 2 } }),
  thrown: { tl: -20, hd: -24, fa: [-80, 40], ba: [-120, 30], fl: [40, 60], bl: [10, 40] },
  victoryBoxer: P(STANCE, { hy: 46, tl: -4, hd: -12, fa: [168, 28], ba: [155, 40], fl: { x: 9, y: 2 }, bl: { x: -10, y: 2 } }),
  victorySalute: P(STANCE, { hy: 48, tl: 0, hd: 0, fa: [168, 132], ba: [2, 4], fl: { x: 5, y: 2 }, bl: { x: -5, y: 2 } }),
  victoryBallet: { hy: 50, tl: -4, hd: -8, fa: [165, 30], ba: [140, 40], fl: { x: 3, y: 2 }, bl: [-8, 120], ff: 30, bf: { rel: 150 } },
  victoryBow: P(STANCE, { hy: 45, tl: 62, hd: 20, fa: [-40, 20], ba: [60, 70], fl: { x: 8, y: 2 }, bl: { x: -12, y: 2 } }),
  defeat: P(STANCE, { hy: 42, tl: 36, hd: 30, fa: [-8, 6], ba: [4, 6], fl: { x: 9, y: 2 }, bl: { x: -11, y: 2 } }),
};

// ------------------------------------------------------------------ move table -------
// Frame counts are sim frames (64 per second) before the character's frame multiplier.
// anim: [frame, pose] keyframes; base names a POSES entry the overrides merge onto.
// hits: active windows. tip = which point carries the hitbox (fF fist, bF, fT toe, bT,
//       fK knee, S shoulder, G ground-wave). level: high | mid | low | air.
// vel:  [from, to, vx, vy?] forward velocity applied while in that window.
const MOVES = {
  // ------------------------------------------------ standing normals
  jab: {
    name: "Jab", total: 18, base: "stance", chain: ["jab", "straight", "kickMid"], cancel: true, next: { P: "p", K: "mix" },
    anim: [[0, {}], [2, { tl: 7, fa: { x: 9, y: 11 }, ba: { x: 4, y: 7 } }, "w"],
      [5, { tl: 19, hx: 3, hd: 6, fa: { x: 30.5, y: 4 }, ba: { x: 3, y: 6 } }], [8, { tl: 19, hx: 3, hd: 6, fa: { x: 30.5, y: 4 }, ba: { x: 3, y: 6 } }],
      [12, { tl: 11, hx: 2, fa: { x: 15, y: 9 }, ba: { x: 4, y: 6 } }, "f"], [18, {}]],
    hits: [{ from: 5, to: 7, tip: "fF", r: 5.5, dmg: 4, level: "high", hitstun: 14, blockstun: 9, push: 150, hitstop: 4, snd: "hit" }],
  },
  straight: {
    name: "Straight", total: 25, base: "stance", chain: ["kickMid"], cancel: true,
    anim: [[0, {}], [3, { tl: 2, hx: -1, ba: { x: -3, y: 4 }, fa: { x: 10, y: 9 } }, "w"],
      [7, { tl: 27, hx: 5, hd: 6, ba: { x: 30.5, y: 1 }, fa: { x: 4, y: 9 }, bl: { x: -18, y: 2 } }],
      [10, { tl: 27, hx: 5, hd: 6, ba: { x: 30.5, y: 1 }, fa: { x: 4, y: 9 }, bl: { x: -18, y: 2 } }],
      [15, { tl: 14, hx: 3, ba: { x: 14, y: 7 }, fa: { x: 8, y: 9 }, bl: { x: -16, y: 2 } }, "f"], [25, {}]],
    hits: [{ from: 7, to: 9, tip: "bF", r: 6.5, dmg: 8, level: "high", hitstun: 18, blockstun: 12, push: 210, hitstop: 6, snd: "heavy" }],
    vel: [[5, 9, 60]],
  },
  uppercut: {
    name: "Uppercut", total: 34, base: "crouch",
    anim: [[0, { tl: 28, ba: { x: 7, y: -10 }, fa: { x: 10, y: 8 } }],
      [8, { hy: 47, tl: -6, hd: -10, ba: { x: 10, y: 29 }, fa: { x: 6, y: 4 }, fl: { x: 10, y: 2 }, bl: { x: -12, y: 2 } }],
      [12, { hy: 47, tl: -6, hd: -10, ba: { x: 9, y: 30 }, fa: { x: 6, y: 4 }, fl: { x: 10, y: 2 }, bl: { x: -12, y: 2 } }],
      [34, {}]],
    hits: [{ from: 6, to: 11, tip: "bF", r: 7, dmg: 13, level: "mid", hitstun: 30, blockstun: 16, push: 120, hitstop: 8, snd: "heavy", launch: { vx: 140, vy: 780 }, kd: true }],
  },
  kickMid: {
    name: "Snap kick", total: 25, base: "stance", cancel: true, next: { K: "k" },
    anim: [[0, {}], [3, { tl: 0, fl: [80, 110], bl: { x: -8, y: 2 } }, "w"],
      [7, { hy: 45, tl: -10, fl: { x: 40, y: 2, r: "h" }, ff: 102, bl: { x: -7, y: 2 } }],
      [11, { hy: 45, tl: -10, fl: { x: 40, y: 2, r: "h" }, ff: 102, bl: { x: -7, y: 2 } }], [16, { tl: -4, fl: [70, 100], bl: { x: -8, y: 2 } }, "f"], [25, {}]],
    hits: [{ from: 7, to: 10, tip: "fT", r: 6, dmg: 7, level: "mid", hitstun: 16, blockstun: 11, push: 190, hitstop: 5, snd: "hit" }],
  },
  longKick: {
    name: "Side kick", total: 30, base: "stance",
    anim: [[0, {}], [5, { tl: -6, fl: [96, 132], bl: { x: -5, y: 2 } }],
      [10, { hy: 46, tl: -30, hd: -6, fl: { x: 50, y: 6, r: "h" }, ff: 96, bl: { x: -8, y: 2 }, fa: { x: 10, y: 4 }, ba: { x: -4, y: 2 } }],
      [14, { hy: 46, tl: -30, hd: -6, fl: { x: 50, y: 6, r: "h" }, ff: 96, bl: { x: -8, y: 2 }, fa: { x: 10, y: 4 }, ba: { x: -4, y: 2 } }], [30, {}]],
    hits: [{ from: 10, to: 13, tip: "fT", r: 6, dmg: 9, level: "mid", hitstun: 17, blockstun: 12, push: 250, hitstop: 6, snd: "heavy" }],
    vel: [[4, 10, 70]],
  },
  roundhouse: {
    name: "Roundhouse", total: 36, base: "stance",
    anim: [[0, {}], [5, { tl: -4, bl: [64, 124], fl: { x: 4, y: 2 } }],
      [12, { hy: 46, tl: -26, hd: -8, bl: { x: 41, y: 26, r: "h" }, bf: 118, fl: { x: -2, y: 2 }, fa: { x: 6, y: 2 }, ba: [-40, 20] }],
      [16, { hy: 46, tl: -26, hd: -8, bl: { x: 41, y: 26, r: "h" }, bf: 118, fl: { x: -2, y: 2 }, fa: { x: 6, y: 2 }, ba: [-40, 20] }], [36, {}]],
    hits: [{ from: 11, to: 15, tip: "bT", r: 7, dmg: 11, level: "high", hitstun: 22, blockstun: 14, push: 220, hitstop: 8, snd: "heavy", launch: { vx: 260, vy: 380 }, kd: true }],
  },
  // ------------------------------------------------ crouching
  sweep: {
    name: "Sweep", total: 32, base: "crouch",
    anim: [[0, {}], [4, { hy: 18, tl: 34, fa: { x: 10, y: -34 }, bl: { x: 10, y: 2 }, fl: { x: 8, y: 2 } }],
      [8, { hy: 18, tl: 36, fa: { x: 10, y: -34 }, ba: { x: 2, y: 2 }, bl: { x: 46, y: -14, r: "h" }, bf: 92, fl: { x: 6, y: 2 } }],
      [12, { hy: 18, tl: 36, fa: { x: 10, y: -34 }, ba: { x: 2, y: 2 }, bl: { x: 46, y: -14, r: "h" }, bf: 92, fl: { x: 6, y: 2 } }], [32, {}]],
    hits: [{ from: 8, to: 11, tip: "bT", r: 7, dmg: 7, level: "low", hitstun: 18, blockstun: 12, push: 80, hitstop: 6, snd: "hit", launch: { vx: 60, vy: 260 }, kd: true }],
  },
  // ------------------------------------------------ air
  airPunch: {
    name: "Air punch", total: 18, base: "air", air: true,
    anim: [[0, {}], [2, { tl: 8, fa: { x: 8, y: 6 } }, "w"], [4, { tl: 22, fa: { x: 28, y: -12 }, ba: { x: 2, y: 4 } }], [12, { tl: 22, fa: { x: 28, y: -12 }, ba: { x: 2, y: 4 } }], [18, {}]],
    hits: [{ from: 4, to: 12, tip: "fF", r: 6.5, dmg: 7, level: "air", hitstun: 16, blockstun: 10, push: 120, hitstop: 5, snd: "hit" }],
  },
  airKick: {
    name: "Flying kick", total: 21, base: "air", air: true,
    anim: [[0, {}], [5, { tl: -14, fl: { x: 38, y: -22, r: "h" }, ff: { rel: 100 }, bl: [20, 110], fa: [40, 60], ba: [-30, 50] }],
      [15, { tl: -14, fl: { x: 38, y: -22, r: "h" }, ff: { rel: 100 }, bl: [20, 110], fa: [40, 60], ba: [-30, 50] }], [21, {}]],
    hits: [{ from: 5, to: 15, tip: "fT", r: 7, dmg: 9, level: "air", hitstun: 18, blockstun: 12, push: 160, hitstop: 6, snd: "heavy", airKd: true }],
  },
  // ------------------------------------------------ throws
  throw: {
    name: "Throw", total: 34, base: "stance", throw: true,
    anim: [[0, {}], [4, { tl: 20, hx: 3, fa: { x: 24, y: -2 }, ba: { x: 22, y: 0 } }],
      [14, { tl: -8, hd: -16, fa: [172, 8], ba: [178, 8] }],
      [20, { tl: -28, hd: -20, fa: [206, 0], ba: [214, 0] }], [34, {}]],
    // victim offset (thrower's facing frame): [frame, dx, dy(pelvis above ground), rot]
    victim: [[0, 30, 40, 0], [4, 28, 42, -10], [14, 12, 74, -80], [20, -22, 66, -150]],
    release: 20, dmg: 11, toss: { vx: -320, vy: 300 },
  },
  throwWhiff: {
    name: "Grab", total: 20, base: "stance",
    anim: [[0, {}], [4, { tl: 20, hx: 3, fa: { x: 24, y: -2 }, ba: { x: 22, y: 0 } }], [9, { tl: 20, hx: 3, fa: { x: 24, y: -2 }, ba: { x: 22, y: 0 } }], [20, {}]],
  },

  // ================================================ SPECIALS
  // ---- TIMBER
  knotShot: {
    name: "Knot Shot", total: 30, base: "stance", special: true, motion: ["B", "F"], btn: "P",
    anim: [[0, {}], [6, { tl: -6, ba: [-62, 72] }], [12, { tl: 22, hx: 3, ba: { x: 30, y: 6 } }], [16, { tl: 22, hx: 3, ba: { x: 30, y: 6 } }], [30, {}]],
    projectile: { at: 12, from: "bF", vx: 430, vy: 0, g: 0, r: 7, dmg: 9, chip: 2, hitstun: 16, blockstun: 14, push: 200, life: 2.5, level: "mid" },
  },
  haymaker: {
    name: "Haymaker", total: 46, base: "stance", special: true, motion: ["F", "F"], btn: "P",
    anim: [[0, {}], [9, { tl: -14, hx: -3, ba: [-72, 100], fa: { x: 8, y: 10 } }],
      [13, { tl: 32, hx: 8, hd: 6, ba: { x: 31, y: 2 }, fa: { x: 4, y: 6 }, fl: { x: 22, y: 3 }, bl: { x: -24, y: 2 } }],
      [24, { tl: 32, hx: 8, hd: 6, ba: { x: 31, y: 2 }, fa: { x: 4, y: 6 }, fl: { x: 22, y: 3 }, bl: { x: -24, y: 2 } }],
      [32, { tl: 16, hx: 3, ba: { x: 14, y: 8 }, fa: { x: 8, y: 8 }, fl: { x: 16, y: 2 }, bl: { x: -18, y: 2 } }, "f"], [46, {}]],
    hits: [{ from: 11, to: 23, tip: "bF", r: 8, dmg: 14, level: "mid", hitstun: 26, blockstun: 18, push: 400, hitstop: 9, snd: "heavy", chip: 3 }],
    vel: [[10, 24, 500]],
  },
  risingSplinter: {
    name: "Rising Splinter", total: 30, base: "crouch", special: true, motion: ["D", "F"], btn: "P",
    anim: [[0, { tl: 26, ba: { x: 6, y: -10 } }], [4, { hy: 46, tl: -8, ba: [176, 4], fa: [60, 80], fl: { x: 12, y: 2 }, bl: { x: -12, y: 2 } }],
      [10, { hy: null, tl: -8, ba: [176, 4], fa: [60, 80], fl: [60, 100], bl: [10, 90] }],
      [16, { hy: null, tl: -8, ba: [176, 4], fa: [60, 80], fl: [60, 100], bl: [10, 90] }], [30, P(AIR, { hy: null })]],
    hits: [{ from: 3, to: 15, tip: "bF", r: 8, dmg: 12, level: "mid", hitstun: 30, blockstun: 16, push: 100, hitstop: 8, snd: "heavy", launch: { vx: 120, vy: 760 }, kd: true, chip: 3 }],
    invuln: [1, 9], jump: { at: 4, vx: 110, vy: 720 }, landLag: 14,
  },
  // ---- BRASS
  cogToss: {
    name: "Cog Toss", total: 34, base: "stance", special: true, motion: ["B", "F"], btn: "P",
    anim: [[0, {}], [8, { tl: 16, ba: [-50, 20], fa: { x: 10, y: 4 } }], [16, { tl: -4, ba: [128, 20] }], [20, { tl: -4, ba: [128, 20] }], [34, {}]],
    projectile: { at: 16, from: "bF", vx: 300, vy: 560, g: 1700, r: 8.5, dmg: 11, chip: 3, hitstun: 20, blockstun: 16, push: 200, life: 3, level: "mid", ground: true },
  },
  steamRam: {
    name: "Steam Ram", total: 44, base: "stance", special: true, motion: ["B", "F"], btn: "K",
    anim: [[0, {}], [10, { hy: 40, tl: -8, fa: [20, 110], ba: [0, 120] }],
      [14, { tl: 42, hx: 6, hd: -14, fa: [24, 110], ba: [4, 120], fl: { x: 22, y: 2 }, bl: { x: -24, y: 2 } }],
      [30, { tl: 42, hx: 6, hd: -14, fa: [24, 110], ba: [4, 120], fl: { x: 22, y: 2 }, bl: { x: -24, y: 2 } }], [44, {}]],
    hits: [{ from: 13, to: 30, tip: "S", r: 12, dmg: 13, level: "mid", hitstun: 24, blockstun: 16, push: 260, hitstop: 9, snd: "heavy", launch: { vx: 320, vy: 360 }, kd: true, chip: 3 }],
    vel: [[12, 30, 470]], armor: [1, 30],
  },
  pistonStomp: {
    name: "Piston Stomp", total: 40, base: "stance", special: true, motion: ["D", "D"], btn: "K",
    anim: [[0, {}], [8, { hy: 52, tl: -4, fl: [42, 64], bl: [-8, 40], fa: [60, 60], ba: [40, 60] }],
      [18, { hy: 36, tl: 30, hd: 12, fl: { x: 15, y: 2 }, bl: { x: -15, y: 2 }, fa: [-6, 8], ba: [8, 8] }],
      [24, { hy: 36, tl: 30, hd: 12, fl: { x: 15, y: 2 }, bl: { x: -15, y: 2 }, fa: [-6, 8], ba: [8, 8] }], [40, {}]],
    hits: [
      { from: 18, to: 22, tip: "G", gx: 34, gy: 6, r: 34, dmg: 10, level: "low", hitstun: 20, blockstun: 14, push: 140, hitstop: 8, snd: "heavy", launch: { vx: 120, vy: 420 }, kd: true, shake: 1, chip: 2 },
      { from: 18, to: 22, tip: "G", gx: -20, gy: 6, r: 20, dmg: 8, level: "low", hitstun: 20, blockstun: 14, push: 140, hitstop: 8, snd: "heavy", launch: { vx: -120, vy: 380 }, kd: true, chip: 2 },
    ],
  },
  // ---- PIROUETTE
  spinKick: {
    name: "Spin Kick", total: 40, base: "stance", special: true, motion: ["D", "B"], btn: "K",
    anim: [[0, {}], [6, { hy: 47, tl: -16, fl: { x: 46, y: 8, r: "h" }, ff: { rel: 150 }, bl: { x: -2, y: 2 }, fa: [96, 0], ba: [84, 0] }],
      [30, { hy: 47, tl: -16, fl: { x: 46, y: 8, r: "h" }, ff: { rel: 150 }, bl: { x: -2, y: 2 }, fa: [96, 0], ba: [84, 0] }], [40, {}]],
    flip: [6, 30, 4],
    hits: [
      { from: 8, to: 11, tip: "fT", r: 7, dmg: 5, level: "mid", hitstun: 16, blockstun: 10, push: 60, hitstop: 4, snd: "hit", chip: 1 },
      { from: 16, to: 19, tip: "fT", r: 7, dmg: 5, level: "mid", hitstun: 16, blockstun: 10, push: 60, hitstop: 4, snd: "hit", chip: 1 },
      { from: 24, to: 28, tip: "fT", r: 7, dmg: 6, level: "mid", hitstun: 20, blockstun: 12, push: 120, hitstop: 7, snd: "heavy", launch: { vx: 220, vy: 380 }, kd: true, chip: 1 },
    ],
    vel: [[6, 30, 250]],
  },
  glide: {
    name: "Glide", total: 36, base: "stance", special: true, motion: ["F", "F"], btn: "K",
    anim: [[0, {}], [5, { hy: null, tl: -56, hd: 6, fl: [82, 8], ff: { rel: 150 }, bl: [42, 112], fa: [-64, 20], ba: [100, 30] }],
      [22, { hy: null, tl: -56, hd: 6, fl: [82, 8], ff: { rel: 150 }, bl: [42, 112], fa: [-64, 20], ba: [100, 30] }], [36, {}]],
    hits: [{ from: 6, to: 20, tip: "fT", r: 7, dmg: 9, level: "low", hitstun: 20, blockstun: 12, push: 120, hitstop: 7, snd: "heavy", launch: { vx: 140, vy: 300 }, kd: true, chip: 2 }],
    vel: [[4, 22, 560]],
  },
  fouette: {
    name: "Fouette", total: 28, base: "crouch", special: true, motion: ["D", "U"], btn: "K",
    anim: [[0, {}], [4, { hy: 40, tl: -6, fl: [100, 100], bl: { x: -6, y: 2 }, fa: [100, 40], ba: [60, 40] }],
      [7, { hy: null, tl: -14, fl: [176, 6], ff: { rel: 170 }, bl: [-20, 40], fa: [120, 20], ba: [60, 30] }],
      [16, { hy: null, tl: -14, fl: [176, 6], ff: { rel: 170 }, bl: [-20, 40], fa: [120, 20], ba: [60, 30] }], [28, P(AIR, { hy: null })]],
    hits: [{ from: 5, to: 16, tip: "fT", r: 7.5, dmg: 11, level: "mid", hitstun: 30, blockstun: 14, push: 100, hitstop: 8, snd: "heavy", launch: { vx: 140, vy: 700 }, kd: true, chip: 2 }],
    invuln: [1, 8], jump: { at: 4, vx: 80, vy: 700 }, landLag: 12,
  },
  // ---- MOTLEY
  juggleBall: {
    name: "Juggle Ball", total: 26, base: "stance", special: true, motion: ["B", "F"], btn: "P",
    anim: [[0, {}], [5, { tl: 4, ba: [-40, 50] }], [9, { tl: 14, ba: { x: 28, y: 10 } }], [13, { tl: 14, ba: { x: 28, y: 10 } }], [26, {}]],
    projectile: { at: 9, from: "bF", vx: 570, vy: 0, g: 0, r: 5.5, dmg: 7, chip: 2, hitstun: 15, blockstun: 12, push: 160, life: 2, level: "mid" },
  },
  pratfall: {
    name: "Pratfall", total: 40, base: "stance", special: true, motion: ["D", "U"], btn: "P",
    anim: [[0, {}], [6, { hy: 30, tl: 30, hd: 14, sc: 1 }], [14, { hy: 30, tl: 30, hd: 14, sc: 0.04 }], [16, { hy: 30, tl: 30, sc: 0.04 }],
      [24, { hy: 44, tl: 0, sc: 1, fa: [150, 30], ba: [130, 30] }], [40, {}]],
    invuln: [3, 26], teleport: 15,
  },
  cartwheel: {
    name: "Cartwheel", total: 34, base: "stance", special: true, motion: ["F", "F"], btn: "K",
    anim: [[0, {}], [4, { tl: 20, rot: 0, fa: [180, 0], ba: [175, 0], fl: [32, 0], bl: [-32, 0] }],
      [26, { tl: 20, rot: 360, fa: [180, 0], ba: [175, 0], fl: [32, 0], bl: [-32, 0] }], [34, {}]],
    autoAll: true,
    hits: [
      { from: 9, to: 13, tip: "fF", r: 7, dmg: 6, level: "mid", hitstun: 18, blockstun: 10, push: 50, hitstop: 5, snd: "hit", chip: 1 },
      { from: 17, to: 21, tip: "fT", r: 7, dmg: 7, level: "mid", hitstun: 20, blockstun: 12, push: 120, hitstop: 7, snd: "heavy", launch: { vx: 180, vy: 400 }, kd: true, chip: 1 },
    ],
    vel: [[4, 26, 360]],
  },
  // ================================================ COMBO FINISHERS
  // P after a jab, or K after a snap kick (hit, blocked or whiffed), gives the fighter's own
  // second hit. "w" keys are wind-ups and "f" keys follow-throughs: each fighter's style
  // makes them bigger or smaller.
  // ---- TIMBER
  splitter: {
    name: "Splitter", total: 27, base: "stance", combo: true, cancel: true, next: { K: "k" },
    anim: [[0, { tl: 12, hx: 2, fa: { x: 15, y: 9 } }], [3, { tl: 4, hx: 0, ba: [-30, 100], fa: { x: 12, y: 9 } }, "w"],
      [7, { tl: 28, hx: 7, hd: 8, ba: { x: 27, y: 8 }, fa: { x: 6, y: 9 }, bl: { x: -17, y: 2 } }],
      [10, { tl: 28, hx: 7, hd: 8, ba: { x: 27, y: 8 }, fa: { x: 6, y: 9 }, bl: { x: -17, y: 2 } }],
      [16, { tl: 12, hx: 3, ba: { x: 12, y: 10 }, fa: { x: 8, y: 9 } }, "f"], [27, {}]],
    hits: [{ from: 7, to: 9, tip: "bF", r: 7, dmg: 9, level: "high", hitstun: 20, blockstun: 13, push: 240, hitstop: 7, snd: "heavy" }],
    vel: [[2, 9, 120]],
  },
  timberFall: {
    name: "Timber Fall", total: 34, base: "stance", combo: true,
    anim: [[0, {}], [4, { tl: -4, bl: [50, 110], fl: { x: 5, y: 2 } }, "w"],
      [10, { hy: 46, tl: -24, hd: -8, bl: { x: 40, y: 22, r: "h" }, bf: 115, fl: { x: -2, y: 2 }, fa: { x: 6, y: 3 }, ba: [-40, 20] }],
      [14, { hy: 46, tl: -24, hd: -8, bl: { x: 40, y: 22, r: "h" }, bf: 115, fl: { x: -2, y: 2 }, fa: { x: 6, y: 3 }, ba: [-40, 20] }],
      [21, { tl: -8, bl: [30, 60], fl: { x: 4, y: 2 } }, "f"], [34, {}]],
    hits: [{ from: 10, to: 13, tip: "bT", r: 7, dmg: 10, level: "high", hitstun: 22, blockstun: 14, push: 230, hitstop: 8, snd: "heavy", launch: { vx: 240, vy: 360 }, kd: true }],
    vel: [[2, 10, 90]],
  },
  // ---- BRASS
  rivetHammer: {
    name: "Rivet Hammer", total: 35, base: "stance", combo: true, next: { K: "k" },
    anim: [[0, {}], [6, { hy: 46, tl: -10, hd: -6, fa: [170, 30], ba: [165, 30] }, "w"],
      [11, { hy: 40, tl: 34, hx: 5, hd: 10, fa: { x: 24, y: -6 }, ba: { x: 22, y: -4 } }],
      [15, { hy: 40, tl: 34, hx: 5, hd: 10, fa: { x: 24, y: -6 }, ba: { x: 22, y: -4 } }],
      [22, { tl: 18, hx: 2, fa: { x: 12, y: 2 }, ba: { x: 10, y: 2 } }, "f"], [35, {}]],
    hits: [{ from: 11, to: 14, tip: "fF", r: 8.5, dmg: 9, level: "over", hitstun: 24, blockstun: 15, push: 200, hitstop: 9, snd: "heavy", shake: 1 }],
    vel: [[4, 12, 120]],
  },
  boilerKick: {
    name: "Boiler Kick", total: 32, base: "stance", combo: true,
    anim: [[0, {}], [5, { tl: -4, fl: [100, 120], bl: { x: -8, y: 2 } }, "w"],
      [10, { hy: 45, tl: -14, fl: { x: 44, y: 16, r: "h" }, ff: { rel: 100 }, bl: { x: -8, y: 2 }, fa: { x: 12, y: 8 }, ba: { x: 6, y: 8 } }],
      [14, { hy: 45, tl: -14, fl: { x: 44, y: 16, r: "h" }, ff: { rel: 100 }, bl: { x: -8, y: 2 }, fa: { x: 12, y: 8 }, ba: { x: 6, y: 8 } }],
      [20, { tl: -4, fl: [70, 100], bl: { x: -8, y: 2 } }, "f"], [32, {}]],
    hits: [{ from: 10, to: 13, tip: "fT", r: 7.5, dmg: 10, level: "mid", hitstun: 20, blockstun: 14, push: 420, hitstop: 8, snd: "heavy" }],
    vel: [[3, 10, 100]],
  },
  // ---- PIROUETTE
  pasDeDeux: {
    name: "Pas de Deux", total: 28, base: "stance", combo: true, cancel: true, next: { K: "k" },
    anim: [[0, {}], [2, { tl: 8, ba: { x: 6, y: 10 } }, "w"], [5, { tl: 22, hx: 4, ba: { x: 30, y: 5 }, fa: { x: 6, y: 9 } }],
      [8, { tl: 10, hx: 2, ba: { x: 10, y: 8 }, fa: { x: 10, y: 12 } }], [11, { tl: 24, hx: 6, fa: { x: 30, y: 10 }, ba: { x: 4, y: 6 } }],
      [14, { tl: 24, hx: 6, fa: { x: 30, y: 10 }, ba: { x: 4, y: 6 } }], [19, { tl: 10, fa: { x: 14, y: 9 } }, "f"], [28, {}]],
    hits: [
      { from: 5, to: 6, tip: "bF", r: 6, dmg: 5, level: "high", hitstun: 16, blockstun: 10, push: 60, hitstop: 4, snd: "hit" },
      { from: 11, to: 13, tip: "fF", r: 6.5, dmg: 7, level: "high", hitstun: 20, blockstun: 12, push: 200, hitstop: 6, snd: "heavy" },
    ],
    vel: [[1, 13, 150]],
  },
  arabesque: {
    name: "Arabesque", total: 34, base: "stance", combo: true,
    anim: [[0, {}], [4, { tl: 4, bl: [40, 90], fa: [60, 30], ba: [100, 20] }, "w"],
      [9, { hy: 48, tl: -34, hd: -10, bl: [160, 8], bf: { rel: 160 }, fl: { x: 2, y: 2 }, fa: [100, 10], ba: [150, 10] }],
      [13, { hy: 48, tl: -34, hd: -10, bl: [160, 8], bf: { rel: 160 }, fl: { x: 2, y: 2 }, fa: [100, 10], ba: [150, 10] }],
      [20, { tl: -10, bl: [60, 60], fa: [60, 30] }, "f"], [34, {}]],
    hits: [{ from: 9, to: 12, tip: "bT", r: 7.5, dmg: 10, level: "high", hitstun: 26, blockstun: 13, push: 120, hitstop: 8, snd: "heavy", launch: { vx: 120, vy: 620 }, kd: true }],
    vel: [[2, 9, 100]],
  },
  // ---- MOTLEY
  slapstick: {
    name: "Slapstick", total: 30, base: "stance", combo: true, cancel: true, next: { K: "k" },
    anim: [[0, {}], [3, { tl: 0, ba: [-20, 40], fa: { x: 8, y: 10 } }, "w"], [6, { tl: 18, hx: 3, ba: { x: 26, y: 12 }, fa: { x: 6, y: 8 } }],
      [9, { tl: 6, hx: 1, ba: { x: 10, y: 4 }, fa: [-10, 40] }], [12, { tl: 20, hx: 5, fa: { x: 28, y: 12 }, ba: { x: 4, y: 6 } }],
      [15, { tl: 20, hx: 5, fa: { x: 28, y: 12 }, ba: { x: 4, y: 6 } }], [21, { tl: 4, fa: { x: 12, y: 4 } }, "f"], [30, {}]],
    hits: [
      { from: 6, to: 7, tip: "bF", r: 7, dmg: 4, level: "high", hitstun: 16, blockstun: 10, push: 40, hitstop: 4, snd: "hit" },
      { from: 12, to: 14, tip: "fF", r: 7, dmg: 6, level: "high", hitstun: 22, blockstun: 12, push: 220, hitstop: 6, snd: "heavy" },
    ],
    vel: [[1, 14, 130]],
  },
  bananaSweep: {
    name: "Banana Sweep", total: 32, base: "crouch", combo: true,
    anim: [[0, {}], [4, { hy: 20, tl: 30, bl: [30, 80], fl: { x: 10, y: 2 }, fa: { x: 10, y: -30 } }, "w"],
      [8, { hy: 18, tl: 36, fa: { x: 12, y: -34 }, ba: { x: 2, y: 2 }, bl: { x: 48, y: -14, r: "h" }, bf: 92, fl: { x: 6, y: 2 } }],
      [12, { hy: 18, tl: 36, fa: { x: 12, y: -34 }, ba: { x: 2, y: 2 }, bl: { x: 48, y: -14, r: "h" }, bf: 92, fl: { x: 6, y: 2 } }],
      [18, { hy: 20, tl: 30, bl: { x: -8, y: 2 }, fl: { x: 10, y: 2 } }, "f"], [32, {}]],
    hits: [{ from: 8, to: 11, tip: "bT", r: 7.5, dmg: 8, level: "low", hitstun: 18, blockstun: 12, push: 80, hitstop: 6, snd: "hit", launch: { vx: 60, vy: 300 }, kd: true }],
    vel: [[2, 9, 110]],
  },
  // ---- mix-up enders: P then K after a jab. Each fighter has a LOW one or an overhead
  rootSweep: {
    name: "Root Sweep", total: 30, base: "crouch", combo: true,
    anim: [[0, {}], [3, { hy: 22, tl: 30, fl: [30, 80], bl: { x: -12, y: 2 }, fa: { x: 12, y: -24 } }, "w"],
      [7, { hy: 17, tl: 38, fa: { x: 12, y: -34 }, ba: { x: 4, y: 0 }, fl: { x: 46, y: -14, r: "h" }, ff: 92, bl: { x: -10, y: 2 } }],
      [11, { hy: 17, tl: 38, fa: { x: 12, y: -34 }, ba: { x: 4, y: 0 }, fl: { x: 46, y: -14, r: "h" }, ff: 92, bl: { x: -10, y: 2 } }],
      [17, { hy: 20, tl: 30, fl: { x: 12, y: 2 }, bl: { x: -12, y: 2 } }, "f"], [30, {}]],
    hits: [{ from: 7, to: 10, tip: "fT", r: 7.5, dmg: 8, level: "low", hitstun: 18, blockstun: 12, push: 90, hitstop: 6, snd: "hit", launch: { vx: 60, vy: 280 }, kd: true }],
    vel: [[1, 8, 120]],
  },
  gearGrind: {
    name: "Gear Grind", total: 34, base: "crouch", combo: true,
    anim: [[0, {}], [5, { hy: 24, tl: 24, fl: [40, 90], bl: { x: -12, y: 2 }, fa: { x: 10, y: -10 } }, "w"],
      [10, { hy: 20, tl: 30, fl: { x: 44, y: -16, r: "h" }, ff: { rel: 90 }, bl: { x: -12, y: 2 }, fa: { x: 12, y: -20 }, ba: { x: 4, y: -4 } }],
      [14, { hy: 20, tl: 30, fl: { x: 44, y: -16, r: "h" }, ff: { rel: 90 }, bl: { x: -12, y: 2 }, fa: { x: 12, y: -20 }, ba: { x: 4, y: -4 } }],
      [21, { hy: 22, tl: 26, fl: { x: 14, y: 2 } }, "f"], [34, {}]],
    hits: [{ from: 10, to: 13, tip: "fT", r: 8, dmg: 10, level: "low", hitstun: 20, blockstun: 14, push: 160, hitstop: 8, snd: "heavy", shake: 1, launch: { vx: 80, vy: 300 }, kd: true }],
    vel: [[2, 10, 110]],
  },
  plieSweep: {
    name: "Plie Sweep", total: 28, base: "crouch", combo: true,
    anim: [[0, {}], [3, { hy: 24, tl: 24, fa: [100, 20], ba: [60, 30] }, "w"],
      [7, { hy: 18, tl: 34, fl: { x: 48, y: -14, r: "h" }, ff: 92, bl: { x: -8, y: 2 }, fa: [110, 20], ba: [70, 20] }],
      [10, { hy: 18, tl: 34, fl: { x: 48, y: -14, r: "h" }, ff: 92, bl: { x: -8, y: 2 }, fa: [110, 20], ba: [70, 20] }],
      [16, { hy: 22, tl: 26, fl: { x: 12, y: 2 } }, "f"], [28, {}]],
    hits: [{ from: 7, to: 9, tip: "fT", r: 7.5, dmg: 8, level: "low", hitstun: 18, blockstun: 11, push: 80, hitstop: 6, snd: "hit", launch: { vx: 60, vy: 300 }, kd: true }],
    vel: [[1, 8, 130]],
  },
  jesterDrop: {
    name: "Jester Drop", total: 34, base: "stance", combo: true,
    anim: [[0, {}], [5, { hy: 40, tl: -8, bl: { x: -8, y: 2 }, fl: [120, 60], fa: [140, 30], ba: [120, 30] }, "w"],
      [10, { hy: 52, tl: -14, fl: [160, 10], ff: { rel: 150 }, bl: { x: -6, y: 4 }, fa: [150, 20], ba: [130, 20] }],
      [14, { hy: 44, tl: 20, hd: 10, fl: { x: 40, y: 24, r: "h" }, ff: { rel: 120 }, bl: { x: -8, y: 2 }, fa: { x: 12, y: 4 }, ba: { x: 4, y: 4 } }],
      [18, { hy: 44, tl: 20, hd: 10, fl: { x: 40, y: 24, r: "h" }, ff: { rel: 120 }, bl: { x: -8, y: 2 }, fa: { x: 12, y: 4 }, ba: { x: 4, y: 4 } }],
      [25, { tl: 8, fl: { x: 14, y: 2 } }, "f"], [34, {}]],
    hits: [{ from: 13, to: 16, tip: "fT", r: 8, dmg: 9, level: "over", hitstun: 22, blockstun: 13, push: 180, hitstop: 8, snd: "heavy" }],
    vel: [[3, 13, 110]],
  },
};
const NORMAL_IDS = ["jab", "straight", "uppercut", "kickMid", "longKick", "roundhouse", "sweep", "airPunch", "airKick", "throw", "throwWhiff"];

// Push a key's pose further from (amt > 1) or closer to (amt < 1) the move's base pose.
// Only numbers, {x, y} targets and [angle, bend] pairs that the base also has are scaled.
function scaleSpec(base, over, amt) {
  const out = {};
  for (const k in over) {
    const v = over[k], b = base[k];
    if (typeof v === "number" && typeof b === "number") out[k] = b + (v - b) * amt;
    else if (typeof v === "number" && b === undefined && (k === "tl" || k === "hx" || k === "hd")) out[k] = v * amt;
    else if (v && b && typeof v === "object" && !Array.isArray(v) && !Array.isArray(b) && v.x !== undefined && b.x !== undefined && v.r === b.r)
      out[k] = Object.assign({}, v, { x: b.x + (v.x - b.x) * amt, y: b.y + (v.y - b.y) * amt });
    else if (Array.isArray(v) && Array.isArray(b)) out[k] = [b[0] + (v[0] - b[0]) * amt, b[1] + (v[1] - b[1]) * amt];
    else out[k] = v;
  }
  return out;
}

// Resolve every move for every character once: frames scaled, keyframes resolved.
function buildMoveSet(ch) {
  const set = {};
  const k = ch.stats.frame || 1;
  const sf = (f) => Math.max(0, Math.round(f * k));
  const ids = NORMAL_IDS.concat(ch.specials, ch.combos ? Object.values(ch.combos) : []);
  const style = ch.style || { windup: 1, follow: 1 };
  for (const id of ids) {
    const m = MOVES[id];
    if (!m) continue;
    const base = POSES[m.base] || STANCE;
    const styled = m.anim.some((k) => k[2]);
    // moves shared by everyone get a clip per fighter when the fighter's style changes them
    const clip = styled && NORMAL_IDS.includes(id) ? id + "_" + ch.id : id;
    const r = { id, clip, def: m, name: m.name, total: Math.max(2, sf(m.total)), keys: [] };
    for (const [f, over0, tag] of m.anim) {
      const amt = tag === "w" ? style.windup : tag === "f" ? style.follow : 1;
      const over = amt === 1 ? over0 : scaleSpec(base, over0, amt);
      const spec = Object.assign({}, base, over);
      if (m.autoAll || m.base === "air") spec.hy = null;
      const pose = resolvePose(spec, ch);
      r.keys.push([sf(f), pose, limbEnds(ch, pose)]);
    }
    r.hits = (m.hits || []).map((h) => Object.assign({}, h, { from: sf(h.from), to: sf(h.to), dmg: h.dmg * ch.stats.dmg }));
    r.vel = (m.vel || []).map(([a, b, vx, vy]) => [sf(a), sf(b), vx, vy]);
    if (m.projectile) r.projectile = Object.assign({}, m.projectile, { at: sf(m.projectile.at), dmg: m.projectile.dmg * ch.stats.dmg });
    if (m.invuln) r.invuln = [sf(m.invuln[0]), sf(m.invuln[1])];
    if (m.armor) r.armor = [sf(m.armor[0]), sf(m.armor[1])];
    if (m.jump) r.jump = Object.assign({}, m.jump, { at: sf(m.jump.at) });
    if (m.flip) r.flip = [sf(m.flip[0]), sf(m.flip[1]), m.flip[2]];
    if (m.teleport !== undefined) r.teleport = sf(m.teleport);
    if (m.release !== undefined) r.release = sf(m.release);
    if (m.victim) r.victim = m.victim.map(([f, dx, dy, rot]) => [sf(f), dx, dy, rot]);
    r.landLag = m.landLag || 0;
    r.cancel = !!m.cancel;
    r.chain = m.chain || [];
    r.air = !!m.air;
    r.special = !!m.special;
    r.combo = !!m.combo;
    set[id] = r;
  }
  return set;
}

// Hand and foot positions of a resolved pose: wrist relative to the shoulder, ankle relative
// to the hip, before whole-body rotation. s is the bend direction of the middle joint.
function limbEnds(ch, p) {
  const d = ch.dims;
  const end = (a, e, l1, l2) => ({ x: l1 * dX(a) + l2 * dX(a + e), y: l1 * dY(a) + l2 * dY(a + e), s: e >= 0 ? 1 : -1 });
  return [
    end(p[P_FA0], p[P_FA1], d.uarm, d.farm), end(p[P_BA0], p[P_BA1], d.uarm, d.farm),
    end(p[P_FL0], -p[P_FL1], d.thigh, d.shin), end(p[P_BL0], -p[P_BL1], d.thigh, d.shin),
  ];
}
/** @type {[number, number, string, string, number][]} */
const LIMB_IDX = [[P_FA0, P_FA1, "uarm", "farm", 1], [P_BA0, P_BA1, "uarm", "farm", 1], [P_FL0, P_FL1, "thigh", "shin", -1], [P_BL0, P_BL1, "thigh", "shin", -1]];

// Sample a keyframed move at frame t. Keys are joined with a smooth curve that keeps its
// speed through in-between keys (so a wind-up flows into the strike) but comes to rest on
// held and turning keys, and never overshoots. Body angles blend directly, while hands and
// feet travel between their key positions and the elbows and knees are solved again each
// frame, so a jab goes out in a line instead of swinging down and up.
function slopeAt(vp, v, vn, fp, f, fn) {
  if (vp === undefined || vn === undefined) return 0;
  const d0 = (v - vp) / Math.max(1, f - fp), d1 = (vn - v) / Math.max(1, fn - f);
  if (d0 * d1 <= 0) return 0;
  return 2 * d0 * d1 / (d0 + d1);
}
function hermite(v0, v1, m0, m1, h, u) {
  const u2 = u * u, u3 = u2 * u;
  return (2 * u3 - 3 * u2 + 1) * v0 + (u3 - 2 * u2 + u) * h * m0 + (-2 * u3 + 3 * u2) * v1 + (u3 - u2) * h * m1;
}
const ANGLE_SET = new Set(ANGLE_IDX);
function sampleKeys(keys, t, out, ch) {
  if (t <= keys[0][0]) return copyPose(keys[0][1], out);
  for (let i = 1; i < keys.length; i++) {
    const [f1, p1, e1] = keys[i];
    if (t <= f1) {
      const [f0, p0, e0] = keys[i - 1];
      const kp = keys[i - 2], kn = keys[i + 1];
      const h = Math.max(1e-6, f1 - f0), u = clamp((t - f0) / h, 0, 1);
      for (let c = 0; c < P_LEN; c++) {
        const w = ANGLE_SET.has(c);
        const v0 = p0[c], v1 = w ? v0 + wrap180(p1[c] - v0) : p1[c];
        const vp = kp ? (w ? v0 - wrap180(v0 - kp[1][c]) : kp[1][c]) : undefined;
        const vn = kn ? (w ? v1 + wrap180(kn[1][c] - v1) : kn[1][c]) : undefined;
        const m0 = slopeAt(vp, v0, v1, kp ? kp[0] : 0, f0, f1);
        const m1 = slopeAt(v0, v1, vn, f0, f1, kn ? kn[0] : 0);
        out[c] = hermite(v0, v1, m0, m1, h, u);
      }
      out[P_FLIP] = u < 1 ? p0[P_FLIP] : p1[P_FLIP];
      out[P_AUTO] = lerp(p0[P_AUTO], p1[P_AUTO], smooth01(u));
      if (ch && e0 && e1) {
        for (let L = 0; L < 4; L++) {
          const a = e0[L], b = e1[L];
          if (a.s !== b.s) continue;          // the joint flips over: keep the angle blend
          const ap = kp && kp[2] ? kp[2][L] : undefined, bn = kn && kn[2] ? kn[2][L] : undefined;
          const fp = kp ? kp[0] : 0, fn = kn ? kn[0] : 0;
          const tx = hermite(a.x, b.x, slopeAt(ap && ap.x, a.x, b.x, fp, f0, f1), slopeAt(a.x, b.x, bn && bn.x, f0, f1, fn), h, u);
          const ty = hermite(a.y, b.y, slopeAt(ap && ap.y, a.y, b.y, fp, f0, f1), slopeAt(a.y, b.y, bn && bn.y, f0, f1, fn), h, u);
          const [i0, i1, l1n, l2n, sign] = LIMB_IDX[L];
          const l1 = ch.dims[l1n], l2 = ch.dims[l2n];
          // pick the solution that bends the same way as the keys (rel = forearm - upper angle)
          let best = null;
          for (const bend of [-1, 1]) {
            const [g1, g2] = ik2(0, 0, tx, ty, l1, l2, bend);
            const rel = wrap180(g2 - g1);
            if ((rel >= 0 ? 1 : -1) === a.s || Math.abs(rel) < 0.5) { best = [g1, rel]; break; }
          }
          if (!best) continue;
          out[i0] = best[0]; out[i1] = sign > 0 ? best[1] : -best[1];
        }
      }
      return out;
    }
  }
  return copyPose(keys[keys.length - 1][1], out);
}

// Resolved static poses per character (cached).
function buildPoseSet(ch) {
  const out = {};
  for (const name in POSES) out[name] = resolvePose(POSES[name], ch);
  return out;
}
for (const ch of CHARACTERS) {
  ch.poses = buildPoseSet(ch);
  ch.moves = buildMoveSet(ch);
}
