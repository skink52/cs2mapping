"""game_ui -> cs_script (stage D pass `gameui`). CS2 still has game_ui in the FGD but none of its outputs fire.

Every game_ui becomes a table entry in <addon>_io.js. Outputs that sent Activate / Deactivate to it now send
RunScriptInput GameUIOn_<name> / GameUIOff_<name> to the io script (activator kept). While a player holds a game_ui, the
script polls their keys every tick and fires the game_ui's own outputs on each change, with the same targets, inputs,
parameters and delays: PlayerOn/PlayerOff, Pressed/Unpressed Forward/Back/MoveLeft/MoveRight/Attack/Attack2, and the axis
outputs XAxis (left -1 / right 1), YAxis (back -1 / forward 1), AttackAxis / Attack2Axis (0 / 1), which pass the axis value
when the output has no parameter. Spawnflags: 32 Freeze Player (move type NONE while held), 128 +Use and 256 Jump deactivate
(ignored for the first 0.5 s), 64 Hide Weapon and FieldOfView are not emulated. Death or disconnect releases the controls.
The game_ui entities are removed from the vmap."""
import json, re
import dmx

OUTS = ['PlayerOn', 'PlayerOff', 'PressedForward', 'UnpressedForward', 'PressedBack', 'UnpressedBack', 'PressedMoveLeft',
        'UnpressedMoveLeft', 'PressedMoveRight', 'UnpressedMoveRight', 'PressedAttack', 'UnpressedAttack', 'PressedAttack2',
        'UnpressedAttack2', 'XAxis', 'YAxis', 'AttackAxis', 'Attack2Axis']
HEAD_LINE = '//   GameUIOn_<name> / GameUIOff_<name>  replaces game_ui (Activate / Deactivate): keys polled every tick, outputs fired from here'


def run(m, c):
    uis = {}
    for e in m.by_class('game_ui'):
        name = m.name(e)
        if not name: continue
        outs = []
        for cn in m.conns(e):
            o, t, i, p, d, n = m.conn_tuple(cn)
            if o in OUTS: outs.append([o, t, i, p, d])
            else: c.todo.append('game_ui %s output %s -> %s.%s not emulated' % (name, o, t, i))
        uis[name] = {'flags': int(float(m.P(e, 'spawnflags', '0') or 0)), 'outs': outs}
        if float(m.P(e, 'FieldOfView', '-1') or -1) > -1:
            c.todo.append('game_ui %s had FieldOfView %s (looking away deactivated it in CS:GO; not emulated)' % (name, m.P(e, 'FieldOfView')))
    if not uis: return {}
    low = {k.lower(): k for k in uis}
    n = 0
    for e, cn in list(m.all_conns()):
        o, t, i, p, d, times = m.conn_tuple(cn)
        k = low.get(t.lower())
        if k is None: continue
        if i.lower() in ('activate', 'deactivate'):
            dmx.set_(cn, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cn, b'inputName', dmx.T_STR, b'RunScriptInput')
            dmx.set_(cn, b'overrideParam', dmx.T_STR, ('GameUI%s_%s' % ('On' if i.lower() == 'activate' else 'Off', k)).encode()); n += 1
        else:
            c.todo.append('%s output %s -> game_ui %s.%s not converted' % (m.name(e) or m.cls(e), o, k, i))
    for e in m.by_class('game_ui'):
        if m.name(e) in uis: m.remove_node(e)
    held = sum(1 for u in uis.values() if u['flags'] & 32)
    c.log.append('%d game_ui -> script (%d Activate/Deactivate outputs -> GameUIOn_/GameUIOff_; %d freeze the player while held; %d outputs fired from the key poll)'
                 % (len(uis), n, held, sum(len(u['outs']) for u in uis.values())))
    c.gameuis = uis
    return uis


JS = r'''// ---------------------------------------------------------------- game_ui replacement (outputs never fire in CS2)
// GameUIOn_<name> / GameUIOff_<name> take the activator as the driver. While held, the driver's keys are polled every tick and
// the game_ui's outputs fire on each change (axis outputs pass -1/0/1 unless the output had a parameter). Freeze Player = move
// type NONE while held; +use / jump deactivate when the game_ui had those flags. Several game_uis can share one driver.
/** @type {Record<string, { flags: number, outs: [string, string, string, string, number][] }>} */
const GAMEUI = __UIS__;
/** @type {Map<string, { pawn: CSPlayerPawn, since: number, keys: Record<string, boolean> }>} */
const gameuiHeld = new Map();
/** @type {[string, CSInputs][]} */
const GAMEUI_KEYS = [["Forward", CSInputs.FORWARD], ["Back", CSInputs.BACK], ["MoveLeft", CSInputs.LEFT], ["MoveRight", CSInputs.RIGHT],
    ["Attack", CSInputs.ATTACK], ["Attack2", CSInputs.ATTACK2]];
function gameuiPawn(ent) {
    if (ent instanceof CSPlayerPawn) return ent;
    if (ent instanceof CSPlayerController) return ent.GetPlayerPawn();
    return undefined;
}
/** @param {string} ui @param {string} out @param {CSPlayerPawn} pawn @param {string} [value] */
function gameuiFire(ui, out, pawn, value) {
    for (const [o, target, input, param, delay] of GAMEUI[ui].outs) {
        if (o !== out) continue;
        const v = param !== "" ? param : (value ?? "");
        if (target.toLowerCase() === "!activator") Instance.EntFireAtTarget({ target: pawn, input, value: v, activator: pawn, delay });
        else Instance.EntFireAtName({ name: target, input, value: v, activator: pawn, delay });
    }
}
/** @param {string} ui */
function gameuiRelease(ui) {
    const h = gameuiHeld.get(ui);
    if (!h) return;
    gameuiHeld.delete(ui);
    const p = h.pawn;
    for (const [key] of GAMEUI_KEYS) if (h.keys[key]) gameuiFire(ui, "Unpressed" + key, p);
    if (h.keys.MoveLeft || h.keys.MoveRight) gameuiFire(ui, "XAxis", p, "0");
    if (h.keys.Forward || h.keys.Back) gameuiFire(ui, "YAxis", p, "0");
    if (h.keys.Attack) gameuiFire(ui, "AttackAxis", p, "0");
    if (h.keys.Attack2) gameuiFire(ui, "Attack2Axis", p, "0");
    gameuiFire(ui, "PlayerOff", p);
    const stillFrozen = [...gameuiHeld].some(([u, o]) => o.pawn === p && (GAMEUI[u].flags & 32));
    if (GAMEUI[ui].flags & 32 && !stillFrozen && p.IsValid() && p.GetMoveType() === CSMoveType.NONE) p.SetMoveType(CSMoveType.WALK);
}
for (const ui of Object.keys(GAMEUI)) {
    Instance.OnScriptInput("GameUIOn_" + ui, ({ activator }) => {
        const pawn = gameuiPawn(activator);
        if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) return;
        const cur = gameuiHeld.get(ui);
        if (cur && cur.pawn === pawn) return;
        if (cur) gameuiRelease(ui);
        gameuiHeld.set(ui, { pawn, since: Instance.GetGameTime(), keys: {} });
        if (GAMEUI[ui].flags & 32) pawn.SetMoveType(CSMoveType.NONE);
        gameuiFire(ui, "PlayerOn", pawn);
        wakeThink();
    });
    Instance.OnScriptInput("GameUIOff_" + ui, () => gameuiRelease(ui));
}
THINKERS.push(() => {
    const now = Instance.GetGameTime();
    for (const [ui, h] of [...gameuiHeld]) {
        const p = h.pawn, f = GAMEUI[ui].flags;
        if (!p.IsValid() || !p.IsAlive()) { gameuiRelease(ui); continue; }
        if (now - h.since > 0.5 && ((f & 128 && p.IsInputPressed(CSInputs.USE)) || (f & 256 && p.IsInputPressed(CSInputs.JUMP)))) { gameuiRelease(ui); continue; }
        const was = { ...h.keys };
        for (const [key, bit] of GAMEUI_KEYS) {
            const down = p.IsInputPressed(bit);
            if (down !== !!h.keys[key]) { h.keys[key] = down; gameuiFire(ui, (down ? "Pressed" : "Unpressed") + key, p); }
        }
        const ax = (k) => (k.MoveRight ? 1 : 0) - (k.MoveLeft ? 1 : 0), ay = (k) => (k.Forward ? 1 : 0) - (k.Back ? 1 : 0);
        if (ax(was) !== ax(h.keys)) gameuiFire(ui, "XAxis", p, String(ax(h.keys)));
        if (ay(was) !== ay(h.keys)) gameuiFire(ui, "YAxis", p, String(ay(h.keys)));
        if (!!was.Attack !== !!h.keys.Attack) gameuiFire(ui, "AttackAxis", p, h.keys.Attack ? "1" : "0");
        if (!!was.Attack2 !== !!h.keys.Attack2) gameuiFire(ui, "Attack2Axis", p, h.keys.Attack2 ? "1" : "0");
    }
    return gameuiHeld.size > 0;
});'''


def js_section(uis):
    return JS.replace('__UIS__', json.dumps(uis, indent=1))


def patch_script(js, uis, think_js):
    """add (or replace) the game_ui section in an existing <addon>_io.js"""
    if 'const GAMEUI = ' in js:
        return re.sub(r'const GAMEUI = .*?;\n/\*\* @type \{Map', 'const GAMEUI = %s;\n/** @type {Map' % json.dumps(uis, indent=1), js, flags=re.S)
    mm = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    need = ('Instance', 'CSPlayerPawn', 'CSPlayerController', 'CSInputs', 'CSMoveType')
    if mm:
        names = [x.strip() for x in mm.group(1).split(',') if x.strip()]
        for n in need:
            if n not in names: names.append(n)
        js = js[:mm.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[mm.end():]
    else:
        js = 'import { %s } from "cs_script/point_script";\n\n' % ', '.join(need) + js
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    js = '\n'.join(lines) + '\n'
    if 'const THINKERS' not in js: js += '\n' + think_js + '\n'
    return js + '\n' + js_section(uis) + '\n'
