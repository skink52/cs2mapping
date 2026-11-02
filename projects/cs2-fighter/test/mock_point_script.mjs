// Minimal stand-in for CS2's "cs_script/point_script" module, enough to run puppet_brawl.js
// headless: entities, templates, players with button state, custom cameras and a HUD layout.
export const CSInputs = { NONE: 0, FORWARD: 1, BACK: 2, LEFT: 4, RIGHT: 8, WALK: 16, DUCK: 32, JUMP: 64, USE: 128, ATTACK: 256, ATTACK2: 512, RELOAD: 1024, SHOW_SCORES: 2048, LOOK_AT_WEAPON: 4096 };
export const CSMoveType = { INVALID: -1, NONE: 0, WALK: 1, FLYGRAVITY: 2, VPHYSICS: 3, NOCLIP: 4, OBSERVER: 5, LADDER: 6, CUSTOM: 7 };
export const CSGearSlot = { INVALID: -1, RIFLE: 0, PISTOL: 1, KNIFE: 2, GRENADES: 3, C4: 4, BOOSTS: 5 };
export const CSWeaponType = { KNIFE: 0, PISTOL: 1, SUBMACHINEGUN: 2, RIFLE: 3 };
export const CustomCameraMode = { DISABLED: 0, CONTROLLED: 1, CONTROLLED_POSITION: 2, FOLLOW_POSITION: 3 };

export const stats = { teleports: 0, moves: 0, scale: 0, color: 0, spawned: 0, removed: 0, hudVar: 0, hudClass: 0, hudVarP: 0, hudClassP: 0, fired: [], say: [], cmds: [], errors: [], msgs: [], inputs: [] };
const ents = [];
let nextId = 1;
function finite(v, what) {
  for (const k of Object.keys(v || {})) if (typeof v[k] === "number" && !Number.isFinite(v[k])) { stats.errors.push(`${what}.${k} not finite`); }
}

export class Entity {
  constructor(name = "", cls = "info_target", pos = { x: 0, y: 0, z: 0 }, ang = { pitch: 0, yaw: 0, roll: 0 }) {
    this._id = nextId++; this._name = name; this._cls = cls; this._pos = { ...pos }; this._ang = { ...ang }; this._vel = { x: 0, y: 0, z: 0 };
    this._valid = true; this._parent = undefined; ents.push(this);
  }
  IsValid() { return this._valid; }
  GetAbsOrigin() { return { ...this._pos }; }
  GetAbsAngles() { return { ...this._ang }; }
  GetAbsVelocity() { return { ...this._vel }; }
  GetEntityName() { return this._name; }
  SetEntityName(n) { this._name = n; }
  GetClassName() { return this._cls; }
  GetParent() { return this._parent; }
  SetParent(p) { this._parent = p; }
  Teleport(v) { if (!this._valid) throw new Error("Teleport on removed entity"); stats.teleports++; if (v.position) { finite(v.position, "teleport.pos"); this._pos = { ...v.position }; } if (v.angles) { finite(v.angles, "teleport.ang"); this._ang = { ...v.angles }; } if (v.velocity) this._vel = { ...v.velocity }; }
  Move(v) { if (!this._valid) throw new Error("Move on removed entity"); stats.moves++; if (v.position) { finite(v.position, "move.pos"); this._pos = { ...v.position }; } if (v.angles) { finite(v.angles, "move.ang"); this._ang = { ...v.angles }; } }
  Remove() { this._valid = false; stats.removed++; }
  Kill() { this.Remove(); }
  GetHealth() { return 100; }
  IsAlive() { return this._valid; }
}
export class BaseModelEntity extends Entity {
  constructor(...a) { super(...a); this._scale = 1; this._model = ""; this._color = { r: 255, g: 255, b: 255, a: 255 }; this._glow = false; }
  SetModel(m) { this._model = m; }
  GetModelName() { return this._model; }
  SetModelScale(s) { if (!Number.isFinite(s) || s <= 0) stats.errors.push("bad scale " + s); stats.scale++; this._scale = s; }
  GetModelScale() { return this._scale; }
  SetColor(c) { finite(c, "color"); stats.color++; this._color = { a: 255, ...c }; }
  GetColor() { return this._color; }
  Glow(c) { this._glow = true; }
  Unglow() { this._glow = false; }
  IsGlowing() { return this._glow; }
}
export class PointTemplate extends Entity {
  // model: one model path, or a list where every entry after the first is parented to the first
  constructor(name, model, pos) { super(name, "point_template", pos); this._models = Array.isArray(model) ? model : [model]; }
  ForceSpawn(origin, angles) {
    const out = [];
    if (origin) finite(origin, "spawn.pos");
    for (const m of this._models) {
      stats.spawned++;
      if (m.startsWith("particle:")) { const e = new Entity(this._name + "_spawn", "info_particle_system", origin || this._pos, angles); e._effect = m.slice(9); out.push(e); continue; }
      const e = new BaseModelEntity(this._name + "_spawn", "prop_dynamic", origin || this._pos);
      e._model = m;
      if (out.length) e._parent = out[0];
      out.push(e);
    }
    return out;
  }
}
export class CustomPlayerCamera extends Entity {
  constructor(pawn) { super("", "custom_camera", pawn._pos); this._mode = 0; this._pawn = pawn; this._parent = pawn; }
  GetPlayer() { return this._pawn; }
  GetMode() { return this._mode; }
  SetMode(m) { this._mode = m; }
  SetFollowConfig() {}
}
export class CSWeaponBase extends BaseModelEntity {
  constructor(cls, type, slot) { super("", cls); this._type = type; this._slot = slot; }
  GetData() { const t = this._type; return { GetType: () => t, GetName: () => this._cls }; }
}
export class CSPlayerController extends Entity {
  constructor(slot, name) { super("", "cs_player_controller"); this._slot = slot; this._pname = name; this._connected = true; this._bot = false; this._pawn = null; }
  GetPlayerSlot() { return this._slot; }
  GetPlayerName() { return this._pname; }
  GetPlayerPawn() { return this._pawn || undefined; }
  IsConnected() { return this._connected; }
  IsBot() { return this._bot; }
}
export class CSPlayerPawn extends BaseModelEntity {
  constructor(ctrl, pos) {
    super("", "player", pos);
    this._ctrl = ctrl; this._held = 0; this._just = 0; this._moveType = CSMoveType.WALK; this._alive = true; this._cam = null;
    this._weapons = [new CSWeaponBase("weapon_knife", CSWeaponType.KNIFE, CSGearSlot.KNIFE), new CSWeaponBase("weapon_ak47", CSWeaponType.RIFLE, CSGearSlot.RIFLE)];
    this._active = this._weapons[1];
  }
  GetPlayerController() { return this._ctrl; }
  GetOriginalPlayerController() { return this._ctrl; }
  IsInputPressed(b) { return (this._held & b) === b && b !== 0; }
  WasInputJustPressed(b) { return (this._just & b) === b && b !== 0; }
  WasInputJustReleased() { return false; }
  SetMoveType(t) { this._moveType = t; }
  GetMoveType() { return this._moveType; }
  IsAlive() { return this._alive && this._valid; }
  SetEyeAngles(a) { finite(a, "eye"); }
  GetCustomCamera() { if (!this._cam) this._cam = new CustomPlayerCamera(this); return this._cam; }
  GetActiveWeapon() { return this._active; }
  FindWeaponBySlot(s) { return this._weapons.find((w) => w._slot === s); }
  SwitchToWeapon(w) { this._active = w; }
  DestroyWeapons() { this._weapons = []; this._active = undefined; }
  GiveNamedItem(n) { this._weapons.push(new CSWeaponBase(n, n.includes("knife") ? 0 : 3, n.includes("knife") ? 2 : 0)); }
  // test helper: press(bits) for one tick on top of held
  press(bits) { this._just |= bits; this._held |= bits; }
}
export class CustomHudLayout extends Entity {
  constructor(name) { super(name, "custom_hud_layout"); this.classes = new Map(); this.vars = new Map(); this.pclasses = new Map(); this.pvars = new Map(); }
  SetHasClass(id, c, on) { stats.hudClass++; this.classes.set(id + "." + c, on); }
  SetHasClassForPlayer(slot, id, c, on) { stats.hudClassP++; this.pclasses.set(slot + ":" + id + "." + c, on); }
  SetDialogVariableString(id, v, val) { stats.hudVar++; if (typeof val !== "string") stats.errors.push("hud var not string " + id); this.vars.set(id + "." + v, val); }
  SetDialogVariableStringForPlayer(slot, id, v, val) { stats.hudVarP++; this.pvars.set(slot + ":" + id + "." + v, val); }
  SetInputCaptureEnabled() {}
  IsInputCaptureEnabled() { return false; }
  Reset() { this.classes.clear(); this.vars.clear(); this.pclasses.clear(); this.pvars.clear(); }
  ResetForPlayer(slot) { for (const k of [...this.pclasses.keys()]) if (k.startsWith(slot + ":")) this.pclasses.delete(k); for (const k of [...this.pvars.keys()]) if (k.startsWith(slot + ":")) this.pvars.delete(k); }
}

const hooks = {};
let think = null, nextThink = Infinity, time = 0;
const controllers = [];
const scriptInputs = {};
const cheats = {};
const delays = [];
function on(name) { return (cb) => { (hooks[name] ||= []).push(cb); }; }
export const Instance = {
  Msg: (t) => { stats.msgs.push(String(t)); if (process.env.PB_VERBOSE) console.log(String(t)); },
  DebugScreenText() {}, DebugLine() {}, DebugSphere() {}, DebugBox() {},
  SetThink: (cb) => { think = cb; },
  SetNextThink: (t) => { nextThink = t; },
  GetGameTime: () => time,
  Delay: (s) => new Promise((res) => delays.push({ at: time + s, res })),
  OnActivate: on("activate"), OnScriptReload: (cfg) => { hooks.reload = cfg; },
  OnRoundStart: on("roundStart"), OnBeginRoundRestart: on("beginRoundRestart"), OnRoundEnd: on("roundEnd"),
  OnPlayerDisconnect: on("disconnect"), OnPlayerKill: on("kill"), OnPlayerReset: on("reset"), OnPlayerTeamChanged: on("team"),
  OnModifyPlayerDamage: on("modifyDamage"), OnPlayerConnect: on("connect"), OnPlayerActivate: on("pactivate"),
  OnScriptInput: (n, cb) => { scriptInputs[n] = cb; },
  RegisterCheatCommand: (n, cb) => { cheats[n] = cb; },
  FindEntityByName: (n) => ents.find((e) => e._valid && e._name === n),
  FindEntitiesByName: (n) => { if (n.endsWith("*")) { const p = n.slice(0, -1); return ents.filter((e) => e._valid && e._name.startsWith(p)); } return ents.filter((e) => e._valid && e._name === n); },
  FindEntityByClass: (c) => ents.find((e) => e._valid && e._cls === c),
  FindEntitiesByClass: (c) => ents.filter((e) => e._valid && e._cls === c),
  GetPlayerController: (slot) => controllers[slot],
  GetAllPlayerControllers: () => controllers.filter(Boolean),
  EntFireAtName: (cfg) => { stats.fired.push(cfg.name + ":" + cfg.input); if (cfg.input === "SetMessage") (stats.text ||= []).push(cfg.name + "=" + cfg.value); },
  EntFireAtTarget: (cfg) => { stats.inputs.push({ target: cfg.target, input: cfg.input, value: cfg.value }); },
  ServerCommand: (c) => { stats.cmds.push(c); if (c.startsWith("say ")) stats.say.push(c); },
  ClientCommand: () => {},
  ConnectOutput: () => 1, DisconnectOutput: () => {},
  IsWarmupPeriod: () => false, IsFreezePeriod: () => false, GetMapName: () => "test",
};

// ------------------------------------------------------------- test driver API
export const sim = {
  ents, hooks, scriptInputs, cheats, controllers,
  time: () => time,
  addPlayer(slot, name, pos) {
    const c = new CSPlayerController(slot, name);
    const p = new CSPlayerPawn(c, pos);
    c._pawn = p; controllers[slot] = c;
    return p;
  },
  respawn(slot, pos) {
    const c = controllers[slot]; c._pawn._valid = false;
    const p = new CSPlayerPawn(c, pos); c._pawn = p;
    for (const cb of hooks.reset || []) cb({ player: p });
    return p;
  },
  fire(name, ...args) { for (const cb of hooks[name] || []) cb(...args); },
  tick(n = 1) {
    for (let i = 0; i < n; i++) {
      time += 1 / 64;
      for (const d of delays.splice(0)) { if (d.at <= time) d.res(); else delays.push(d); }
      if (think && time >= nextThink - 1e-9) { nextThink = Infinity; think(); }
      for (const c of controllers) if (c && c._pawn) c._pawn._just = 0;
    }
  },
  async flush() { await new Promise((r) => setTimeout(r, 0)); },
};
