"""game_round_end and player_weaponstrip replacements (stage D `roundend` pass).

Neither class is in CS2's .fgd files, so both did nothing in game (autoport's entity check held mg_minecraft_multigames
and mg_nature_multigames for them, 9 Nov 2026).

game_round_end: every EndRound_Draw / EndRound_TerroristsWin / EndRound_CounterTerroristsWin input on one becomes
RunScriptInput RoundEnd_<n>_<Draw|T|CT> on the map's io script. CS:GO's input parameter is a delay in seconds; it is added to
the output's own delay. The script ends the round with FireWinCondition on an info_map_parameters (Hellmatch's verified
method: one is added as `port_map_params` when the map has none, an unnamed one is named). If CS2 hasn't ended the round
1.5 s later (a server with mp_ignore_round_win_conditions 1, warmup), it falls back to mg_mario_party's method: kill the
losing team, then make the winners the no-objective winner and run the round clock out. The entity's OnRoundEnded outputs
fire from the script when that entity ended the round. The game_round_end entities are removed.

player_weaponstrip: Strip / StripWeaponsAndSuit -> RunScriptInput WeaponStrip, which strips the activator
(pawn.DestroyWeapons(), knife included, as CS:GO did). The entities are removed.
"""
import json, re
import dmx

HEAD_LINES = ['//   RoundEnd_<n>_<Draw|T|CT> replaces game_round_end EndRound_* (FireWinCondition, then a forced end)',
              '//   WeaponStrip replaces player_weaponstrip Strip / StripWeaponsAndSuit (activator only)']
MODES = {'endround_draw': 'Draw', 'endround_terroristswin': 'T', 'endround_counterterroristswin': 'CT'}

ROUNDEND_JS = r'''// ---------------------------------------------------------------- game_round_end replacement (not in CS2)
// FireWinCondition on the map's info_map_parameters ends the round with a winner. If the round hasn't ended 1.5 s later
// (mp_ignore_round_win_conditions 1, warmup), kill the losing team, then make the winners the team that wins when the
// clock runs out, and run it out (mg_mario_party's method).
const ROUNDEND_PARAMS = __PARAMS__;
/** @type {Record<string, { mode: string, after: { t: string, i: string, p: string, d: number }[] }>} */
const ROUNDEND = __ROUNDEND__;
let roundEndOver = false;
let roundEndCvar = false;
/** @param {number} team */
function roundEndKillTeam(team) {
    for (let slot = 0; slot < 64; slot++) {
        const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
        if (pawn && pawn.IsValid() && pawn.IsAlive() && pawn.GetTeamNumber() === team)
            pawn.TakeDamage({ damage: 100000, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR });
    }
}
/** @param {string} key */
async function roundEnd(key) {
    const r = ROUNDEND[key];
    if (!r || roundEndOver) return;
    const reason = r.mode === 'T' ? CSRoundEndReason.TERRORISTS_WIN : r.mode === 'CT' ? CSRoundEndReason.CTS_WIN : CSRoundEndReason.DRAW;
    Entities.FireInput({ name: ROUNDEND_PARAMS, input: "FireWinCondition", value: reason });
    for (const o of r.after) Entities.FireInput({ name: o.t, input: o.i, value: o.p, delay: o.d });
    await Instance.Delay(1.5);
    if (roundEndOver) return;
    if (r.mode !== 'Draw') {
        const winner = r.mode === 'T' ? 2 : 3;
        roundEndKillTeam(winner === 2 ? 3 : 2);
        await Instance.Delay(1.0);
        if (roundEndOver) return;
        Console.ServerCommand(`mp_default_team_winner_no_objective ${winner}`);
        roundEndCvar = true;
    }
    GameRules.SetRoundRemainingTime(0);
}
for (const key of Object.keys(ROUNDEND)) Instance.OnScriptInput("RoundEnd_" + key, () => { roundEnd(key); });
Instance.OnRoundStart(() => { roundEndOver = false; });
Instance.OnRoundEnd(() => {
    roundEndOver = true;
    if (roundEndCvar) { Console.ServerCommand("mp_default_team_winner_no_objective -1"); roundEndCvar = false; }
});'''

STRIP_JS = r'''// ---------------------------------------------------------------- player_weaponstrip replacement (not in CS2)
Instance.OnScriptInput("WeaponStrip", ({ activator }) => {
    const pawn = activator instanceof CSPlayerPawn ? activator : activator instanceof CSPlayerController ? activator.GetPlayerPawn() : undefined;
    if (pawn && pawn.IsValid() && pawn.IsAlive()) pawn.DestroyWeapons();
});'''


def run(m, c):
    """Convert the map's game_round_end / player_weaponstrip. Sets c.roundend = {key: {...}} and c.weaponstrip = bool, c.map_params = name."""
    c.roundend = {}; c.weaponstrip = False; c.map_params = None
    ends = m.by_class('game_round_end'); strips = m.by_class('player_weaponstrip')
    if not ends and not strips: return
    if ends:
        names = {}
        for i, e in enumerate(ends):
            if m.name(e): names.setdefault(m.name(e).lower(), []).append((i, e))
        n = 0
        for src, cc in list(m.all_conns()):
            t = dmx.get(cc, b'targetName').decode().lower(); inp = dmx.get(cc, b'inputName').decode().lower()
            if t not in names or inp not in MODES: continue
            i, e = names[t][0]
            key = '%d_%s' % (i, MODES[inp])
            if key not in c.roundend:
                after = []
                for oc in m.conns(e):
                    if dmx.get(oc, b'outputName').decode().lower() == 'onroundended':
                        after.append({'t': dmx.get(oc, b'targetName').decode(), 'i': dmx.get(oc, b'inputName').decode(),
                                      'p': dmx.get(oc, b'overrideParam').decode(), 'd': round(float(dmx.get(oc, b'delay') or 0), 3)})
                c.roundend[key] = {'mode': MODES[inp], 'after': after}
            try: extra = float(dmx.get(cc, b'overrideParam').decode() or 0)
            except ValueError: extra = 0.0
            dmx.set_(cc, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
            dmx.set_(cc, b'overrideParam', dmx.T_STR, ('RoundEnd_' + key).encode())
            dmx.set_(cc, b'delay', dmx.T_FLOAT, float(dmx.get(cc, b'delay') or 0) + max(extra, 0.0)); n += 1
        unused = [m.name(e) or '(unnamed)' for i, e in enumerate(ends) if not any(k.startswith('%d_' % i) for k in c.roundend)]
        for e in ends: m.remove_node(e)
        c.log.append('removed %d game_round_end (not in CS2); %d EndRound_* inputs -> script RoundEnd_<n>_<mode> (FireWinCondition, forced end as fallback)%s'
                     % (len(ends), n, '; never triggered, dropped: ' + ', '.join(unused) if unused else ''))
        if c.roundend:
            mp = m.by_class('info_map_parameters')
            if mp:
                if not m.name(mp[0]): m.setp(mp[0], 'targetname', 'port_map_params')
                c.map_params = m.name(mp[0])
            else:
                o = m.origin(ends[0])
                m.new_entity('info_map_parameters', o, {'targetname': 'port_map_params'})
                c.map_params = 'port_map_params'; c.log.append('added info_map_parameters port_map_params (FireWinCondition target for the round ends)')
            c.todo.append('roundend: check a scripted round end in game (FireWinCondition, then the forced fallback if a server blocks it)')
    if strips:
        names = set(m.name(e).lower() for e in strips if m.name(e)); n = 0
        for src, cc in list(m.all_conns()):
            if dmx.get(cc, b'targetName').decode().lower() in names and dmx.get(cc, b'inputName').decode().lower() in ('strip', 'stripweaponsandsuit'):
                dmx.set_(cc, b'targetName', dmx.T_STR, c.script.encode()); dmx.set_(cc, b'inputName', dmx.T_STR, b'RunScriptInput')
                dmx.set_(cc, b'overrideParam', dmx.T_STR, b'WeaponStrip'); n += 1
        for e in strips: m.remove_node(e)
        c.weaponstrip = n > 0
        c.log.append('removed %d player_weaponstrip (not in CS2); %d Strip inputs -> script WeaponStrip (strips the activator)' % (len(strips), n))


def _patch_script(js, c):
    """Add the round-end / strip sections to an <addon>_io.js (or start one)."""
    need = [x for x in ('CSPlayerPawn', 'CSPlayerController', 'CSDamageFlags', 'CSRoundEndReason') if c.roundend or x in ('CSPlayerPawn', 'CSPlayerController')]
    mt = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if mt:
        names = [x.strip() for x in mt.group(1).split(',') if x.strip()]
        names += [n for n in need if n not in names]
        js = js[:mt.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[mt.end():]
    else:
        js = 'import { %s } from "cs_script/point_script";\n\n' % ', '.join(['Instance'] + need) + js
    js = re.sub(r'\n// -{10,} game_round_end replacement.*?\n\}\);(?=\n|$)', '', js, flags=re.S)        # rerun-safe
    js = re.sub(r'\n// -{10,} player_weaponstrip replacement.*?\n\}\);(?=\n|$)', '', js, flags=re.S)
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    for h in HEAD_LINES[::-1]:
        if h not in lines and last_head is not None: lines.insert(last_head + 1, h)
    js = '\n'.join(lines) + '\n'
    if c.roundend:
        js += '\n' + ROUNDEND_JS.replace('__PARAMS__', json.dumps(c.map_params)).replace('__ROUNDEND__', json.dumps(c.roundend, indent=4)) + '\n'
    if c.weaponstrip: js += '\n' + STRIP_JS + '\n'
    return js


def patch_script(*a, **k):
    """_patch_script, then the import line made to name every API global the script uses (Entities, Console, GameRules)."""
    import jsapi
    return jsapi.ensure_imports(_patch_script(*a, **k))
