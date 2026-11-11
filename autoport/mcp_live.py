"""Live-game tools for tools/mcp_server.py: its loader imports any autoport/*.py that defines MCP_TOOLS and adds the tools.

Each call opens its own console connection and closes it before returning: CS2 answers one console client at a time, so
an MCP server must not sit on the slot between calls (cs2-map-mcp closes its shared connection after 5 s idle for the
same reason). Calls that use the game take the cs2live.exclusive lock, so autoport, a review session and the MCP don't
drive the same CS2 at once. Nothing launches CS2 except game_launch with dry_run=false, and nothing takes focus unless a
call passes allow_focus=true (refused while someone uses the PC). Tool names follow cs2-map-mcp's (game_command,
game_screenshot, game_reset, game_crash_report, playtest, script_test, route_test, physics_probe ...).

Written by Claude (AI) for skink52's autoport; not hand-written.
"""
from __future__ import annotations

import contextlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)
import crashdump  # noqa: E402
import cs2live  # noqa: E402
import ingame_check  # noqa: E402
import livetest  # noqa: E402
import vconsole  # noqa: E402

OUT = ingame_check.OUT
CONN = {'port': {'type': 'integer', 'description': 'VConsole2 port (Workshop Tools)', 'default': vconsole.PORT},
        'netcon': {'type': 'integer', 'description': 'plain-text netcon port (a client started with -netconport) instead of VConsole2'}}
VEC = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 3, 'maxItems': 3}


@contextlib.contextmanager
def _game(port=vconsole.PORT, netcon=None, addon=None, owner='mcp'):
    g = cs2live.connect(port, netcon, addon)
    try:
        with cs2live.exclusive(owner, wait=60):
            yield g
    finally:
        g.c.close()


def _short(lines, n=60):
    return [l[:300] for l in lines[-n:]]


# ------------------------------------------------------------------ console
def game_status(port=vconsole.PORT, netcon=None):
    p = netcon or port
    out = {'console_port': p, 'reachable': vconsole.reachable(port=p), 'cs2': cs2live.cs2_processes(),
           'vconsole_windows': cs2live.close_vconsole_windows(confirm=False)}
    if out['reachable']:
        with vconsole.Console(port=p, netcon=bool(netcon)) as c:
            out['ping_seconds'] = c.ping(10)
            out['addon'] = getattr(c.wire, 'addon', None)
            if out['ping_seconds'] is None:
                out['holders'] = vconsole.holders(p)
    return out


def game_command(commands, wait=1.5, port=vconsole.PORT, netcon=None):
    cmds = [c for c in re.split(r';;|\n', commands) if c.strip()]
    with _game(port, netcon, owner='mcp game_command') as g:
        return {'lines': _short(g.command(cmds, wait=float(wait)), 400)}


def game_tail(seconds=10, grep=None, port=vconsole.PORT, netcon=None):
    rx = re.compile(grep) if grep else None
    with vconsole.Console(port=netcon or port, netcon=bool(netcon)) as c:
        c.ping(10)
        at = c.cursor()
        try:
            c.wait_for(lambda t: False, min(float(seconds), 120))
        except vconsole.ConsoleError as e:
            return {'lines': c.texts(at)[-400:], 'closed': str(e)}
        lines = [t for t in c.texts(at) if rx is None or rx.search(t)]
    return {'lines': _short(lines, 400)}


def game_wait(regex, timeout=60, send=None, port=vconsole.PORT, netcon=None):
    with vconsole.Console(port=netcon or port, netcon=bool(netcon)) as c:
        c.ping(10)
        at = c.cursor()
        if send:
            c.send([x for x in re.split(r';;|\n', send) if x.strip()])
        hit = c.wait_for(regex, min(float(timeout), 600), since=at)
    return {'found': bool(hit), 'line': hit.text if hit else None}


# ------------------------------------------------------------------ process
def game_launch(addon, hammer_map=None, netcon=None, dry_run=True):
    argv = cs2live.launch_command(addon, hammer_map=hammer_map, netcon=netcon)
    if dry_run:
        return {'dry_run': True, 'argv': argv, 'note': 'starts minimised and not activated; refused while any CS2 runs'}
    return cs2live.launch(addon, hammer_map=hammer_map, netcon=netcon, port=netcon or vconsole.PORT)


def game_stop(pid):
    return {'result': cs2live.stop(int(pid))}


# ------------------------------------------------------------------ map and player
def game_load_map(addon, map, plain=False, timeout=150, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, addon, 'mcp game_load_map') as g:
        r = g.load_map(map, addon, plain=bool(plain), timeout=float(timeout))
    lines = r.pop('lines', [])
    r['problems'] = ingame_check.classify(lines, names=(addon, map))
    r['console_lines'] = len(lines)
    return r


def game_reset(port=vconsole.PORT, netcon=None):
    with _game(port, netcon, owner='mcp game_reset') as g:
        return g.reset()


def game_screenshot(name='view', pos=None, ang=None, method='console', hide_hud=True, allow_focus=False, folder=None,
                    port=vconsole.PORT, netcon=None):
    folder = folder or os.path.join(OUT, 'frames')
    with _game(port, netcon, owner='mcp game_screenshot') as g:
        if pos is None and ang is None and method == 'console':
            return {'path': g.console_screenshot('autoport_' + re.sub(r'[^\w.-]', '_', name))}
        return g.views([{'name': name, 'pos': pos, 'ang': ang}], folder, method, bool(hide_hud), bool(allow_focus))


def game_crash_report(dump=None, since_seconds=None):
    import time
    path = dump or crashdump.newest(since=time.time() - float(since_seconds) if since_seconds else None)
    if not path:
        return {'crash': False, 'folder': crashdump.GAME_BIN}
    r = crashdump.report(path if os.path.isabs(path) else os.path.join(crashdump.GAME_BIN, path))
    r['console_tail'] = r['console_tail'][-15:]
    return {'crash': True, **r}


# ------------------------------------------------------------------ tests
def ingame_check_tool(addon, map=None, seconds=20, screenshot=False, views=False, bots=0, play=0, plain=False, no_load=False,
                      port=vconsole.PORT, netcon=None):
    r = ingame_check.check(addon, map, float(seconds), port, netcon, bool(screenshot), bool(views), int(bots), int(play),
                           bool(plain), bool(no_load))
    return {k: r.get(k) for k in ('exit', 'skipped', 'load', 'crash', 'notes', 'report', 'screenshot', 'views', 'playtest')}


def playtest_tool(addon, map, bots=10, seconds=60, spectate=True, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, addon, 'mcp playtest') as g:
        return livetest.playtest(g, map, int(bots), int(seconds), bool(spectate), OUT, addon)


def mode_playtest_tool(addon, map, game_type, game_mode, bots=10, seconds=30, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, addon, 'mcp mode_playtest') as g:
        return livetest.mode_playtest(g, addon, map, int(game_type), int(game_mode), int(bots), int(seconds), OUT)


def script_test(addon, map, steps, timeout=90, allow_focus=False, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, addon, 'mcp script_test') as g:
        if not cs2live.status_has_map(g.status(), map):
            load = g.load_map(map, addon)
            if not load['ok']:
                return {'ok': False, 'reason': load['reason']}
        return livetest.scenario(g, steps, float(timeout), bool(allow_focus), OUT)


def route_test(waypoints, radius=20, within=15, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, owner='mcp route_test') as g:
        done = []
        for i, w in enumerate(waypoints):
            issue = livetest.walk_to(g, w, float(radius), float(within))
            done.append({'waypoint': i, 'goal': w, 'reason': issue, 'eye': g.getpos()})
            if issue:
                return {'ok': False, 'failed_at': i, 'steps': done}
        return {'ok': True, 'steps': done}


def timings(start, goal, within=30, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, owner='mcp timings') as g:
        return livetest.timing(g, start, goal, float(within))


def physics_probe(names, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, owner='mcp physics_probe') as g:
        return livetest.physics_probe(g, names)


def probe_script(action, addon, compile=False):
    if action == 'install':
        return livetest.probe_install(addon, bool(compile))
    if action == 'remove':
        return {'removed': livetest.probe_remove(addon)}
    raise ValueError('action: install or remove')


def player_marks(action='harvest', key='F8', seconds=3, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, owner='mcp player_marks') as g:
        if action == 'install':
            return {'key': livetest.marks_install(g, key)}
        g.c.wait_for(lambda t: False, float(seconds))
        return {'marks': livetest.marks_harvest(g.c.since(0))}


def script_reload(targetname, cs_script, keyvalues=None, port=vconsole.PORT, netcon=None):
    with _game(port, netcon, owner='mcp script_reload') as g:
        return {'console': livetest.script_reload(g, targetname, cs_script, keyvalues or {})}


# What each tool can do to files and to the running game, for the MCP annotations. READ_ONLY: only reads the console, dumps or state.
# DESTRUCTIVE: can replace or delete files (probe_script and player_marks write into the addon / CS2 cfg and remove them again), or can do
# anything at all (game_command, and game_wait's `send`, run any console command), or end a running program (game_stop kills the CS2 that
# game_launch started: whatever that session had not saved is gone). The rest change the running game or add a file (a screenshot), nothing more.
READ_ONLY = {'game_status', 'game_tail', 'game_crash_report', 'physics_probe'}
DESTRUCTIVE = {'game_command', 'game_wait', 'game_stop', 'probe_script', 'player_marks'}


def _tool(name, fn, description, props=None, required=(), conn=True):
    p = dict(props or {})
    if conn:
        p.update(CONN)
    return {'name': name, 'description': description, 'fn': fn,
            'inputSchema': {'type': 'object', 'properties': p, 'required': list(required), 'additionalProperties': False},
            'annotations': {'readOnlyHint': name in READ_ONLY, 'destructiveHint': name in DESTRUCTIVE, 'openWorldHint': False}}


S, I, N, B = ({'type': 'string'}, {'type': 'integer'}, {'type': 'number'}, {'type': 'boolean'})
MCP_TOOLS = [
    _tool('game_status', game_status, 'Is a CS2 console open? Console port reachable, echo round trip, the addon of the session, '
          'running cs2.exe processes and their mode, VConsole2 windows that would hold the single console slot.'),
    _tool('game_command', game_command, 'Run CS2 console commands (separated by ;; or newlines) and return what they printed, '
          'map script output (Instance.Msg) included. wait: extra seconds for server output printed a frame later.',
          {'commands': S, 'wait': N}, ['commands']),
    _tool('game_tail', game_tail, 'Read the live console for N seconds (max 120), optionally filtered by a regex.',
          {'seconds': N, 'grep': S}),
    _tool('game_wait', game_wait, 'Wait until a console line matches a regex (optionally after sending commands); found and the line.',
          {'regex': S, 'timeout': N, 'send': S}, ['regex']),
    _tool('game_launch', game_launch, 'Start CS2 Workshop Tools with an addon, minimised and not activated. dry_run (default true) '
          'only returns the command line. Refused while any CS2 runs.',
          {'addon': S, 'hammer_map': S, 'netcon': I, 'dry_run': B}, ['addon'], conn=False),
    _tool('game_stop', game_stop, 'Stop a CS2 that game_launch started (never another one, never with unsaved Hammer edits).',
          {'pid': I}, ['pid'], conn=False),
    _tool('game_load_map', game_load_map, 'Load an addon map (map_workshop <addon> <map>; plain=true sends map <name>), wait for a '
          'live player, return timing and the console problems sorted into autoport kinds.',
          {'addon': S, 'map': S, 'plain': B, 'timeout': N}, ['addon', 'map']),
    _tool('game_reset', game_reset, 'Undo test changes: keys released, noclip off, HUD on, default recoil, bots kicked, round restart.'),
    _tool('game_screenshot', game_screenshot, 'Screenshot. method console (jpeg_screenshot, no focus) or window (PrintWindow PNG with '
          'a blank/stale frame check). pos (feet) and ang move a noclip camera first. allow_focus brings the window forward '
          '(refused while someone uses the PC).',
          {'name': S, 'pos': VEC, 'ang': VEC, 'method': {'type': 'string', 'enum': ['console', 'window']}, 'hide_hud': B,
           'allow_focus': B, 'folder': S}),
    _tool('game_crash_report', game_crash_report, 'Newest CS2 minidump (or a named one): exception, module+offset, pid, hint, '
          'console lines found in the dump. since_seconds limits it to a recent dump.', {'dump': S, 'since_seconds': N}, conn=False),
    _tool('ingame_check', ingame_check_tool, "autoport's in-game check: load the map, read the console for N seconds, sort errors "
          '(missing resources, script and entity errors, failed loads, crash dump), write the report. Skips if no console is open.',
          {'addon': S, 'map': S, 'seconds': N, 'screenshot': B, 'views': B, 'bots': I, 'play': I, 'plain': B, 'no_load': B}, ['addon']),
    _tool('playtest', playtest_tool, 'Bounded bot match on the map (local player spectates): status samples, errors, script errors.',
          {'addon': S, 'map': S, 'bots': I, 'seconds': I, 'spectate': B}, ['addon', 'map']),
    _tool('mode_playtest', mode_playtest_tool, 'Bot match in a native mode (game_type/game_mode), with the mode cvars restored and checked.',
          {'addon': S, 'map': S, 'game_type': I, 'game_mode': I, 'bots': I, 'seconds': I}, ['addon', 'map', 'game_type', 'game_mode']),
    _tool('script_test', script_test, 'Real-input scenario: steps like {"fire": "door Open"}, {"expect": regex}, {"hold": {"key": '
          '"use", "seconds": 1}}, {"aim": [x,y,z]}, {"go": [x,y,z]}, {"shot": name}; mouse/click/focus need allow_focus. '
          'Keys are always released; returns checks, script errors and frames.',
          {'addon': S, 'map': S, 'steps': {'type': 'array', 'items': {'type': 'object'}}, 'timeout': N, 'allow_focus': B},
          ['addon', 'map', 'steps']),
    _tool('route_test', route_test, 'Walk waypoints (feet positions) with real movement keys; stops at the first one not reached.',
          {'waypoints': {'type': 'array', 'items': VEC}, 'radius': N, 'within': N}, ['waypoints']),
    _tool('timings', timings, 'Seconds on foot from start to goal (setpos at start, then real keys).', {'start': VEC, 'goal': VEC, 'within': N},
          ['start', 'goal']),
    _tool('physics_probe', physics_probe, 'Live state of named entities (count, class, origin, velocity, health). Needs probe_script install.',
          {'names': {'type': 'array', 'items': {'type': 'string'}}}, ['names']),
    _tool('probe_script', probe_script, 'Install (and optionally compile) or remove the autoport probe cs_script in an addon. Remove it '
          'before a Workshop upload.', {'action': {'type': 'string', 'enum': ['install', 'remove']}, 'addon': S, 'compile': B},
          ['action', 'addon'], conn=False),
    _tool('player_marks', player_marks, 'Tester marks: install binds a key that logs position, map and a frame; harvest reads the marks '
          '(and the chat notes typed after each) from the console.',
          {'action': {'type': 'string', 'enum': ['install', 'harvest']}, 'key': S, 'seconds': N}),
    _tool('script_reload', script_reload, 'Restart a point_script (Kill + ent_create) without reloading the map.',
          {'targetname': S, 'cs_script': S, 'keyvalues': {'type': 'object'}}, ['targetname', 'cs_script']),
]
