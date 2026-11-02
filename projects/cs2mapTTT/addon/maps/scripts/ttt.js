// ttt.js: Trouble in Terrorist Town for any CS2 map, one cs_script. AI-generated (Claude), MIT. github.com/skink52/cs2mapTTT
import { Instance, CSPlayerPawn, CSPlayerController, CustomHudLayout, PointTemplate, BaseModelEntity, CSGearSlot, CSWeaponType, CSInputs,
         CSDamageFlags, CSDamageTypes, CSRoundEndReason, CSMoveType } from "cs_script/point_script";

const CONFIG = {
    APPLY_CVARS: true,
    PREP_TIME: 25,
    ROUND_TIME: 360,
    HASTE_START: 210,
    HASTE_PER_DEATH: 20,
    POST_TIME: 8,
    MIN_PLAYERS: 3,
    TRAITOR_RATIO: 0.25,
    DETECTIVE_MIN_PLAYERS: 8,
    DETECTIVE_RATIO: 0.125,
    HIDE_KILLER: true,
    TRY_HIDE_KILLFEED: false,
    HUD_IN_KILLFEED: true,
    SCOREBOARD: true,             // Tab shows the TTT scoreboard over CS2's: the dead stay listed as alive until their body is found
    COVER_TOPBAR: true,           // cover CS2's top bar (alive avatars, clock) with the TTT clock
    HIDE_NATIVE_HUD: false,       // true: no CS2 HUD at all (SetHUDVisibility; also blocks weapon switching and chat, so tap F cycles weapons, Ctrl+F opens chat)
    SHOP_HOLD: 0.45,              // hold F this long for the shop (traitor / detective)
    HIDE_ONLY_ALIVE_ACTIVE: true, // CS2's HUD (chat box, weapon wheel) comes back in prep, after the round and for the dead
    CHAT_HUD_TIME: 15,            // Ctrl+F: CS2's HUD back for this long, to type in chat
    CHAT_LINES: 5, CHAT_KEEP: 14, // chat shown on the TTT HUD while CS2's is hidden
    GIVE_PRIMARY: "auto",
    MAP_WEAPONS_ENOUGH: 10,
    BUTTON_CONE: 0.97,
    PRIMARIES: ["weapon_ak47", "weapon_m4a1", "weapon_famas", "weapon_galilar", "weapon_mp7", "weapon_ump45", "weapon_mac10",
                "weapon_mp9", "weapon_p90", "weapon_nova", "weapon_xm1014", "weapon_ssg08"],
    BODY_RANGE: 110,
    BODY_CONE: 0.8,
    DNA_TIME: 45,
    RADAR_TIME: 60,
    KARMA_START: 1000, KARMA_MAX: 1000, KARMA_MIN_MULT: 0.4,
    KARMA_HURT: 0.5, KARMA_KILL: 60, KARMA_GOOD_KILL: 15, KARMA_CLEAN_ROUND: 30, KARMA_ROUND_REGEN: 5,
    // karma lives for the map session (a script can't keep data across maps); kept by player name over reconnects. Changes during a round
    // apply at the next round start (scoreboard, HUD, damage), so they leak nothing about who was hit.
    TRAITOR_CREDITS: 2, DETECTIVE_CREDITS: 1, CREDIT_EVERY_N_DEATHS: 3,
    SHOP_CURSOR: false,
    SHOP_TIMEOUT: 20,
    F_CYCLE: true,                // tap F = next weapon while CS2's HUD is hidden
    CHAT_ANNOUNCE: true,
    NOHUD_TRAITOR_ITEM: "weapon_decoy",
    DETECTIVE_TINT: { r: 120, g: 160, b: 255, a: 255 },
    HUD_NAME: "ttt_hud",
    HUD_BUDGET: 600,
    CARRY: true,
    CARRY_CLASSES: ["prop_physics", "prop_physics_multiplayer", "prop_physics_override", "func_physbox"],
    CARRY_RANGE: 110, CARRY_AIM_RADIUS: 28, CARRY_HOLD_TIME: 0.35, CARRY_DIST: 70, CARRY_GAIN: 12, CARRY_MAX_SPEED: 900, CARRY_BREAK_DIST: 200, CARRY_THROW: 550,
    BODY_TEMPLATE: "ttt_body_tpl",       // CT body (agents/models/ctm_sas); also the fallback
    BODY_TEMPLATE_T: "ttt_body_tpl_t",   // T body (agents/models/tm_phoenix)
    BODY_MAX: 48,
    BODY_SET_MODEL: false,        // crash risk, see spawnBody
    CARRY_BODIES: true,           // the 29 Oct crash was a one-bone placeholder model + SetModel; set false if carrying a body ever crashes
    HIDE_CLIENT_RAGDOLL: true,
};

const SHOP = {
    2: [
        { id: "armor", name: "Kevlar + helmet", cost: 1 },
        { id: "knife", name: "Assassin knife (one hit)", cost: 1 },
        { id: "m4s", name: "Silenced M4A1-S", cost: 1 },
        { id: "radar", name: "Radar (" + CONFIG.RADAR_TIME + "s)", cost: 1 },
        { id: "nades", name: "HE + Molotov", cost: 1 },
        { id: "heal", name: "2 x Healthshot", cost: 1 },
        { id: "awp", name: "AWP", cost: 2 },
    ],
    3: [
        { id: "armor", name: "Kevlar + helmet", cost: 1 },
        { id: "heal", name: "2 x Healthshot", cost: 1 },
        { id: "taser", name: "Zeus x27", cost: 1 },
        { id: "radar", name: "Radar (" + CONFIG.RADAR_TIME + "s)", cost: 1 },
        { id: "util", name: "Smoke + Flash", cost: 1 },
    ],
};
const SHOP_ROWS = 7;
const RULES = "Rules: no random killing, only kill with a reason (you saw it, they shot you, KOS with proof). KOS calls need a reason. "
    + "The dead don't help the living (no ghosting). Don't use the Esc scoreboard. Traitors don't kill traitors; nobody kills the detective. "
    + "Shooting your own side costs karma and damage.";

// MAP_DATA_BEGIN (tools/build_data.py writes this from maps/*.json; edit those, not this block)
const MAP_DATA = {"ttt_cg_skyscraper_2017":{"buttons":[],"checks":{},"roles":{},"texts":{},"owners":{},"credits":{},"wins":0,"settings":0,"ptouch":{},"alphas":[0,35,70,140,170,225],"duck":0},"ttt_minecraft":{"buttons":[{"id":"ttt_auto_2","pos":[-248.0,16.0,88.0],"desc":"Transforms the water in lava, Single use.","once":true,"wait":0.0,"range":1024.0,"off":false},{"id":"ttt_auto_3","pos":[-960.0,96.0,-5272.0],"desc":"Use this to destroy the little nether island. (with the glowstone)","once":true,"wait":0.0,"range":1024.0,"off":false},{"id":"Ttest_T1_Button","pos":[768.0,-512.0,512.0],"desc":"Destroys the glass floor.","once":true,"wait":0.0,"range":1024.0,"off":false},{"id":"Ttest_T2_Button","pos":[592.0,-560.0,456.0],"desc":"Break dungeon glass","once":false,"wait":0.0,"range":1024.0,"off":false},{"id":"ttt_auto_4","pos":[528.0,-448.0,640.0],"desc":"Sabotage the tester and make indicator red.","once":true,"wait":0.0,"range":1024.0,"off":false}],"checks":{"T1_Check":{"mins":[-970.0,-288.0,32.0],"maxs":[-954.0,-252.0,112.0],"on":true},"T_Cheat_Check":{"mins":[-928.0,-384.0,32.0],"maxs":[-768.0,-160.0,288.0],"on":true},"Portal_Check":{"mins":[0.0,672.0,416.0],"maxs":[64.0,688.0,512.0],"on":true},"Ttest_check":{"mins":[480.0,-480.0,576.0],"maxs":[520.0,-416.0,672.0],"on":false},"T2_Check":{"mins":[-1984.0,820.0,-228.0],"maxs":[-1920.0,840.0,-164.0],"on":true}},"roles":{"T1_logic":"any","Ttest_logic":"tra","T1_logic2":"tra","T_Cheat_Logic":"tra","Ttest_check_any":"any","Portal_Logic":"tra","Ttest_check_detect":"det","T2_Role":"tra"},"texts":{"Start_Text_1":{"msg":"","rcv":1},"Start_Text_2":{"msg":"","rcv":1},"Cave_Text":{"msg":"Crowbar the iron ore!","rcv":0},"Start_Text_T":{"msg":"The traitor room is now available!","rcv":1},"Ttest_Text":{"msg":"Traitor tester is now available!","rcv":1},"Cave2_Text":{"msg":"Crowbar the iron ore!","rcv":0},"T2_Text_Decoy":{"msg":"You've got a Decoy!","rcv":0},"T2_Text_Radio":{"msg":"You've got a Radio!","rcv":0},"T2_Text_Knife":{"msg":"You've got a Knife!","rcv":0},"T2_Text_Tele":{"msg":"You've got a Teleporter!","rcv":0},"T2_Text_Pistol":{"msg":"You've got a Silenced Pistol!","rcv":0},"T2_Text_Flare":{"msg":"You've got a Flaregun!","rcv":0}},"owners":{"T1_Creeper_Owner":{"damager":"Trap_Creeper_Explosion","name":"the TNT minecart"},"Trap_Lava_Owner":{"damager":"Trap_Lava_Hurt","name":"the lava pool"},"Trap_Nether_Owner":{"damager":"Trap_Nether_Hurt","name":"the island as a trap"},"Trap_Portal_Owner":{"damager":"Trap_Portal_Hurt","name":"False nether portal"},"Ttest_Owner":{"damager":"Ttest_Hurt","name":"the traitor tester"},"Ttest_T1_Owner":{"damager":"Ttest_T1_Hurt","name":"glass floor fall"},"Ttest_T3_Owner":{"damager":"Ttest_Hurt","name":"the sabotaged tester"},"Ttest_T2_Owner":{"damager":"Ttest_T2_Hurt","name":"dungeon trap"}},"credits":{"T2_Credits":1},"wins":1,"settings":1,"ptouch":{"ttt_pt_1":{"ent":"minecart","mins":[-1796.0,480.0,128.0],"maxs":[-1792.0,544.0,224.0],"half":[20.0,20.0,10.0],"off":[0.0,0.0,0.0]},"ttt_pt_2":{"ent":"minecart","mins":[-2016.0,544.0,960.0],"maxs":[-1952.0,640.0,992.0],"half":[20.0,20.0,10.0],"off":[0.0,0.0,0.0]},"Ttest_CraftTrigger":{"ent":"GoldBlock","mins":[576.0,-448.0,608.0],"maxs":[608.0,-416.0,612.0],"half":[8.0,8.0,8.0],"off":[0.0,0.0,8.0]},"ttt_pt_3":{"ent":"minecart","mins":[480.0,-640.0,608.0],"maxs":[544.0,-624.0,672.0],"half":[20.0,20.0,10.0],"off":[0.0,0.0,0.0]},"ttt_pt_4":{"ent":"minecart","mins":[608.0,-640.0,608.0],"maxs":[672.0,-624.0,672.0],"half":[20.0,20.0,10.0],"off":[0.0,0.0,0.0]},"ttt_pt_5":{"ent":"DiaBlock","mins":[-1824.0,576.0,736.0],"maxs":[-1792.0,608.0,740.0],"half":[8.0,8.0,8.0],"off":[0.0,0.0,0.0]},"Pigman_Furnace_Trigger":{"ent":"Clay","mins":[-1248.0,-640.0,-5344.0],"maxs":[-1216.0,-636.0,-5312.0],"half":[8.0,8.0,8.0],"off":[0.0,0.0,0.0]},"ttt_pt_6":{"ent":"minecart","mins":[16.0,632.0,496.0],"maxs":[48.0,664.0,576.0],"half":[20.0,20.0,10.0],"off":[0.0,0.0,0.0]}},"alphas":[],"duck":1}};
// MAP_DATA_END

const R_NONE = 0, R_INN = 1, R_TRA = 2, R_DET = 3;
const ROLE_NAME = ["", "INNOCENT", "TRAITOR", "DETECTIVE"];
const ROLE_CLS = ["", "stInn", "stTra", "stDet"];
const P_WAIT = 0, P_PREP = 1, P_ACTIVE = 2, P_POST = 3;
const DIRS = ["ahead", "ahead-left", "left", "behind-left", "behind", "behind-right", "right", "ahead-right"];

class PState {
    constructor(slot) {
        this.slot = slot;
        this.role = R_NONE;
        this.karma = CONFIG.KARMA_START;
        this.karmaBase = CONFIG.KARMA_START;
        this.cleanRound = true;
        this.credits = 0;
        this.knife = false;
        this.radarUntil = 0;
        this.trackSlot = -1;
        this.trackUntil = 0;
        this.shopOpen = false;
        this.shopSel = 0;
        this.shopAt = 0;
        this.fDownAt = -1;
        this.fUsed = false;
        this.prevKeys = 0;
        this.frozen = false;
        this.msg = "";
        this.msgUntil = 0;
        this.lastHit = null;
        this.pendingKill = false;
        this.name = "";
        this.hud = new Map();
        this.loadoutAt = 0;
        this.ctrl = null;
        this.hold = null;
        this.holdStall = 0;
        this.alpha = 255;
        this.duckUntil = 0;
        this.useAt = -1;
        this.grabTried = false;
        this.bodyPend = false;
        this.pendingAttacker = undefined;
        this.deathModel = "";
        this.scaled = false;
        this.scoreDelta = 0;
        this.nativeAt = 0;
        this.nativeHidden = null;
        this.chatHudUntil = 0;
        this.radarText = "";
        this.confirmed = false;
        this.sbAt = 0;
    }
}

let players = new Map();
let phase = P_WAIT;
let phaseEnd = 0;
let roundEnded = false;
let endFallbackAt = 0;
let bodies = [];
let killQueue = [];
let deathsSinceCredit = 0;
let globalMsg = "";
let globalMsgUntil = 0;
let tick = 0;
let now = 0;
let hud = undefined;
let hudFails = 0;
let hudBudget = 0;
let killing = false;
let lastStatus = "";
let thinkStarted = false;
let activeCap = 0;
let waitAnnounced = "";
let waitAnnouncedAt = -100;

const st = (slot) => { let p = players.get(slot); if (!p) { p = new PState(slot); players.set(slot, p); } return p; };
const clean = (s, n = 40) => String(s).replace(/[;"\\\n\r]/g, "").slice(0, n);
const mmss = (s) => { s = Math.max(0, Math.ceil(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
const say = (t) => { if (CONFIG.CHAT_ANNOUNCE) Instance.ServerCommand("say " + clean(t, 120)); };
const log = (t) => Instance.Msg("[ttt] " + t);

function toPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function slotOf(ent) {
    try {
        if (ent instanceof CSPlayerController) return ent.GetPlayerSlot();
        if (ent instanceof CSPlayerPawn) { const c = ent.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; }
    } catch (e) { }
    return -1;
}
function pawnOf(slot) {
    const c = Instance.GetPlayerController(slot);
    if (!c) return undefined;
    const p = c.GetPlayerPawn();
    return p && p.IsValid() ? p : undefined;
}
function liveControllers() {
    const out = [];
    for (const c of Instance.GetAllPlayerControllers()) {
        try { if (c && c.IsValid() && c.IsConnected()) out.push(c); } catch (e) { }
    }
    return out;
}
function isAlive(slot) { const p = pawnOf(slot); return !!p && p.IsAlive(); }
function side(role) { return role === R_TRA ? 2 : (role === R_INN || role === R_DET) ? 1 : 0; }

function applyCvars(respawn) {
    if (!CONFIG.APPLY_CVARS) return;
    Instance.ServerCommand([
        "mp_teammates_are_enemies 1", "mp_friendlyfire 1", "mp_autokick 0", "mp_respawn_immunitytime 0", "mp_freezetime 0",
        "mp_ignore_round_win_conditions 1", "mp_roundtime 15", "mp_round_restart_delay " + CONFIG.POST_TIME, "mp_give_player_c4 0",
        "mp_buy_anywhere 0", "mp_buytime 0", "mp_startmoney 0", "mp_maxmoney 0", "mp_afterroundmoney 0", "mp_playercashawards 0",
        "mp_teamcashawards 0", "mp_free_armor 0", "sv_disable_radar 1", "mp_solid_teammates 1", "mp_death_drop_gun 1",
        "sv_alltalk 0", "sv_deadtalk 0", "sv_talk_enemy_dead 0", "sv_talk_enemy_living 1", "mp_halftime 0",
        "mp_respawn_on_death_t " + (respawn ? 1 : 0), "mp_respawn_on_death_ct " + (respawn ? 1 : 0),
    ].join(";"));
}

// ------------------------------------------------------------------ HUD
function findHud() {
    if (hudFails > 5) return undefined;
    if (hud && hud.IsValid()) return hud;
    hud = undefined;
    const e = Instance.FindEntityByName(CONFIG.HUD_NAME);
    if (e instanceof CustomHudLayout) hud = e;
    else for (const h of Instance.FindEntitiesByClass("custom_hud_layout")) if (h instanceof CustomHudLayout) { hud = h; break; }
    if (hud) for (const p of players.values()) p.hud.clear();
    return hud;
}
function hudVar(p, panel, v, value) {
    const k = panel + "." + v;
    if (p.hud.get(k) === value || hudBudget <= 0) return;
    try { hud.SetDialogVariableStringForPlayer(p.slot, panel, v, value); p.hud.set(k, value); hudBudget--; }
    catch (e) { hudFails++; log("hud var failed " + e); }
}
function hudCls(p, panel, cls, on) {
    const k = panel + "#" + cls;
    if (p.hud.get(k) === on || hudBudget <= 0) return;
    try { hud.SetHasClassForPlayer(p.slot, panel, cls, on); p.hud.set(k, on); hudBudget--; }
    catch (e) { hudFails++; log("hud class failed " + e); }
}
function resetHud(slot) {
    const p = players.get(slot);
    if (p) p.hud.clear();
    if (findHud()) try { hud.ResetForPlayer(slot); } catch (e) { }
}

function dirText(from, yaw, to) {
    const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) * 0.0254;
    let rel = Math.atan2(dy, dx) * 180 / Math.PI - yaw;
    rel = ((rel % 360) + 540) % 360 - 180;
    const d = DIRS[((Math.round(rel / 45) % 8) + 8) % 8];
    const v = dz > 150 ? ", above" : dz < -150 ? ", below" : "";
    return Math.round(dist) + "m " + d + v;
}

function drawHud(p, c) {
    const pawn = c.GetPlayerPawn();
    const alive = !!pawn && pawn.IsValid() && pawn.IsAlive();
    hudCls(p, "Ttt", "stOn", true);
    hudCls(p, "Ttt", "stKF", CONFIG.HUD_IN_KILLFEED);
    hudCls(p, "Ttt", "stNoNat", p.nativeHidden === true && alive);
    hudVar(p, "Chat", "chat", p.nativeHidden === true ? chatText(p) : "");
    if (p.nativeHidden === true && alive) {
        hudVar(p, "Hp", "hp", String(Math.max(0, Math.round(pawn.GetHealth()))));
        hudVar(p, "Ar", "ar", pawn.GetArmor() > 0 ? String(Math.round(pawn.GetArmor())) : "");
        let ammo = "";
        const w = pawn.GetActiveWeapon();
        if (w) {
            let t = -1;
            try { t = w.GetData().GetType(); } catch (e) { }
            ammo = t === CSWeaponType.KNIFE || t === CSWeaponType.GRENADE || t === CSWeaponType.STACKABLEITEM || t === CSWeaponType.EQUIPMENT || t < 0
                ? weaponName(w) : w.GetClipAmmo() + " / " + w.GetReserveAmmo();
        }
        hudVar(p, "Ammo", "ammo", ammo);
        hudCls(p, "Cross", "stScope", pawn.IsScoped());
    }
    let roleCls = "stSpec", role = "SPECTATING", sub = "", info = "", track = "";
    const left = phaseEnd - now;
    if (phase === P_WAIT) { roleCls = "stWait"; role = Instance.IsWarmupPeriod() ? "WARMUP" : "WAITING"; sub = "TTT starts next round"; }
    else if (phase === P_PREP) { roleCls = "stPrep"; role = "PREPARING"; sub = "Roles in " + mmss(left); }
    else {
        if (alive && p.role) { roleCls = ROLE_CLS[p.role]; role = ROLE_NAME[p.role]; }
        sub = phase === P_POST ? "Round over" : (p.role === R_TRA || !alive ? "Time " + mmss(left) : "Haste " + mmss(left));
    }
    if (phase >= P_ACTIVE) {
        if (alive && p.role === R_TRA) info = "Traitors: " + traitorNames(p.slot) + "\nCredits " + p.credits;
        else if (alive && p.role === R_DET) info = "Credits " + p.credits + "   Tap E on a body: inspect / DNA";
        else if (!alive) info = "Traitors: " + traitorNames(-1);
    }
    if (alive) info += (info ? (p.role === R_TRA ? "   " : "\n") : "") + "Karma " + Math.round(p.karmaBase);
    if (alive && p.trackSlot >= 0 && now < p.trackUntil) {
        const t = pawnOf(p.trackSlot);
        if (t && t.IsAlive()) track = "DNA: " + dirText(pawn.GetAbsOrigin(), pawn.GetEyeAngles().yaw, t.GetAbsOrigin()) + " (" + Math.ceil(p.trackUntil - now) + "s)";
        else p.trackUntil = 0;
    }
    if (alive && now < p.radarUntil && (!p.radarText || (tick + p.slot) % 32 === 0)) p.radarText = radarText(p, pawn);
    if (alive && now < p.radarUntil) track += (track ? "\n" : "") + (p.radarText || "");
    for (const k of ROLE_CLS.concat(["stSpec", "stWait", "stPrep"])) if (k) hudCls(p, "Ttt", k, k === roleCls);
    const K = CONFIG.HUD_IN_KILLFEED ? "K" : "";
    hudVar(p, K + "Role", "role", role);
    hudVar(p, K + "Sub", "sub", sub);
    hudVar(p, K + "Info", "info", info);
    hudVar(p, K + "Track", "track", track);
    hudVar(p, "MsgA", "msga", now < globalMsgUntil ? globalMsg : "");
    hudVar(p, "MsgB", "msgb", now < p.msgUntil ? p.msg : "");
    hudCls(p, "Ttt", "stTop", CONFIG.COVER_TOPBAR);
    if (CONFIG.COVER_TOPBAR) hudVar(p, "TopT", "t", phase === P_WAIT ? "WAITING" : phase === P_PREP ? "PREP " + mmss(left) : phase === P_POST ? "ROUND OVER" : (p.role === R_TRA || !alive ? "" : "HASTE ") + mmss(left));
    if (CONFIG.SCOREBOARD && (now >= p.sbAt || (alive && pawn.IsInputPressed(CSInputs.SHOW_SCORES)))) { p.sbAt = now + 1; drawBoard(p, alive); }
    const items = SHOP[p.role] || [];
    const open = p.shopOpen && alive;
    hudCls(p, "ShopBox", "stOpen", open);
    if (open) {
        hudVar(p, "ShopTitle", "title", ROLE_NAME[p.role] + " SHOP - credits " + p.credits);
        for (let i = 0; i < SHOP_ROWS; i++) {
            const it = items[i];
            hudVar(p, "ShopL" + i, "row", it ? it.name + "  [" + it.cost + "]" : "");
            hudCls(p, "Shop" + i, "stSel", !!it && i === p.shopSel);
            hudCls(p, "Shop" + i, "stOff", !it || it.cost > p.credits);
        }
    }
}
const SB_ROWS = 48, SB_HALF = 24, SB_KINDS = ["stH0", "stH1", "stH2", "stH3", "stDet", "stTra", "stMia", "stDead", "stSpec"];
let sbCache = { at: -1, views: [] };
function boardRows(view) {
    if (sbCache.at !== tick) sbCache = { at: tick, views: [] };
    if (sbCache.views[view]) return sbCache.views[view];
    const g = [[], [], [], []];
    const live = phase >= P_ACTIVE;
    for (const c of liveControllers()) {
        const slot = c.GetPlayerSlot(), q = players.get(slot);
        if (!q) continue;
        const team = c.GetTeamNumber(), al = isAlive(slot);
        const name = q.name || c.GetPlayerName() || "player";
        const role = live && q.role ? ROLE_NAME[q.role] : "";
        const row = { t: name, k: String(Math.round(q.karmaBase)), s: String(c.GetScore()), c: "", slot };
        if (live ? !q.role : team !== 2 && team !== 3) { row.c = "stSpec"; g[3].push(row); continue; }
        let gi = 0;
        if (!al && q.confirmed) { gi = 2; row.c = "stDead"; row.t += "  (" + role + ")"; }
        else if (!al && view === 2) { gi = 1; row.c = "stMia"; if (role) row.t += "  (" + role + ")"; }
        if (gi === 0 && live) {
            if (q.role === R_DET) row.c = "stDet";
            else if (q.role === R_TRA && view >= 1) row.c = "stTra";
        }
        g[gi].push(row);
    }
    const titles = ["Terrorists", "Missing in action", "Confirmed dead", "Spectators"];
    const rows = [];
    for (let i = 0; i < 4; i++) {
        if (i && !g[i].length) continue;
        g[i].sort((a, b) => a.t.toLowerCase() < b.t.toLowerCase() ? -1 : 1);
        rows.push({ t: titles[i] + "  (" + g[i].length + ")", k: i === 3 ? "" : "Karma", s: i === 3 ? "" : "Score", c: "stH" + i, slot: -1 });
        for (const r of g[i]) rows.push(r);
    }
    sbCache.views[view] = rows;
    return rows;
}
function drawBoard(p, alive) {
    const view = phase === P_POST || !alive ? 2 : p.role === R_TRA && phase >= P_ACTIVE ? 1 : 0;
    const rows = boardRows(view);
    hudCls(p, "Sb", "stOn", true);
    hudVar(p, "SbSub", "sub", Instance.GetMapName() + "   " + (phase === P_WAIT ? "waiting for players" : phase === P_PREP ? "preparing" : phase === P_POST ? "round over" : "round in progress"));
    hudCls(p, "Sb", "stTwo", rows.length > SB_HALF);
    for (let i = 0; i < SB_ROWS; i++) {
        let r = rows[i];
        if (i === SB_ROWS - 1 && rows.length > SB_ROWS) r = { t: "+" + (rows.length - SB_ROWS + 1) + " more", k: "", s: "", c: "stH3", slot: -1 };
        hudVar(p, "SbN" + i, "n", r ? r.t : "");
        hudVar(p, "SbK" + i, "k", r ? r.k : "");
        hudVar(p, "SbS" + i, "s", r ? r.s : "");
        for (const k of SB_KINDS) hudCls(p, "SbR" + i, k, !!r && r.c === k);
        hudCls(p, "SbR" + i, "stMe", !!r && r.slot === p.slot);
    }
}
function traitorNames(exceptSlot) {
    const n = [];
    for (const q of players.values()) if (q.role === R_TRA && q.slot !== exceptSlot) n.push(q.name + (isAlive(q.slot) ? "" : " (dead)"));
    return n.length ? n.join(", ") : "none";
}
function radarText(p, pawn) {
    const me = pawn.GetAbsOrigin(), yaw = pawn.GetEyeAngles().yaw, list = [];
    for (const q of players.values()) {
        if (q.slot === p.slot || !q.role || (p.role === R_TRA && q.role === R_TRA)) continue;
        const t = pawnOf(q.slot);
        if (!t || !t.IsAlive()) continue;
        const o = t.GetAbsOrigin();
        list.push({ d: (o.x - me.x) ** 2 + (o.y - me.y) ** 2 + (o.z - me.z) ** 2, o });
    }
    list.sort((a, b) => a.d - b.d);
    return "Radar " + Math.ceil(p.radarUntil - now) + "s: " + (list.slice(0, 3).map(e => dirText(me, yaw, e.o)).map((t, i) => (i === 2 ? "\n" : i ? ", " : "") + t).join("") || "nobody");
}
function wrap(text, n = 78) {
    if (text.length <= n) return text;
    const out = []; let line = "";
    for (const w of text.split(" ")) {
        if (line && line.length + 1 + w.length > n) { out.push(line); line = w; } else line = line ? line + " " + w : w;
    }
    if (line) out.push(line);
    return out.join("\n");
}
function tell(slot, text, secs = 6) {
    const p = st(slot); p.msg = wrap(text); p.msgUntil = now + secs;
    if (!findHud()) log("to " + p.name + ": " + text);
}
function announce(text, secs = 7) { globalMsg = wrap(text, 70); globalMsgUntil = now + secs; say(text); }

// ------------------------------------------------------------------ rounds
function onRoundStart() {
    roundEnded = false; endFallbackAt = 0; bodies = []; heldBy.clear(); killQueue = []; deathsSinceCredit = 0; globalMsgUntil = 0;
    for (const p of players.values()) {
        if (p.role) p.karma = Math.min(CONFIG.KARMA_MAX, p.karma + CONFIG.KARMA_ROUND_REGEN + (p.cleanRound ? CONFIG.KARMA_CLEAN_ROUND : 0));
        p.karmaBase = p.karma;
        p.scoreDelta = 0; p.confirmed = false; p.role = R_NONE; p.credits = 0; p.knife = false; p.radarUntil = 0; p.trackUntil = 0; p.trackSlot = -1; p.cleanRound = true;
        p.lastHit = null; p.pendingKill = false; closeShop(p); p.msgUntil = 0; p.hold = null;
    }
    if (Instance.IsWarmupPeriod()) { phase = P_WAIT; applyCvars(true); return; }
    phase = P_PREP; phaseEnd = now + CONFIG.PREP_TIME;
    mapRoundStart();
    applyCvars(true);
    Instance.SetRoundRemainingTime(CONFIG.PREP_TIME + CONFIG.ROUND_TIME + 20);
    for (const c of liveControllers()) { const p = st(c.GetPlayerSlot()); p.loadoutAt = now + 0.5; tint(c.GetPlayerPawn(), false); }
    announce("Preparing - roles are dealt in " + CONFIG.PREP_TIME + "s", 5);
}

function startActive() {
    const cands = [];
    for (const c of liveControllers()) {
        const pawn = c.GetPlayerPawn(), team = c.GetTeamNumber();
        if ((team === 2 || team === 3) && pawn && pawn.IsValid() && pawn.IsAlive()) cands.push(c);
    }
    if (cands.length < CONFIG.MIN_PLAYERS) {
        phaseEnd = now + 5;
        const w = cands.length + "/" + CONFIG.MIN_PLAYERS;
        if (w !== waitAnnounced || now - waitAnnouncedAt > 60) { waitAnnounced = w; waitAnnouncedAt = now; announce("Waiting for players (" + w + ")", 8); }
        else globalMsgUntil = now + 6;
        return;
    }
    for (let i = cands.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [cands[i], cands[j]] = [cands[j], cands[i]]; }
    const nT = Math.max(1, Math.floor(cands.length * CONFIG.TRAITOR_RATIO));
    const nD = cands.length >= CONFIG.DETECTIVE_MIN_PLAYERS ? Math.max(1, Math.floor(cands.length * CONFIG.DETECTIVE_RATIO)) : 0;
    const hasHud = !!findHud();
    cands.forEach((c, i) => {
        const p = st(c.GetPlayerSlot()); p.name = clean(c.GetPlayerName()); p.ctrl = c;
        p.role = i < nT ? R_TRA : i < nT + nD ? R_DET : R_INN;
        p.credits = p.role === R_TRA ? CONFIG.TRAITOR_CREDITS : p.role === R_DET ? CONFIG.DETECTIVE_CREDITS : 0;
        const pawn = c.GetPlayerPawn();
        if (p.role === R_DET) { tint(pawn, true); give(pawn, "weapon_taser"); }
        if (p.role === R_TRA && !hasHud && CONFIG.NOHUD_TRAITOR_ITEM) give(pawn, CONFIG.NOHUD_TRAITOR_ITEM);
        tell(p.slot, p.role === R_TRA ? "You are a TRAITOR. Kill the innocents. Hold F for the shop."
            : p.role === R_DET ? "You are the DETECTIVE. Find the traitors. Hold F for the shop."
            : "You are INNOCENT. Survive and find the traitors.", 8);
    });
    mapFire("start");
    phase = P_ACTIVE; activeCap = now + CONFIG.ROUND_TIME; phaseEnd = Math.min(activeCap, now + CONFIG.HASTE_START); waitAnnounced = "";
    applyCvars(false);
    Instance.SetRoundRemainingTime(phaseEnd - now + 20);
    const dets = cands.filter(c => st(c.GetPlayerSlot()).role === R_DET).map(c => st(c.GetPlayerSlot()).name);
    announce("Roles dealt: " + nT + " traitor" + (nT > 1 ? "s" : "") + (dets.length ? ". Detective: " + dets.join(", ") : ""), 7);
    if (!hasHud && CONFIG.NOHUD_TRAITOR_ITEM) say("No TTT HUD on this map: traitors were given a " + CONFIG.NOHUD_TRAITOR_ITEM.replace("weapon_", ""));
}

function checkWin() {
    if (phase !== P_ACTIVE || roundEnded) return;
    let inn = 0, tra = 0;
    for (const p of players.values()) {
        if (!p.role || p.pendingKill || !isAlive(p.slot)) continue;
        if (p.role === R_TRA) tra++; else inn++;
    }
    if (tra === 0) endRound(R_INN, "All traitors are dead");
    else if (inn === 0) endRound(R_TRA, "The traitors killed everyone");
    else if (now >= phaseEnd) endRound(R_INN, "Time ran out");
}

function endRound(winner, why) {
    roundEnded = true; phase = P_POST; phaseEnd = now + CONFIG.POST_TIME;
    mapFire("end");
    for (const p of players.values()) {
        closeShop(p);
        let d = p.scoreDelta + (p.role && side(p.role) === side(winner) && isAlive(p.slot) ? 1 : 0);
        p.scoreDelta = 0;
        if (d) { const c = Instance.GetPlayerController(p.slot); if (c) c.AddScore(d); }
    }
    announce((winner === R_TRA ? "TRAITORS WIN. " : "INNOCENTS WIN. ") + why + ". Traitors: " + traitorNames(-1), CONFIG.POST_TIME + 2);
    const reason = winner === R_TRA ? CSRoundEndReason.TERRORISTS_WIN : CSRoundEndReason.CTS_WIN;
    Instance.ServerCommand("mp_ignore_round_win_conditions 0;mp_default_team_winner_no_objective " + (winner === R_TRA ? 2 : 3));
    const imp = Instance.FindEntitiesByClass("info_map_parameters")[0];
    if (imp) Instance.EntFireAtTarget({ target: imp, input: "FireWinCondition", value: reason, delay: 0.1 });
    endFallbackAt = now + (imp ? 3 : 0.2);
}

// ------------------------------------------------------------------ players
function wantHidden(p) {
    if (!CONFIG.HIDE_NATIVE_HUD) return false;
    if (now < p.chatHudUntil) return false;
    return !CONFIG.HIDE_ONLY_ALIVE_ACTIVE || phase === P_ACTIVE;
}
function syncNativeHud(p, pawn) {
    if (!CONFIG.HIDE_NATIVE_HUD && p.nativeHidden === null) return;
    const h = wantHidden(p);
    if (p.nativeHidden === h) return;
    p.nativeHidden = h; nativeHud(pawn, !h); p.hud.delete("Ttt#stNoNat");
}
const chatLog = [];
function chatText(p) {
    const lines = chatLog.filter(m => now - m.t < CONFIG.CHAT_KEEP && (m.alive || !isAlive(p.slot) || phase !== P_ACTIVE));
    return lines.slice(-CONFIG.CHAT_LINES).map(m => m.name + ": " + m.text).join("\n");
}
function nativeHud(pawn, visible) {
    try { if (pawn && pawn.IsValid()) Instance.EntFireAtTarget({ target: pawn, input: "SetHUDVisibility", value: visible }); } catch (e) { }
}
function tint(pawn, det) {
    try { if (pawn && pawn.IsValid()) pawn.SetColor(det ? CONFIG.DETECTIVE_TINT : { r: 255, g: 255, b: 255, a: 255 }); } catch (e) { }
    const s = slotOf(pawn);
    if (s >= 0) st(s).alpha = 255;
}
function setAlpha(pawn, a) {
    const s = slotOf(pawn);
    if (s < 0 || !pawn.IsAlive()) return;
    st(s).alpha = a;
    const base = st(s).role === R_DET && phase === P_ACTIVE ? CONFIG.DETECTIVE_TINT : { r: 255, g: 255, b: 255 };
    try { pawn.SetColor({ r: base.r, g: base.g, b: base.b, a }); } catch (e) { }
    try { const w = pawn.GetActiveWeapon(); if (w) w.SetColor({ r: 255, g: 255, b: 255, a }); } catch (e) { }
}
function give(pawn, cls) {
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
    if (cls !== "weapon_healthshot" && pawn.FindWeapon(cls)) return;
    pawn.GiveNamedItem(cls, false);
}
function giveLoadout(pawn) {
    if (!CONFIG.GIVE_PRIMARY || (CONFIG.GIVE_PRIMARY === "auto" && mapWeapons >= CONFIG.MAP_WEAPONS_ENOUGH) || !pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
    if (pawn.FindWeaponBySlot(CSGearSlot.RIFLE)) return;
    pawn.GiveNamedItem(CONFIG.PRIMARIES[Math.floor(Math.random() * CONFIG.PRIMARIES.length)], false);
}
function freeze(p, pawn, on) {
    if (p.frozen === on) return;
    p.frozen = on;
    try { if (pawn && pawn.IsValid()) pawn.SetMoveType(on ? CSMoveType.NONE : CSMoveType.WALK); } catch (e) { }
}
function closeShop(p) {
    if (!p.shopOpen && !p.frozen) return;
    p.shopOpen = false;
    freeze(p, pawnOf(p.slot), false);
    if (CONFIG.SHOP_CURSOR && findHud()) try { hud.SetInputCaptureEnabled(p.slot, false); } catch (e) { }
}
function openShop(p, pawn) {
    if (!findHud() || !SHOP[p.role] || phase !== P_ACTIVE) return;
    p.shopOpen = true; p.shopSel = 0; p.shopAt = now;
    if (CONFIG.SHOP_CURSOR) { try { hud.SetInputCaptureEnabled(p.slot, true); } catch (e) { } }
    else if (pawn.GetGroundEntity()) freeze(p, pawn, true);
}
function buy(p, pawn, idx) {
    const it = (SHOP[p.role] || [])[idx];
    if (!it) return;
    if (it.cost > p.credits) { tell(p.slot, "Not enough credits", 3); return; }
    p.credits -= it.cost;
    switch (it.id) {
        case "armor": pawn.SetArmor(100); pawn.SetHasHelmet(true); break;
        case "knife": p.knife = true; break;
        case "m4s": { const w = pawn.FindWeaponBySlot(CSGearSlot.RIFLE); if (w) pawn.DropWeapon(w); give(pawn, "weapon_m4a1_silencer"); break; }
        case "awp": { const w = pawn.FindWeaponBySlot(CSGearSlot.RIFLE); if (w) pawn.DropWeapon(w); give(pawn, "weapon_awp"); break; }
        case "radar": p.radarUntil = now + CONFIG.RADAR_TIME; p.radarText = ""; break;
        case "nades": give(pawn, "weapon_hegrenade"); give(pawn, "weapon_molotov"); break;
        case "heal": pawn.GiveNamedItem("weapon_healthshot", false); pawn.GiveNamedItem("weapon_healthshot", false); break;
        case "taser": give(pawn, "weapon_taser"); break;
        case "util": give(pawn, "weapon_smokegrenade"); give(pawn, "weapon_flashbang"); break;
    }
    tell(p.slot, "Bought " + it.name, 3);
}

const KEYS = [CSInputs.FORWARD, CSInputs.BACK, CSInputs.USE, CSInputs.LOOK_AT_WEAPON, CSInputs.JUMP, CSInputs.RELOAD];
function playerInput(p, c, pawn) {
    if (phase === P_WAIT && !CONFIG.CARRY) { p.prevKeys = 0; return; }
    let keys = 0;
    if (p.shopOpen) { for (let i = 0; i < 5; i++) if (pawn.IsInputPressed(KEYS[i])) keys |= 1 << i; }
    else {
        if (pawn.IsInputPressed(CSInputs.USE)) keys |= 4;
        if (pawn.IsInputPressed(CSInputs.LOOK_AT_WEAPON)) keys |= 8;
        if (p.hold && pawn.IsInputPressed(CSInputs.RELOAD)) keys |= 32;
    }
    const down = keys & ~p.prevKeys, up = p.prevKeys & ~keys;
    p.prevKeys = keys;
    if (p.shopOpen) {
        if (down & 8) p.fUsed = true;
        const n = (SHOP[p.role] || []).length;
        if (down & 1) p.shopSel = (p.shopSel + n - 1) % n;
        if (down & 2) p.shopSel = (p.shopSel + 1) % n;
        if (down & 4) buy(p, pawn, p.shopSel);
        if ((down & 8) || (down & 16) || now - p.shopAt > CONFIG.SHOP_TIMEOUT) closeShop(p);
        return;
    }
    // F: hold = shop; tap = next weapon only with HIDE_NATIVE_HUD (CS2's own switching is off then); Ctrl+F = chat window
    if (down & 8) {
        p.fDownAt = now; p.fUsed = false;
        if (CONFIG.HIDE_NATIVE_HUD && pawn.IsInputPressed(CSInputs.DUCK)) {
            p.fUsed = true; p.chatHudUntil = now < p.chatHudUntil ? 0 : now + CONFIG.CHAT_HUD_TIME;
            if (p.chatHudUntil) tell(p.slot, "Chat open for " + CONFIG.CHAT_HUD_TIME + "s: press Y / U to type", 3);
            syncNativeHud(p, pawn);
        }
    }
    if ((keys & 8) && !p.fUsed && p.fDownAt >= 0 && now - p.fDownAt >= CONFIG.SHOP_HOLD && SHOP[p.role] && phase === P_ACTIVE) {
        p.fUsed = true; openShop(p, pawn); return;
    }
    if (up & 8) {
        if (!p.fUsed && p.fDownAt >= 0 && now - p.fDownAt < CONFIG.SHOP_HOLD && CONFIG.F_CYCLE && p.nativeHidden === true) cycleWeapon(p, pawn);
        p.fDownAt = -1; p.fUsed = false;
    }
    if (p.hold) {
        if (down & 4) { drop(p, null); p.grabTried = true; }
        else if (down & 32) drop(p, pawn);
    } else if (down & 4) {
        p.useAt = now; p.grabTried = false; p.bodyPend = false;
        if (phase >= P_ACTIVE && CONFIG.CARRY && CONFIG.CARRY_BODIES && aimedBody(pawn)) p.bodyPend = true;   // tap = search, hold = carry
        else if (phase >= P_ACTIVE && !searchBody(p, pawn, pawn.IsInputPressed(CSInputs.WALK)) && p.role === R_TRA && phase === P_ACTIVE) pressButton(p, pawn);
    } else if ((keys & 4) && CONFIG.CARRY && !p.grabTried && now - p.useAt >= CONFIG.CARRY_HOLD_TIME) {
        p.grabTried = true; p.bodyPend = false; tryGrab(p, pawn);
    }
    if ((up & 4) && p.bodyPend) { p.bodyPend = false; if (!p.grabTried) searchBody(p, pawn, pawn.IsInputPressed(CSInputs.WALK)); }
    if (p.hold) carry(p, pawn);
}

const CYCLE_EXTRA = ["weapon_taser", "weapon_hegrenade", "weapon_flashbang", "weapon_smokegrenade", "weapon_molotov", "weapon_incgrenade",
    "weapon_decoy", "weapon_tagrenade", "weapon_healthshot"];
function cycleWeapon(p, pawn) {
    const list = [];
    const add = (w) => { if (w && !list.includes(w)) list.push(w); };
    try {
        add(pawn.FindWeaponBySlot(CSGearSlot.RIFLE)); add(pawn.FindWeaponBySlot(CSGearSlot.PISTOL)); add(pawn.FindWeaponBySlot(CSGearSlot.KNIFE));
        for (const n of CYCLE_EXTRA) add(pawn.FindWeapon(n));
        add(pawn.FindWeaponBySlot(CSGearSlot.GRENADES)); add(pawn.FindWeaponBySlot(CSGearSlot.BOOSTS));
    } catch (e) { return; }
    if (list.length < 2) return;
    const cur = pawn.GetActiveWeapon();
    const next = list[(list.indexOf(cur) + 1) % list.length];
    try { pawn.SwitchToWeapon(next); } catch (e) { return; }
    p.msg = list.map(w => (w === next ? "[" : "") + weaponName(w).toUpperCase() + (w === next ? "]" : "")).join("  ");
    p.msgUntil = now + 1.5;
}

// ------------------------------------------------------------------ carrying (props and bodies)
const heldBy = new Map();
function forward(a) {
    const py = a.pitch * Math.PI / 180, yw = a.yaw * Math.PI / 180;
    return { x: Math.cos(py) * Math.cos(yw), y: Math.cos(py) * Math.sin(yw), z: -Math.sin(py) };
}
function tryGrab(p, pawn) {
    const eye = pawn.GetEyePosition(), f = forward(pawn.GetEyeAngles()), r = CONFIG.CARRY_RANGE;
    const tr = Instance.TraceLine({ start: eye, end: { x: eye.x + f.x * r, y: eye.y + f.y * r, z: eye.z + f.z * r }, ignoreEntity: pawn });
    let e = tr.didHit ? tr.hitEntity : undefined;
    const reach = tr.didHit ? Math.min(r, tr.fraction * r + 8) : r;
    if (!e || e instanceof CSPlayerPawn || e.IsWorld() || !carryable(e)) e = nearestCarryable(eye, f, reach);
    if (!e) return;
    if (heldBy.has(e) || pawn.GetGroundEntity() === e) return;
    p.hold = e; p.holdStall = 0; heldBy.set(e, p.slot);
    try { e.SetOwner(pawn); } catch (err) { }
}
function carryable(e) {
    try { return CONFIG.CARRY_CLASSES.includes(e.GetClassName()) || (CONFIG.CARRY_BODIES && bodies.some(b => b.ent === e)); } catch (err) { return false; }
}
function nearestCarryable(eye, f, reach) {
    // debris objects (the gold block) can be missed by the trace: take the carryable entity closest to the aim line
    let best = null, bestD = CONFIG.CARRY_AIM_RADIUS;
    const list = [];
    for (const cls of CONFIG.CARRY_CLASSES) for (const e of Instance.FindEntitiesByClass(cls)) list.push(e);
    if (CONFIG.CARRY_BODIES) for (const b of bodies) if (b.ent) list.push(b.ent);
    for (const e of list) {
        let o;
        try { o = e.GetAbsOrigin(); } catch (err) { continue; }
        const dx = o.x - eye.x, dy = o.y - eye.y, dz = o.z - eye.z, t = dx * f.x + dy * f.y + dz * f.z;
        if (t < 0 || t > reach + 16) continue;
        const px = dx - f.x * t, py = dy - f.y * t, pz = dz - f.z * t, dd = Math.sqrt(px * px + py * py + pz * pz);
        if (dd >= bestD) continue;
        const tr = Instance.TraceLine({ start: eye, end: o, ignoreEntity: e, ignorePlayers: true });
        if (tr.didHit && tr.fraction < 0.9) continue;
        bestD = dd; best = e;
    }
    return best;
}
const ownerClear = [];
function releaseOwner(e, later) {
    if (!e) return;
    if (later) { ownerClear.push({ e, at: now + 1.5 }); return; }
    try { if (e.IsValid()) e.SetOwner(undefined); } catch (err) { }
}
function drop(p, throwerPawn) {
    const e = p.hold;
    p.hold = null;
    if (!e) return;
    heldBy.delete(e);
    releaseOwner(e, !!throwerPawn);
    if (!throwerPawn) return;
    try {
        const f = forward(throwerPawn.GetEyeAngles()), v = throwerPawn.GetAbsVelocity(), t = CONFIG.CARRY_THROW;
        e.Teleport({ velocity: { x: v.x + f.x * t, y: v.y + f.y * t, z: v.z + f.z * t + 80 } });
    } catch (err) { }
}
function carry(p, pawn) {
    const e = p.hold;
    try {
        if (!e.IsValid() || pawn.GetGroundEntity() === e) { drop(p, null); return; }
        const eye = pawn.GetEyePosition(), f = forward(pawn.GetEyeAngles()), d = CONFIG.CARRY_DIST;
        const o = e.GetAbsOrigin();
        const dx = eye.x + f.x * d - o.x, dy = eye.y + f.y * d - o.y, dz = eye.z + f.z * d - 12 - o.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist > CONFIG.CARRY_BREAK_DIST) { drop(p, null); return; }
        let k = CONFIG.CARRY_GAIN;
        if (dist * k > CONFIG.CARRY_MAX_SPEED) k = CONFIG.CARRY_MAX_SPEED / dist;
        // motion disabled (DisableMotion, frozen by the map): it doesn't move however we push it, so let go
        const v = e.GetAbsVelocity();
        if (dist > 24 && v.x * v.x + v.y * v.y + v.z * v.z < 4) { if (++p.holdStall > 16) { drop(p, null); return; } } else p.holdStall = 0;
        e.Teleport({ velocity: { x: dx * k, y: dy * k, z: dz * k }, angularVelocity: { x: 0, y: 0, z: 0 } });
    } catch (err) { drop(p, null); }
}
function bodyPos(b) {
    if (b.ent) { try { if (b.ent.IsValid()) return b.ent.GetAbsOrigin(); } catch (e) { } b.ent = null; }
    return b.pos;
}
function findTemplate(name) {
    const t = name ? Instance.FindEntityByName(name) : undefined;
    return t instanceof PointTemplate ? t : undefined;
}
function bodyTemplate(team) {
    const ct = findTemplate(CONFIG.BODY_TEMPLATE), t = findTemplate(CONFIG.BODY_TEMPLATE_T);
    return team === 2 ? t || ct : ct || t;
}
function spawnBody(pawn, model) {
    let team = 3;
    try { team = pawn.GetTeamNumber(); } catch (e) { }
    const tpl = bodyTemplate(team);
    if (!tpl || bodies.length >= CONFIG.BODY_MAX) return null;
    try {
        const o = pawn.GetAbsOrigin();
        const ents = tpl.ForceSpawn({ x: o.x, y: o.y, z: o.z + 8 }, { pitch: 0, yaw: pawn.GetAbsAngles().yaw, roll: 0 });
        const e = ents && ents[0];
        if (!e) return null;
        // no SetModel / Teleport on a fresh prop_ragdoll: a model swap left its bone list empty and the next Teleport crashed the server
        if (CONFIG.BODY_SET_MODEL && model && e instanceof BaseModelEntity) e.SetModel(model);
        return e;
    } catch (err) { log("body spawn failed " + err); return null; }
}

// ------------------------------------------------------------------ map entities (converted ttt_* entities, see tools/ttt_convert.py)
const MD = MAP_DATA[Instance.GetMapName()] || MAP_DATA[String(Instance.GetMapName()).replace(/^.*[\\/]/, "")] || null;
const mapState = { btn: new Map(), chk: new Map(), txtOff: new Set(), owner: new Map() };
let mapWeapons = 0;
const WEAPON_CLASSES = ["ak47", "m4a1", "m4a1_silencer", "famas", "galilar", "aug", "sg556", "awp", "ssg08", "scar20", "g3sg1", "mp7", "mp9",
    "mp5sd", "mac10", "ump45", "p90", "bizon", "nova", "xm1014", "mag7", "sawedoff", "m249", "negev", "glock", "hkp2000", "usp_silencer",
    "p250", "fiveseven", "tec9", "cz75a", "deagle", "revolver", "elite"];
function mapFire(ev) { if (MD && MD.settings) Instance.EntFireAtName({ name: "ttt_ms__" + ev, input: "Trigger", delay: 0.05 }); }
function relay(id, ev, activator) { Instance.EntFireAtName({ name: id + "__" + ev, input: "Trigger", activator }); }
function mapRoundStart() {
    ptState.clear(); ownerClear.length = 0;
    mapState.btn.clear(); mapState.chk.clear(); mapState.txtOff.clear(); mapState.owner.clear();
    if (MD) {
        for (const b of MD.buttons || []) mapState.btn.set(b.id, { used: false, next: 0, off: !!b.off });
        for (const id in MD.checks || {}) mapState.chk.set(id, MD.checks[id].on);
    }
    mapWeapons = 0;
    for (const w of WEAPON_CLASSES) for (const e of Instance.FindEntitiesByClass("weapon_" + w)) { try { if (!e.GetOwner()) mapWeapons++; } catch (x) { } }
    if (MD && MD.settings) Instance.EntFireAtName({ name: "ttt_ms__prep", input: "Trigger", delay: 0.05 });
}
function roleOk(slot, want) {
    const r = st(slot).role;
    if (!r || !isAlive(slot)) return false;
    return want === "any" || (want === "inn" && r === R_INN) || (want === "tra" && r === R_TRA) || (want === "det" && r === R_DET);
}
function trapOwner(inflictor) {
    if (!MD || !MD.owners || !inflictor || !mapState.owner.size) return null;
    let n = "";
    try { n = inflictor.GetEntityName(); } catch (e) { return null; }
    if (!n) return null;
    for (const [id, slot] of mapState.owner) { const o = MD.owners[id]; if (o && o.damager === n && slot >= 0) return { slot, name: o.name || "a trap" }; }
    return null;
}
function aimButton(pawn) {
    if (!MD || !MD.buttons || !MD.buttons.length) return null;
    const eye = pawn.GetEyePosition(), f = forward(pawn.GetEyeAngles());
    let best = null, bestDot = CONFIG.BUTTON_CONE;
    for (const b of MD.buttons) {
        const s = mapState.btn.get(b.id);
        if (!s || s.off || (b.once && s.used) || now < s.next) continue;
        const dx = b.pos[0] - eye.x, dy = b.pos[1] - eye.y, dz = b.pos[2] - eye.z, d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (d > b.range || d < 1) continue;
        const dot = (dx * f.x + dy * f.y + dz * f.z) / d;
        if (dot > bestDot) { bestDot = dot; best = b; }
    }
    return best;
}
function pressButton(p, pawn) {
    const b = aimButton(pawn);
    if (!b) return;
    const s = mapState.btn.get(b.id);
    s.used = true; s.next = now + Math.max(0.5, b.wait > 0 ? b.wait : 0.5);
    relay(b.id, "pressed", pawn);
    tell(p.slot, "Traitor trap: " + (b.desc || "activated"), 4);
}
function buttonHint(p, pawn) {
    const b = aimButton(pawn);
    if (b) { p.msg = "[E] traitor trap: " + (b.desc || "use"); p.msgUntil = now + 0.5; }
}
const ptState = new Map();
function ptouchFire(id, activator) {
    if (phase !== P_ACTIVE) return;   // map trigger outputs (win sequences) only in live rounds
    const s = ptState.get(id) || { last: -10, inside: false };
    ptState.set(id, s);
    if (now - s.last < 1) return;
    s.last = now;
    let act = activator;
    if (!act) { const c = MD.ptouch[id]; act = Instance.FindEntityByName(c.ent); }
    for (const q of players.values()) if (q.hold && act && q.hold === act) drop(q, null);
    relay(id, "touch", act);
}
function ptouchPoll() {
    if (!MD || !MD.ptouch || phase !== P_ACTIVE) return;   // live rounds only; a prop placed during warmup/prep fires once the round goes live
    for (const id in MD.ptouch) {
        const c = MD.ptouch[id], s = ptState.get(id) || { last: -10, inside: false };
        ptState.set(id, s);
        let hit = null;
        for (const e of Instance.FindEntitiesByName(c.ent)) {
            let o;
            try { o = e.GetAbsOrigin(); } catch (err) { continue; }
            const x = o.x + c.off[0], y = o.y + c.off[1], z = o.z + c.off[2];
            if (x + c.half[0] >= c.mins[0] && x - c.half[0] <= c.maxs[0] && y + c.half[1] >= c.mins[1] && y - c.half[1] <= c.maxs[1]
                && z + c.half[2] >= c.mins[2] && z - c.half[2] <= c.maxs[2]) { hit = e; break; }
        }
        if (hit && !s.inside) ptouchFire(id, hit);
        s.inside = !!hit;
    }
}
function mapInput(name, fn) { Instance.OnScriptInput(name, (inp) => { try { fn(inp); } catch (e) { log(name + ": " + e); } }); }
if (MD) {
    for (const b of MD.buttons || []) {
        mapInput("ttt:btnoff:" + b.id, () => { const s = mapState.btn.get(b.id); if (s) s.off = true; });
        mapInput("ttt:btnon:" + b.id, () => { const s = mapState.btn.get(b.id); if (s) s.off = false; });
        mapInput("ttt:btntog:" + b.id, () => { const s = mapState.btn.get(b.id); if (s) s.off = !s.off; });
    }
    for (const id in MD.checks || {}) {
        const c = MD.checks[id];
        mapInput("ttt:chkon:" + id, () => mapState.chk.set(id, true));
        mapInput("ttt:chkoff:" + id, () => mapState.chk.set(id, false));
        mapInput("ttt:chk:" + id, ({ activator }) => {
            if (!mapState.chk.get(id)) return;
            relay(id, "found", activator);
            let n = 0;
            for (const q of players.values()) {
                if (q.role !== R_TRA) continue;
                const t = pawnOf(q.slot);
                if (!t || !t.IsAlive()) continue;
                const o = t.GetAbsOrigin(), z = o.z + 36;
                if (o.x >= c.mins[0] - 16 && o.x <= c.maxs[0] + 16 && o.y >= c.mins[1] - 16 && o.y <= c.maxs[1] + 16 && z >= c.mins[2] - 36 && z <= c.maxs[2] + 36) n++;
            }
            if (n) log("tester " + id + ": " + n + " traitor(s) inside");
        });
    }
    for (const id in MD.roles || {}) {
        const want = MD.roles[id];
        mapInput("ttt:role:" + id, ({ activator }) => relay(id, roleOk(slotOf(toPawn(activator)), want) ? "pass" : "fail", activator));
    }
    for (const id in MD.texts || {}) {
        const t = MD.texts[id];
        mapInput("ttt:txtoff:" + id, () => mapState.txtOff.add(id));
        mapInput("ttt:txt:" + id, ({ activator }) => {
            if (mapState.txtOff.has(id) || !t.msg) return;
            if (t.rcv === 0) { const s = slotOf(toPawn(activator)); if (s >= 0) tell(s, t.msg, 5); return; }
            for (const c of liveControllers()) {
                const s = c.GetPlayerSlot(), r = st(s).role;
                if (t.rcv === 1 || (t.rcv === 2 && r === R_DET) || (t.rcv === 3 && r === R_TRA) || (t.rcv === 4 && (r === R_INN || r === R_DET))) tell(s, t.msg, 5);
            }
        });
    }
    for (const id in MD.owners || {}) {
        mapInput("ttt:own:" + id, ({ activator }) => mapState.owner.set(id, slotOf(toPawn(activator))));
        mapInput("ttt:unown:" + id, () => mapState.owner.delete(id));
    }
    for (const id in MD.credits || {}) {
        const n = MD.credits[id];
        mapInput("ttt:cred:" + id, ({ activator }) => {
            const s = slotOf(toPawn(activator)), q = s >= 0 ? st(s) : null;
            if (q && q.credits >= n) { q.credits -= n; relay(id, "ok", activator); } else relay(id, "fail", activator);
        });
    }
    for (const id in MD.ptouch || {}) {
        mapInput("ttt:ptouch:" + id, ({ activator }) => ptouchFire(id, activator));
    }
    if (MD.duck) {
        mapInput("ttt:duck:on", ({ activator }) => { const s = slotOf(toPawn(activator)); if (s >= 0) { st(s).duckUntil = now + 30; tell(s, "Crouch (hold Ctrl) to crawl through", 4); } });
        mapInput("ttt:duck:off", ({ activator }) => { const s = slotOf(toPawn(activator)); if (s >= 0) st(s).duckUntil = 0; });
    }
    for (const a of MD.alphas || []) mapInput("ttt:alpha:" + a, ({ activator }) => { const pw = toPawn(activator); if (pw) setAlpha(pw, a); });
    if (MD.wins) {
        mapInput("ttt:win:t", () => { if (phase === P_ACTIVE) endRound(R_TRA, "The map gave the traitors the win"); });
        mapInput("ttt:win:i", () => { if (phase === P_ACTIVE) endRound(R_INN, "The map gave the innocents the win"); });
        mapInput("ttt:win:d", () => { if (phase === P_ACTIVE) endRound(R_INN, "Draw"); });
    }
}

// ------------------------------------------------------------------ bodies
function aimedBody(pawn) {
    if (!bodies.length) return null;
    const eye = pawn.GetEyePosition(), a = pawn.GetEyeAngles();
    const py = a.pitch * Math.PI / 180, yw = a.yaw * Math.PI / 180;
    const f = { x: Math.cos(py) * Math.cos(yw), y: Math.cos(py) * Math.sin(yw), z: -Math.sin(py) };
    let best = null, bestDot = CONFIG.BODY_CONE;
    for (const b of bodies) {
        const bp = bodyPos(b);
        const dx = bp.x - eye.x, dy = bp.y - eye.y, dz = bp.z + 12 - eye.z;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (d > CONFIG.BODY_RANGE + 40) continue;
        const dot = d < 40 ? 1 : (dx * f.x + dy * f.y + dz * f.z) / d;
        if (dot > bestDot) { bestDot = dot; best = b; }
    }
    return best;
}
function searchBody(p, pawn, covert) {
    const best = aimedBody(pawn);
    if (!best) return false;
    const what = best.name + " was " + (best.role === R_INN ? "an " : "a ") + ROLE_NAME[best.role] + ".";
    if (covert && !best.found) tell(p.slot, "Covert search (not announced): " + what, 6);
    else if (!best.found) {
        best.found = true;
        const bq = players.get(best.slot);
        if (bq && bq.role === best.role) bq.confirmed = true;
        announce(p.name + " found the body of " + best.name + ". They were " + (best.role === R_INN ? "an " : "a ") + ROLE_NAME[best.role] + ".");
    }
    if (p.role === R_DET && !best.dnaTaken) {
        best.dnaTaken = true;
        const ago = Math.round(now - best.time);
        let txt = best.name + ": killed by " + best.weapon + " " + ago + "s ago.";
        if (best.killerSlot >= 0 && best.killerSlot !== best.slot && isAlive(best.killerSlot)) {
            p.trackSlot = best.killerSlot; p.trackUntil = now + CONFIG.DNA_TIME; txt += " DNA trail on the killer for " + CONFIG.DNA_TIME + "s.";
        } else txt += " No DNA trail.";
        tell(p.slot, txt, 8);
    }
    return true;
}

function weaponLabel(hit) {
    if (!hit) return "unknown causes";
    if (hit.weapon) return hit.weapon;
    if (hit.types & CSDamageTypes.BLAST) return "an explosion";
    if (hit.types & CSDamageTypes.BURN) return "fire";
    if (hit.types & CSDamageTypes.FALL) return "a fall";
    return "unknown causes";
}

function onDeath(pawn, attacker, weapon) {
    const vs = slotOf(pawn);
    if (vs < 0) return;
    const p = st(vs);
    p.pendingKill = false;
    closeShop(p);
    if (p.hold) drop(p, null);
    if (!p.deathModel) { try { p.deathModel = pawn.GetModelName(); } catch (e) { } }
    if (phase < P_ACTIVE || !p.role) { p.deathModel = ""; return; }
    let ks = slotOf(attacker);
    const hit = p.lastHit && now - p.lastHit.t < 15 ? p.lastHit : null;
    if ((ks < 0 || ks === vs) && hit) ks = hit.slot;
    const wname = weapon ? weaponName(weapon) : null;
    let pos;
    try { pos = pawn.GetAbsOrigin(); } catch (e) { pos = { x: 0, y: 0, z: 0 }; }
    const ent = spawnBody(pawn, p.deathModel);
    p.deathModel = "";
    bodies.push({ slot: vs, name: p.name || "someone", role: p.role, pos, ent, time: now, killerSlot: ks, weapon: wname || weaponLabel(hit), found: false, dnaTaken: false });
    if (phase !== P_ACTIVE) return;
    const k = ks >= 0 && ks !== vs ? players.get(ks) : undefined;
    if (k && k.role) {
        const kc = Instance.GetPlayerController(ks);
        if (side(k.role) === side(p.role)) { k.karma = Math.max(0, k.karma - CONFIG.KARMA_KILL); k.cleanRound = false; if (CONFIG.HIDE_KILLER) k.scoreDelta--; else if (kc) kc.AddScore(-1); }
        else { if (p.role === R_TRA) k.karma = Math.min(CONFIG.KARMA_MAX, k.karma + CONFIG.KARMA_GOOD_KILL); if (CONFIG.HIDE_KILLER) k.scoreDelta++; else if (kc) kc.AddScore(1); }
    }
    if (p.role === R_TRA) {
        for (const q of players.values()) if (q.role === R_DET && isAlive(q.slot)) q.credits++;
    } else {
        phaseEnd = Math.min(phaseEnd + CONFIG.HASTE_PER_DEATH, activeCap);
        deathsSinceCredit++;
        const bonus = p.role === R_DET || deathsSinceCredit >= CONFIG.CREDIT_EVERY_N_DEATHS;
        if (deathsSinceCredit >= CONFIG.CREDIT_EVERY_N_DEATHS) deathsSinceCredit = 0;
        if (bonus) for (const q of players.values()) if (q.role === R_TRA && isAlive(q.slot)) { q.credits++; tell(q.slot, "+1 credit", 3); }
        Instance.SetRoundRemainingTime(phaseEnd - now + 20);
    }
}
function weaponName(w) {
    try { const n = w.GetData().GetName(); if (n) return n.replace(/^weapon_/, ""); } catch (e) { }
    try { return w.GetClassName().replace(/^weapon_/, ""); } catch (e) { return "a weapon"; }
}

// ------------------------------------------------------------------ damage
Instance.OnModifyPlayerDamage((ev) => {
    if (killing) return;
    const victim = ev.player, vs = slotOf(victim);
    const as = slotOf(ev.attacker);
    // prep: players can't hurt each other, but the world (trigger_hurt, falls, traps) still kills, and the dead respawn
    if (phase === P_PREP) return as >= 0 && as !== vs ? { abort: true } : undefined;
    let dmg = ev.damage, changed = false;
    if (phase === P_ACTIVE && as >= 0 && as !== vs) {
        const a = st(as);
        if (a.karmaBase < CONFIG.KARMA_MAX) { dmg *= Math.max(CONFIG.KARMA_MIN_MULT, a.karmaBase / CONFIG.KARMA_MAX); changed = true; }
        if (a.knife && ev.weapon) {
            try { if (ev.weapon.GetData().GetType() === CSWeaponType.KNIFE) { dmg = 500; a.knife = false; changed = true; } } catch (e) { }
        }
    }
    const byPlayer = as >= 0 && as !== vs;
    if (vs >= 0 && phase === P_ACTIVE && dmg >= victim.GetHealth() && ((CONFIG.HIDE_KILLER && byPlayer) || (CONFIG.HIDE_CLIENT_RAGDOLL && bodyTemplate()))) {
        const v = st(vs);
        v.pendingKill = true;
        v.pendingAttacker = !CONFIG.HIDE_KILLER && byPlayer ? ev.attacker : undefined;
        return { damage: Math.max(1, Math.round(dmg)), damageFlags: ev.damageFlags | CSDamageFlags.PREVENT_DEATH };
    }
    if (changed) return { damage: Math.max(1, Math.round(dmg)) };
});

Instance.OnPlayerDamage((ev) => {
    if (killing) return;
    const vs = slotOf(ev.player);
    if (vs < 0) return;
    const p = st(vs), as = slotOf(ev.attacker);
    if (as >= 0 && as !== vs) {
        p.lastHit = { slot: as, t: now, types: ev.damageTypes, weapon: ev.weapon ? weaponName(ev.weapon) : null };
        const a = st(as);
        if (phase === P_ACTIVE && a.role && p.role && side(a.role) === side(p.role)) {
            a.karma = Math.max(0, a.karma - ev.damage * CONFIG.KARMA_HURT); a.cleanRound = false;
        }
    } else {
        const own = trapOwner(ev.inflictor);
        if (own) p.lastHit = { slot: own.slot, t: now, types: ev.damageTypes, weapon: own.name };
        else if (!p.lastHit || now - p.lastHit.t > 15) p.lastHit = { slot: -1, t: now, types: ev.damageTypes, weapon: null };
    }
    if (p.shopOpen) closeShop(p);
    if (p.pendingKill) {
        if (ev.player.GetHealth() <= 1) killQueue.push(vs);
        else p.pendingKill = false;
    }
});

function runKills() {
    while (killQueue.length) {
        const vs = killQueue.shift(), p = st(vs), pawn = pawnOf(vs);
        if (!pawn || !pawn.IsAlive()) { p.pendingKill = false; continue; }
        try { p.deathModel = pawn.GetModelName(); } catch (e) { p.deathModel = ""; }
        if (CONFIG.HIDE_CLIENT_RAGDOLL && bodyTemplate()) { try { pawn.SetModelScale(0.02); p.scaled = true; } catch (e) { } }
        let attacker = p.pendingAttacker;
        try { if (attacker && !attacker.IsValid()) attacker = undefined; } catch (e) { attacker = undefined; }
        p.pendingAttacker = undefined;
        killing = true;
        try { pawn.TakeDamage({ damage: 1000, attacker, inflictor: attacker, damageTypes: attacker ? CSDamageTypes.BULLET : CSDamageTypes.GENERIC, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR }); }
        catch (e) { log("kill failed " + e); }
        finally { killing = false; }
        if (pawn.IsValid() && pawn.IsAlive()) { log("hidden kill blocked; check plugins/damage settings"); p.pendingKill = false; }
    }
}

Instance.OnPlayerKill(({ player, attacker, weapon }) => onDeath(player, attacker, weapon));

// ------------------------------------------------------------------ lifecycle
Instance.OnRoundStart(() => { now = Instance.GetGameTime(); onRoundStart(); ensureThink(); });
function flushScores() {
    for (const p of players.values()) {
        if (!p.scoreDelta) continue;
        const c = Instance.GetPlayerController(p.slot);
        if (c) c.AddScore(p.scoreDelta);
        p.scoreDelta = 0;
    }
}
Instance.OnRoundEnd(() => { flushScores(); if (phase !== P_WAIT) { phase = P_POST; roundEnded = true; endFallbackAt = 0; } for (const p of players.values()) closeShop(p); });
const savedKarma = new Map();
function restoreKarma(p) {
    const k = p.name && savedKarma.get(p.name);
    if (k === undefined) return;
    savedKarma.delete(p.name); p.karma = k; p.karmaBase = k;
}
Instance.OnPlayerConnect(({ player }) => { const s = player.GetPlayerSlot(); players.delete(s); const p = st(s); p.name = clean(player.GetPlayerName()); restoreKarma(p); });
Instance.OnPlayerActivate(({ player }) => {
    const s = player.GetPlayerSlot(), p = st(s); p.name = clean(player.GetPlayerName()); resetHud(s);
    if (CONFIG.TRY_HIDE_KILLFEED) Instance.ClientCommand(s, "cl_drawhud_force_deathnotices -1");
});
Instance.OnPlayerDisconnect(({ playerSlot }) => { const q = players.get(playerSlot); if (q && q.hold) drop(q, null); if (q && q.name && q.karma < CONFIG.KARMA_START) savedKarma.set(q.name, q.karma); players.delete(playerSlot); for (const b of bodies) if (b.killerSlot === playerSlot) b.killerSlot = -1; });
Instance.OnPlayerReset(({ player }) => {
    const s = slotOf(player);
    if (s < 0) return;
    const p = st(s); p.frozen = false; p.shopOpen = false; p.pendingKill = false; p.hud.clear();
    if (p.hold) drop(p, null);
    if (p.scaled) { p.scaled = false; try { player.SetModelScale(1); } catch (e) { } }
    try { p.name = clean(player.GetPlayerController().GetPlayerName()); } catch (e) { }
    tint(player, false);
    if (phase === P_ACTIVE && !p.role) {
        p.role = R_INN;
    }
    if (phase === P_ACTIVE && p.role === R_DET) tint(player, true);
    if (phase === P_PREP || phase === P_WAIT) p.loadoutAt = now + 0.3;
    p.nativeHidden = null; p.nativeAt = now + 0.5; p.chatHudUntil = 0;
    resetHud(s);
});
Instance.OnPlayerTeamChanged(({ player }) => { const s = slotOf(player); if (s >= 0) resetHud(s); });
Instance.OnCustomHudClicked(({ player, buttonId }) => {
    if (!player || !/^Shop\d$/.test(buttonId)) return;
    const p = st(player.GetPlayerSlot()), pawn = player.GetPlayerPawn();
    if (!p.shopOpen || !pawn || !pawn.IsAlive()) return;
    p.shopSel = Number(buttonId.slice(4)); buy(p, pawn, p.shopSel);
});
Instance.OnPlayerChat(({ player, text }) => {
    if (!player) return;
    try {
        const s = player.GetPlayerSlot();
        chatLog.push({ t: now, name: clean(player.GetPlayerName()).slice(0, 16), text: String(text).replace(/[\r\n]/g, " ").slice(0, 90), alive: isAlive(s) });
        if (chatLog.length > 20) chatLog.shift();
    } catch (e) { }
    const t = text.trim().toLowerCase();
    if (t === "!rules" || t === "/rules") tell(player.GetPlayerSlot(), RULES, 15);
    if (t === "!ttt" || t === "/ttt") tell(player.GetPlayerSlot(), "Tap E on a body = identify (Shift+E = covert, not announced). Hold E on a prop or body = carry (E drop, R throw). Hold F = shop (traitor/detective): W/S pick, E buy, F close. Tab = scoreboard. Traitors: aim at a trap and press E. !rules = rules." + (CONFIG.HIDE_NATIVE_HUD ? " Tap F = next weapon. Ctrl+F = chat for " + CONFIG.CHAT_HUD_TIME + "s." : ""), 12);
});

function think() {
    Instance.SetNextThink(Instance.GetGameTime());
    try {
        now = Instance.GetGameTime(); tick++;
        hudBudget = CONFIG.HUD_BUDGET;
        if (Instance.IsWarmupPeriod() && phase !== P_WAIT) phase = P_WAIT;
        runKills();
        if (tick % 8 === 4) {
            ptouchPoll();
            for (let i = ownerClear.length - 1; i >= 0; i--) if (now >= ownerClear[i].at) { releaseOwner(ownerClear[i].e, false); ownerClear.splice(i, 1); }
        }
        if (phase === P_PREP && now >= phaseEnd) startActive();
        if (phase === P_ACTIVE && tick % 8 === 0) checkWin();
        if (roundEnded && endFallbackAt && now >= endFallbackAt) {
            endFallbackAt = 0;
            Instance.ServerCommand("mp_ignore_round_win_conditions 0");
            Instance.SetRoundRemainingTime(1);
        }
        const h = findHud();
        const cs = liveControllers();
        for (const c of cs) {
            try {
                let p = st(c.GetPlayerSlot());
                if (p.ctrl !== c) {
                    if (p.ctrl) {
                        if (p.name && p.karma < CONFIG.KARMA_START) savedKarma.set(p.name, p.karma);
                        p = new PState(p.slot); players.set(p.slot, p); resetHud(p.slot);
                    }
                    p.ctrl = c; p.name = clean(c.GetPlayerName()); restoreKarma(p);
                    if (phase === P_ACTIVE && !p.role && isAlive(p.slot)) p.role = R_INN;
                }
                const pawn = c.GetPlayerPawn();
                const alive = !!pawn && pawn.IsValid() && pawn.IsAlive();
                if (alive) {
                    if (!c.IsBot() && (tick + p.slot) % 8 === 0 && now >= p.nativeAt) syncNativeHud(p, pawn);
                    if (p.loadoutAt && now >= p.loadoutAt) { p.loadoutAt = 0; if (phase === P_PREP) giveLoadout(pawn); }
                    playerInput(p, c, pawn);
                    if (p.role === R_TRA && phase === P_ACTIVE && !p.shopOpen && MD && (tick + p.slot) % 8 === 0) buttonHint(p, pawn);
                    if (p.duckUntil > now && (tick + p.slot) % 32 === 0 && !pawn.IsDucked()) { p.msg = "Crouch (hold Ctrl) to crawl through"; p.msgUntil = now + 0.6; }
                    if (p.alpha < 255 && (tick + p.slot) % 16 === 0) { try { const w = pawn.GetActiveWeapon(); if (w) w.SetColor({ r: 255, g: 255, b: 255, a: p.alpha }); } catch (e) { } }
                } else {
                    if (p.shopOpen || p.frozen) closeShop(p);
                    if (p.nativeHidden === true && pawn && pawn.IsValid()) { p.nativeHidden = false; nativeHud(pawn, true); }
                }
                if (h && (tick + p.slot) % 8 === 0) drawHud(p, c);
            } catch (e) { log("player " + c.GetPlayerSlot() + ": " + e); }
        }
        if (tick % 640 === 0) {
            const s = "phase " + phase + " players " + cs.length + " hud " + (h ? "yes" : "no");
            if (s !== lastStatus) { lastStatus = s; log(s); }
        }
    } catch (e) { log("think: " + e); }
}
function ensureThink() {
    if (thinkStarted) return;
    thinkStarted = true;
    Instance.SetThink(think);
    Instance.SetNextThink(Instance.GetGameTime());
}

Instance.OnActivate(() => {
    now = Instance.GetGameTime();
    applyCvars(true);
    ensureThink();
    log("loaded; HUD " + (findHud() ? "found" : "missing (add custom_hud_layout '" + CONFIG.HUD_NAME + "')"));
});
Instance.OnScriptReload({
    before: () => { for (const p of players.values()) closeShop(p); return null; },
    after: () => { thinkStarted = false; ensureThink(); },
});
