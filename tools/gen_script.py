"""Build the per-map cs_script (maps/scripts/<map>_io.js) that replaces dead CS:GO entity behaviour."""
import json, os
import gravity
HERE = os.path.dirname(os.path.abspath(__file__))

def build(mapname, script_name, push=None, commands=None, scores=None, speeds=None, gravities=None, spawn_equips=None, equip_items=None):
    head = ['import { Instance, CSPlayerPawn, CSPlayerController%s } from "cs_script/point_script";' % ((', CSInputs' if speeds else '') + (', CSMoveType' if gravities else '') + (', CSGearSlot' if spawn_equips else '')), '',
            '// %s: CS2 replacements for CS:GO entity behaviour that no longer works, written by the CS2 post-import clean.' % mapname,
            '// Everything here is driven by `%s` -> RunScriptInput <input name>, with the activator passed through.' % script_name, '//']
    if push: head.append('//   PushIn_<n> / PushOut_<n>   replaces the trigger_push brushes (CS:GO "set speed" behaviour)')
    if commands: head.append('//   Cmd_<n>     replaces point_servercommand (chat messages / cvars)')
    if scores: head.append('//   Score_<pts> replaces game_score (ApplyScore)')
    if speeds: head.append('//   Speed_<mult> replaces player_speedmod ModifySpeed (activator only, 1 = back to normal)')
    if gravities: head.append(gravity.HEAD_LINE)
    if spawn_equips: head.append('//   (automatic) replaces game_player_equips without "Use Only" (CS:GO ran them on every spawn, CS2 does not)')
    if equip_items: head.append(ITEMS_HEAD)
    body = ['', '// ---------------------------------------------------------------- shared think loop',
            '/** @type {(() => boolean)[]} each returns true while it still needs ticks */',
            'const THINKERS = [];', 'let thinking = false;',
            'function wakeThink() { if (!thinking) { thinking = true; Instance.SetNextThink(Instance.GetGameTime()); } }',
            'Instance.SetThink(() => {', '    let active = false;', '    for (const t of THINKERS) if (t()) active = true;',
            '    if (active) Instance.SetNextThink(Instance.GetGameTime()); else thinking = false;', '});'] if (push or speeds or gravities or spawn_equips) else []
    if push:
        body += ['', '// ---------------------------------------------------------------- trigger_push replacement',
                 "// CS2's trigger_push keeps adding velocity every tick while you are inside it, so CS:GO pushes became rocket launchers.",
                 "// CS:GO's push simply moved you at the push speed in the push direction. Each former trigger_push is now a",
                 '// trigger_multiple that fires PushIn_<id> / PushOut_<id>; while a player is inside, their velocity along the push',
                 '// direction is held at the push speed (sideways / other movement is left alone), clamped to sv_maxvelocity (3500).',
                 '/** @type {Record<string, { dir: number[], speed: number, mins: number[], maxs: number[] }>} */',
                 'const PUSH = ' + json.dumps(push, indent=4) + ';',
                 open(os.path.join(HERE, 'push_tail.js')).read().rstrip()]
    if commands:
        body += ['', '// ---------------------------------------------------------------- point_servercommand replacement',
                 '// CS2 servers block most point_servercommand commands, so the map\'s chat messages / cvars are sent from script instead.',
                 '/** @type {string[]} */',
                 'const COMMANDS = ' + json.dumps(commands, indent=4) + ';',
                 'COMMANDS.forEach((cmd, i) => {',
                 '    Instance.OnScriptInput("Cmd_" + i, () => { Instance.ServerCommand(cmd); });',
                 '});']
    if scores:
        body += ['', '// ---------------------------------------------------------------- game_score replacement (entity removed in CS2)',
                 "// Outputs that fired <game_score>.ApplyScore now fire Score_<points>; the activator's scoreboard score goes up.",
                 'for (const pts of %s) {' % json.dumps(sorted(scores)),
                 '    Instance.OnScriptInput("Score_" + pts, ({ activator }) => {',
                 '        const pawn = activator instanceof CSPlayerPawn ? activator : undefined;',
                 '        const ctrl = pawn ? pawn.GetPlayerController() : (activator instanceof CSPlayerController ? activator : undefined);',
                 '        if (ctrl && ctrl.IsValid()) ctrl.AddScore(pts);',
                 '    });',
                 '}']
    if speeds:
        body += ['', SPEED_JS.replace('__SPEEDS__', json.dumps(sorted(speeds)))]
    if gravities:
        body += ['', gravity.js_section(gravities)]
    if spawn_equips:
        body += ['', SPAWN_EQUIP_JS.replace('__EQUIPS__', json.dumps(spawn_equips))]
    if equip_items:
        body += ['', ITEMS_JS.replace('__ITEMS__', json.dumps(equip_items, indent=4))]
    return '\n'.join(head + body) + '\n'

SPAWN_EQUIP_JS = r'''// ---------------------------------------------------------------- spawn equips (game_player_equip without "Use Only")
// CS:GO ran these on every spawn ("Strip First" = start with nothing but their items). CS2 doesn't, so each (re)spawning
// player is handled one tick after OnPlayerReset (after CS2 has handed out its default loadout).
/** @type {{ strip: boolean, items: string[] }[]} */
const SPAWN_EQUIPS = __EQUIPS__;
/** @type {Set<CSPlayerPawn>} */
const spawnQueue = new Set();
Instance.OnPlayerReset(({ player }) => {
    if (player && player.IsValid()) { spawnQueue.add(player); wakeThink(); }
});
THINKERS.push(() => {
    for (const pawn of spawnQueue) {
        spawnQueue.delete(pawn);
        if (!pawn.IsValid() || !pawn.IsAlive()) continue;
        for (const eq of SPAWN_EQUIPS) {
            if (eq.strip) pawn.DestroyWeapons();
            for (const item of eq.items) {
                if (!item.startsWith("item_") && (item === "weapon_knife" ? pawn.FindWeaponBySlot(CSGearSlot.KNIFE) : pawn.FindWeapon(item))) continue;
                pawn.GiveNamedItem(item, false);
            }
        }
    }
    return false;
});'''

ITEMS_HEAD = '//   Item_<equip> / ItemAll_<equip>  replaces item_* (armour) in game_player_equips: CS2 crashes on map load with an item in a weapon slot'
ITEMS_JS = r'''// ---------------------------------------------------------------- game_player_equip items (item_assaultsuit, item_kevlar...)
// An item_* in a game_player_equip weapon slot crashes the CS2 server on map load, so the items were taken out of the equips
// and are given from here: every output that triggers the equip also fires Item_<equip> (activator) or ItemAll_<equip>.
/** @type {Record<string, string[]>} */
const EQUIP_ITEMS = __ITEMS__;
function itemPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
function giveItems(pawn, items) {
    if (pawn && pawn.IsValid() && pawn.IsAlive()) for (const it of items) pawn.GiveNamedItem(it, false);
}
for (const [equip, items] of Object.entries(EQUIP_ITEMS)) {
    Instance.OnScriptInput("Item_" + equip, ({ activator }) => giveItems(itemPawn(activator), items));
    Instance.OnScriptInput("ItemAll_" + equip, () => {
        for (let slot = 0; slot < 64; slot++) giveItems(Instance.GetPlayerController(slot)?.GetPlayerPawn(), items);
    });
}'''

def patch_items(js, equip_items):
    """Add (or replace) the equip-items section in an existing <map>_io.js (follow-up pass)."""
    import re
    sec = ITEMS_JS.replace('__ITEMS__', json.dumps(equip_items, indent=4))
    js = js.replace('if (item === "weapon_knife" ? pawn.FindWeaponBySlot', 'if (!item.startsWith("item_") && (item === "weapon_knife" ? pawn.FindWeaponBySlot')
    js = js.replace('pawn.FindWeapon(item)) continue;', 'pawn.FindWeapon(item))) continue;') if 'item.startsWith("item_") && (' in js and 'pawn.FindWeapon(item))) continue;' not in js else js
    if '// ---------------------------------------------------------------- game_player_equip items' in js:
        i = js.index('// ---------------------------------------------------------------- game_player_equip items')
        j = js.find('\n// ----------------------------------------------------------------', i + 10)
        return js[:i] + sec + (js[j:] if j >= 0 else '\n')
    m = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if m:
        names = [x.strip() for x in m.group(1).split(',') if x.strip()]
        for n in ('CSPlayerPawn', 'CSPlayerController'):
            if n not in names: names.append(n)
        js = js[:m.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[m.end():]
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if last_head is not None: lines.insert(last_head + 1, ITEMS_HEAD)
    return '\n'.join(lines) + '\n\n' + sec + '\n'

SPEED_JS = r'''// ---------------------------------------------------------------- player_speedmod replacement (dead in CS2)
// While a player has a multiplier, their ground speed is driven from their own movement keys at 250 x mult.
const BASE_SPEED = 250, WALK_FACTOR = 0.52, DUCK_FACTOR = 0.34;
/** @type {Map<number, number>} player slot -> speed multiplier */
const speedBySlot = new Map();
function speedPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
THINKERS.push(() => {
    for (const [slot, mult] of speedBySlot) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) { speedBySlot.delete(slot); continue; }
        if (!pawn.GetGroundEntity()) continue;
        const fwd = (pawn.IsInputPressed(CSInputs.FORWARD) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.BACK) ? 1 : 0);
        const side = (pawn.IsInputPressed(CSInputs.RIGHT) ? 1 : 0) - (pawn.IsInputPressed(CSInputs.LEFT) ? 1 : 0);
        if (fwd === 0 && side === 0) continue;
        const yaw = pawn.GetEyeAngles().yaw * Math.PI / 180;
        let dx = Math.cos(yaw) * fwd + Math.sin(yaw) * side;
        let dy = Math.sin(yaw) * fwd - Math.cos(yaw) * side;
        const len = Math.hypot(dx, dy); dx /= len; dy /= len;
        let speed = BASE_SPEED * mult;
        if (pawn.IsInputPressed(CSInputs.WALK)) speed *= WALK_FACTOR;
        if (pawn.IsDucking()) speed *= DUCK_FACTOR;
        pawn.Move({ velocity: { x: dx * speed, y: dy * speed, z: pawn.GetAbsVelocity().z } });
    }
    return speedBySlot.size > 0;
});
for (const s of __SPEEDS__) {
    Instance.OnScriptInput("Speed_" + s, ({ activator }) => {
        const pawn = speedPawn(activator);
        const ctrl = pawn ? pawn.GetPlayerController() : undefined;
        if (!ctrl) return;
        if (s === 1) speedBySlot.delete(ctrl.GetPlayerSlot()); else speedBySlot.set(ctrl.GetPlayerSlot(), s);
        wakeThink();
    });
}'''
