"""Tests in the running game: bot playtests, real-input scenarios, walking a route with real movement keys, spawn-to-goal
timings, entity probes, tester marks (one key per problem spot), restarting a map script without a reload. Stdlib only.

  python livetest.py reset
  python livetest.py playtest <addon> <map> [--bots 10] [--seconds 60] [--player]
  python livetest.py mode <addon> <map> --game-type 1 --game-mode 2 [--bots 10] [--seconds 30]
  python livetest.py scenario <addon> <map> steps.json [--focus]
  python livetest.py walk X Y Z [--within 15] [--radius 20]
  python livetest.py timing <addon> <map> --start X Y Z --goal X Y Z
  python livetest.py probe install|remove <addon> [--compile]    (needed by: physics, alive counts)
  python livetest.py physics <name> [<name>...]
  python livetest.py marks install [--key F8] | harvest [--seconds 5]
  python livetest.py reload <targetname> <cs_script path> [key=value...]
  common: --port 29000 | --netcon PORT, --out DIR (logs and frames)

All need CS2 already running with its console open (Workshop Tools, or -netconport). Nothing here launches the game or
takes focus unless told to (--focus, and then only while nobody uses the PC). Mirrors the live tests of
Rmgs123/cs2-map-mcp (MIT; playtest.py, scripting.py script_test, route.py, competitive.py comp_timings, modes.py
mode_playtest, physics.py physics_probe, marks.py, scripting.py script_reload; commit 07e8ca3), re-written: that project
reads player state from its own compiled point_script; here getpos/status are the default and the probe is optional.

Written by Claude (AI) for skink52's autoport; not hand-written.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)   # appended: inside tools/mcp_server.py, tools/ modules keep priority
import cs2live  # noqa: E402
import vconsole  # noqa: E402
from cs2live import CS2, GameError  # noqa: E402

# keys a scenario may hold: our name -> CS2 console button (scripting.py:445-448; CS2's +left is a strafe)
KEYS = {'attack': 'attack', 'attack2': 'attack2', 'use': 'use', 'forward': 'forward', 'back': 'back', 'left': 'left',
        'right': 'right', 'jump': 'jump', 'duck': 'duck', 'reload': 'reload', 'walk': 'sprint', 'turnleft': 'turnleft',
        'turnright': 'turnright'}
STEP_KINDS = ('cmd', 'say', 'fire', 'press', 'walk', 'go', 'wait', 'expect', 'shot', 'use', 'hold', 'aim', 'mouse', 'click', 'focus')
WAIT_AFTER = ('cmd', 'say', 'fire', 'press')
ENGINE_NOISE = re.compile(r'^Graph Warning: animation/graphs/|Failed to set animgraph param e_(?:face|body)_idle|^Annotation:')
SCRIPT_ERROR = re.compile(r'Uncaught|(?:Type|Reference|Syntax|Range|Internal)Error|Invalid module specifier|'
                          r'Failed to (?:load|compile).*script|invoked on an invalid entity|Couldn\'t find output named', re.I)


def script_errors(lines) -> list[str]:
    """Script failures in console text (scripting.py:525-540, plus the 5 Nov 2026 API messages, cs_script-notes.md)."""
    out = []
    for i, ln in enumerate(lines):
        if ln.lower().startswith('annotation:'):
            continue
        if 'Uncaught' in ln and i + 1 < len(lines) and not lines[i + 1].lstrip().startswith('at '):
            ln = ln + ' ' + lines[i + 1].strip()
        if SCRIPT_ERROR.search(ln) and ln not in out:
            out.append(ln)
    return out


def errors(lines) -> list[str]:
    """Problem-looking lines (playtest.py:25-34): error / failed / missing, not 'terrorist', not '0 errors'."""
    out = []
    for ln in lines:
        low = ln.lower()
        if low.startswith('annotation:') or ENGINE_NOISE.search(ln):
            continue
        if re.search(r'error|failed|missing', low) and 'terrorist' not in low and not re.search(r'(errors|failed|missing):? 0\b|no errors', low):
            out.append(ln)
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------ the optional probe script
PROBE_REL = 'scripts/autoport_probe/autoport_probe'     # under the content addon; remove() takes it out before upload
PROBE_JS = r'''import { Instance } from "cs_script/point_script";
// autoport live probe (skink52): authoritative player and entity state over the console. Remove before upload.
const r = (x) => Math.round(x * 100) / 100;
const v3 = (v) => v ? [r(v.x), r(v.y), r(v.z)] : null;
Instance.RegisterCheatCommand("ap_probe_players", (args) => {
  const token = args.trim();
  let n = 0;
  for (const c of Instance.GetAllPlayerControllers()) {
    if (!c.IsConnected()) continue;
    const p = c.GetPlayerPawn(), ok = !!p && p.IsValid();
    Instance.Msg("AP_PLAYER " + token + " " + JSON.stringify({slot: c.GetPlayerSlot(), bot: c.IsBot(), team: c.GetTeamNumber(),
      alive: ok && p.IsAlive(), health: ok ? p.GetHealth() : 0, noclip: ok ? p.IsNoclipping() : false, pos: ok ? v3(p.GetAbsOrigin()) : null}));
    n++;
  }
  Instance.Msg("AP_PLAYERS_END " + token + " " + JSON.stringify({map: Instance.GetMapName(), count: n, freeze: Instance.IsFreezePeriod(), warmup: Instance.IsWarmupPeriod()}));
});
Instance.RegisterCheatCommand("ap_probe_entities", (args) => {
  const [token, ...names] = args.trim().split(/\s+/);
  for (const name of names) {
    const found = Instance.FindEntitiesByName(name).filter((e) => e.IsValid());
    if (!found.length) Instance.Msg("AP_ENTITY " + token + " " + JSON.stringify({name, count: 0, entity: null}));
    for (const e of found.slice(0, 16)) Instance.Msg("AP_ENTITY " + token + " " + JSON.stringify({name, count: found.length,
      entity: {classname: e.GetClassName(), origin: v3(e.GetAbsOrigin()), angles: e.GetAbsAngles(), velocity: v3(e.GetAbsVelocity()),
               health: e.GetHealth(), alive: e.IsAlive()}}));
  }
  Instance.Msg("AP_ENTITIES_END " + token + " " + JSON.stringify({map: Instance.GetMapName()}));
});
'''


def probe_paths(addon: str) -> tuple[str, str]:
    content = os.path.join(CS2, 'content', 'csgo_addons', addon, *PROBE_REL.split('/')) + '.js'
    game = os.path.join(CS2, 'game', 'csgo_addons', addon, *PROBE_REL.split('/')) + '.vjs_c'
    return content, game


def compile_command(source: str) -> list[str]:
    """resourcecompiler -f -i <file> (cs2-gotchas.md: how a map script is compiled by hand)."""
    return [os.path.join(cs2live.GAME_BIN, 'resourcecompiler.exe'), '-f', '-i', source]


def probe_install(addon: str, run_compiler: bool = False) -> dict:
    """Write the probe into the addon; with run_compiler, compile it (resourcecompiler, ~seconds). It ships with a
    Workshop upload if left there: probe_remove() before uploading."""
    src, out = probe_paths(addon)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    with open(src, 'w', encoding='utf-8', newline='\n') as f:
        f.write(PROBE_JS)
    res = {'source': src, 'compiled': out, 'compile': compile_command(src)}
    if run_compiler:
        r = subprocess.run(res['compile'], cwd=cs2live.GAME_BIN, capture_output=True, text=True, errors='replace', timeout=300)
        res.update(code=r.returncode, ok=r.returncode == 0 and os.path.exists(out), log=(r.stdout + r.stderr)[-2000:])
    return res


def probe_remove(addon: str) -> list[str]:
    gone = []
    for p in probe_paths(addon):
        with contextlib.suppress(OSError):
            os.remove(p)
            gone.append(p)
    return gone


def _probe_spawn(g):
    g.command(['sv_cheats 1', 'ent_fire autoport_probe Kill',
               'ent_create point_script {"targetname" "autoport_probe" "cs_script" "%s.vjs"}' % PROBE_REL], wait=0.6)


def probe_players(g, spawn: bool = True) -> dict | None:
    """{map, count, freeze, warmup, players: [...]} from the probe; None when it isn't there (and spawn failed)."""
    token = uuid.uuid4().hex[:10]
    for attempt in (0, 1):
        lines = g.query('ap_probe_players ' + token, r'AP_PLAYERS_END ' + token, timeout=2.0, retries=0)
        end = next((l for l in lines if l.startswith('AP_PLAYERS_END ' + token)), None)
        if end:
            state = json.loads(end.split(' ', 2)[2])
            state['players'] = [json.loads(l.split(' ', 2)[2]) for l in lines if l.startswith('AP_PLAYER ' + token)]
            return state
        if attempt or not spawn:
            return None
        _probe_spawn(g)
    return None


def physics_probe(g, names: list[str]) -> dict:
    """Live state of named entities: count, class, origin, angles, velocity, health, alive (physics.py:582-617). Compare
    before/after an action; a vanished entity alone doesn't prove it broke."""
    if not names or len(names) > 64:
        raise ValueError('give 1..64 targetnames')
    token = uuid.uuid4().hex[:10]
    cmd = 'ap_probe_entities %s %s' % (token, ' '.join(names))
    lines = g.query(cmd, r'AP_ENTITIES_END ' + token, timeout=2.0, retries=0)
    if not any(l.startswith('AP_ENTITIES_END ' + token) for l in lines):
        _probe_spawn(g)
        lines = g.query(cmd, r'AP_ENTITIES_END ' + token, timeout=4.0, retries=1)
    end = next((l for l in lines if l.startswith('AP_ENTITIES_END ' + token)), None)
    if not end:
        raise GameError('the probe did not answer: run "livetest.py probe install <addon> --compile" first')
    seen = {n: {'name': n, 'count': 0, 'entities': []} for n in names}
    for l in lines:
        if l.startswith('AP_ENTITY ' + token):
            rec = json.loads(l.split(' ', 2)[2])
            seen[rec['name']]['count'] = rec['count']
            if rec['entity']:
                seen[rec['name']]['entities'].append(rec['entity'])
    return {'map': json.loads(end.split(' ', 2)[2]).get('map'), 'entities': list(seen.values())}


# ------------------------------------------------------------------ bot playtests
def _status_players(lines) -> dict:
    bots = sum(1 for l in lines if re.search(r'\bBOT\b', l))
    humans = sum(1 for l in lines if re.match(r"\s*\d+\s+\d+:\d+", l))
    return {'bots': bots, 'humans': humans}


def playtest(g, map_name: str, bots: int = 10, seconds: int = 60, spectate: bool = True, out_dir: str | None = None,
             addon: str | None = None) -> dict:
    """A bounded bot match (playtest.py:124-163): bots join both teams, the local player watches, status (and the probe
    when present) is sampled every few seconds, and every console line goes to the log."""
    if not 0 <= bots <= 32 or not 1 <= seconds <= 600:
        raise ValueError('bots 0..32, seconds 1..600')
    at = g.c.cursor()
    st = g.status()
    reloaded = False
    if not cs2live.status_has_map(st, map_name):
        load = g.load_map(map_name, addon)
        if not load['ok']:
            raise GameError('could not load %s: %s' % (map_name, load['reason']))
        reloaded = True
    g.command(['sv_cheats 1', 'bot_kick', 'mp_limitteams 0', 'mp_autoteambalance 0', 'bot_quota 0', 'mp_warmup_end',
               'mp_freezetime 0', 'mp_restartgame 1'], wait=2.0)
    if spectate and bots:
        g.command('jointeam 1', wait=0.5)       # leave first, or CS2 fills the freed slot with one more bot
    for i in range(bots):
        g.command('bot_add_t' if i < bots // 2 else 'bot_add_ct', wait=0.25)
    t0 = time.monotonic()
    samples = []
    probe = probe_players(g, spawn=False) is not None
    while time.monotonic() - t0 < seconds:
        st = g.command('status', wait=0.6)
        sample = {'t': round(time.monotonic() - t0, 1), **_status_players(st)}
        if probe:
            p = probe_players(g, spawn=False) or {}
            sample['alive'] = {str(t): sum(1 for x in p.get('players', []) if x['team'] == t and x['alive']) for t in (2, 3)}
        samples.append(sample)
        time.sleep(min(5.0, max(0.2, seconds - (time.monotonic() - t0))))
    lines = g.c.texts(at)
    errs = [e for e in errors(lines)]
    result = {'map': map_name, 'reloaded': reloaded, 'bots_requested': bots, 'seconds': round(time.monotonic() - t0, 1),
              'human': 'spectator' if spectate and bots else 'player', 'samples': samples[-3:], 'probe': probe,
              'errors': errs[:8], 'error_count': len(errs), 'script_errors': script_errors(lines)[:8],
              'ok': bool(samples) and not errs}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, 'playtest_%s_%s.json' % (map_name, time.strftime('%Y%m%d_%H%M%S')))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({**result, 'samples': samples, 'console': lines}, f, indent=1)
        result['log'] = path
    return result


MODE_CVARS = ['game_type', 'game_mode', 'sv_airaccelerate', 'sv_autobunnyhopping', 'sv_enablebunnyhopping',
              'mp_respawn_on_death_t', 'mp_respawn_on_death_ct', 'mp_ignore_round_win_conditions', 'mp_freezetime',
              'mp_limitteams', 'mp_autoteambalance', 'mp_warmuptime', 'bot_quota']


def mode_playtest(g, addon: str, map_name: str, game_type: int, game_mode: int, bots: int = 10, seconds: int = 30,
                  out_dir: str | None = None) -> dict:
    """A playtest in a native mode (modes.py:378-460): the mode cvars are read, game_type/game_mode set, the map
    reloaded so the rules rebuild, the bot match run, then every cvar is put back and checked."""
    before = g.cvars(MODE_CVARS)
    try:
        g.command(['mp_freezetime 0', 'game_type %d' % game_type, 'game_mode %d' % game_mode], wait=0.2)
        load = g.load_map(map_name, addon)
        if not load['ok']:
            raise GameError('could not load %s: %s' % (map_name, load['reason']))
        now = g.cvars(['game_type', 'game_mode'])
        if (int(float(now.get('game_type', -1))), int(float(now.get('game_mode', -1)))) != (game_type, game_mode):
            raise GameError('CS2 did not keep game_type %d / game_mode %d: %s' % (game_type, game_mode, now))
        result = playtest(g, map_name, bots, seconds, True, out_dir, addon)
        result['mode'] = {'game_type': game_type, 'game_mode': game_mode}
    finally:
        if before:
            g.command(['%s %s' % kv for kv in before.items()], wait=0.2)
            after = g.cvars(list(before))
            bad = {k: (v, after.get(k)) for k, v in before.items() if after.get(k) != v}
            if bad:
                raise GameError('mode cvars not restored: %s' % bad)
    result['restored'] = before
    return result


# ------------------------------------------------------------------ real input
def mouse_move(dx: int, dy: int, step: int = 20, pause: float = 0.01) -> int:
    """Relative mouse motion with SendInput (system.py:155-167). Goes to whatever window is in front: only call it
    while the game is focused."""
    import ctypes
    import ctypes.wintypes as wt

    class MI(ctypes.Structure):
        _fields_ = [('dx', wt.LONG), ('dy', wt.LONG), ('mouseData', wt.DWORD), ('dwFlags', wt.DWORD), ('time', wt.DWORD),
                    ('dwExtraInfo', ctypes.POINTER(wt.ULONG))]

    class IN(ctypes.Structure):
        _fields_ = [('type', wt.DWORD), ('mi', MI)]
    n = max(1, math.ceil(max(abs(dx), abs(dy)) / step))
    done_x = done_y = 0
    for i in range(1, n + 1):
        tx, ty = round(dx * i / n), round(dy * i / n)
        ev = IN(0, MI(tx - done_x, ty - done_y, 0, 0x0001, 0, None))
        ctypes.windll.user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(IN))
        done_x, done_y = tx, ty
        time.sleep(pause)
    return n


def click_window(hwnd: int, fx: float, fy: float) -> tuple[int, int]:
    """A real left click at fractions of the client area (a HUD button in cursor mode; system.py:170-183)."""
    import ctypes
    import ctypes.wintypes as wt
    u = ctypes.windll.user32
    rect = wt.RECT()
    u.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wt.POINT(int(rect.right * fx), int(rect.bottom * fy))
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    u.SetCursorPos(pt.x, pt.y)
    time.sleep(0.06)
    for flag in (0x0002, 0x0004):
        u.mouse_event(flag, 0, 0, 0, 0)
        time.sleep(0.06)
    return pt.x, pt.y


def validate_steps(steps):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 128:
        raise ValueError('steps: a list of 1..128 actions')
    for s in steps:
        kinds = [k for k in s if k in STEP_KINDS]
        if len(kinds) == 2 and 'wait' in kinds and any(k in WAIT_AFTER for k in kinds):
            kinds.remove('wait')
        if len(kinds) != 1:
            raise ValueError('each step needs exactly one action of %s: %r' % (', '.join(STEP_KINDS), s))
        k, v = kinds[0], s[kinds[0]]
        if k == 'expect':
            re.compile(v)
        elif k == 'hold' and (not isinstance(v, dict) or v.get('key') not in KEYS):
            raise ValueError('hold: {"key": one of %s, "seconds": n}' % ', '.join(KEYS))
        elif k in ('walk', 'go') and (not isinstance(v, list) or len(v) != 3):
            raise ValueError('%s: [x, y, z] (feet)' % k)
        elif k == 'say' and any(c in str(v) for c in '\n\r;"'):
            raise ValueError('say cannot hold a newline, semicolon or quote')
    return steps


def scenario(g, steps, timeout: float = 90, allow_focus: bool = False, out_dir: str | None = None) -> dict:
    """Run steps with real input and check the console (scripting.py:554-899). Step forms:
    {"cmd": "..."} {"say": "..."} {"fire": "name Input"} {"press": "button"} (each may add "wait": s),
    {"walk": [x,y,z]} (setpos, noclip off), {"go": [x,y,z]} (walk there with +forward), {"wait": s},
    {"expect": regex, "within": s}, {"shot": name}, {"use": true}, {"hold": {"key": k, "seconds": s}},
    {"aim": [x,y,z]}, {"mouse": {"dx": n, "dy": n}}, {"click": [fx, fy]}, {"focus": true|false}.
    mouse, click and focus need allow_focus (the window must be in front); keys are always released at the end."""
    steps = validate_steps(steps)
    t0 = time.monotonic()
    deadline = t0 + timeout
    at = g.c.cursor()
    checks, shots, done = [], [], []
    reason = None
    focus_prev = None

    def left():
        rem = deadline - time.monotonic()
        if rem <= 0:
            raise TimeoutError('scenario ran past %g s' % timeout)
        return rem

    def hold(key, seconds):
        try:
            g.command('+' + KEYS[key], wait=0)
            time.sleep(min(seconds, left()))
        finally:
            g.command('-' + KEYS[key], wait=0.1)

    cursor = at
    try:
        g.release_keys()
        for i, s in enumerate(steps):
            left()
            k = next(x for x in s if x in STEP_KINDS and not (x == 'wait' and len([y for y in s if y in STEP_KINDS]) > 1))
            v = s[k]
            if k in ('cmd', 'say', 'fire', 'press', 'walk', 'use', 'hold', 'aim', 'mouse', 'click'):
                cursor = g.c.cursor()
            if k == 'cmd':
                g.command(v, wait=0.25)
            elif k == 'say':
                g.command('say ' + v, wait=0.25)
            elif k == 'fire':
                g.command('ent_fire ' + v, wait=0.25)
            elif k == 'press':
                g.command('ent_fire %s Press' % v, wait=0.25)
            elif k == 'walk':
                g.command(['noclip 0', 'setpos %g %g %g' % tuple(v)], wait=0.4)
            elif k == 'go':
                issue = walk_to(g, v, within=min(15, left()))
                if issue:
                    raise RuntimeError('go step %d: %s' % (i, issue))
            elif k == 'wait':
                time.sleep(min(float(v), left()))
            elif k == 'expect':
                hit = g.c.wait_for(v, min(float(s.get('within', 5)), left()), since=cursor)
                checks.append({'expect': v, 'ok': bool(hit)})
                if not hit:
                    raise RuntimeError('expected %r, not seen' % v)
            elif k == 'shot':
                path = g.console_screenshot('autoport_' + re.sub(r'[^\w.-]', '_', str(v)))
                shots.append({'name': v, 'path': path})
            elif k == 'use':
                hold('use', 0.15)
            elif k == 'hold':
                hold(v['key'], float(v.get('seconds', 0.2)))
            elif k == 'aim':
                eye = g.getpos()
                if not eye:
                    raise RuntimeError('aim: getpos returned no eye position')
                g.command('setang %g %g 0' % tuple(cs2live.look_at(eye[:3], v)[:2]), wait=1.0)
            elif k in ('mouse', 'click', 'focus'):
                if not allow_focus:
                    raise RuntimeError('%s needs the game window in front: run with --focus' % k)
                if k == 'focus':
                    if v and focus_prev is None:
                        focus_prev = cs2live.foreground()
                        cs2live.focus(g.game_window()['hwnd'], True)
                    elif not v and focus_prev:
                        import ctypes
                        ctypes.windll.user32.SetForegroundWindow(focus_prev)
                        focus_prev = None
                elif cs2live.foreground() != g.game_window()['hwnd']:
                    raise RuntimeError('%s: the CS2 window is not in front; not sent' % k)
                elif k == 'mouse':
                    mouse_move(int(v.get('dx', 0)), int(v.get('dy', 0)))
                else:
                    click_window(g.game_window()['hwnd'], v[0], v[1])
            if k in WAIT_AFTER and 'wait' in s:
                time.sleep(min(float(s['wait']), left()))
            done.append({'step': i, 'action': k})
    except Exception as e:  # noqa: BLE001 - the reason goes in the result
        reason = '%s: %s' % (type(e).__name__, e)
    finally:
        with contextlib.suppress(Exception):
            g.release_keys()
        if focus_prev:
            with contextlib.suppress(Exception):
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(focus_prev)
    lines = g.c.texts(at)
    errs = script_errors(lines)
    result = {'ok': reason is None and not errs and all(c['ok'] for c in checks), 'reason': reason,
              'seconds': round(time.monotonic() - t0, 1), 'steps_done': len(done), 'checks': checks, 'shots': shots,
              'script_errors': errs[:8]}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, 'scenario_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({**result, 'steps': steps, 'console': lines}, f, indent=1)
        result['log'] = path
    return result


def walk_to(g, goal, radius: float = 20, within: float = 15, duck: bool = False, jump: bool = False) -> str | None:
    """Walk to goal (feet) with real movement keys: aim with setang, pulse +forward, read getpos, until within radius
    (route.py Driver.go). None on arrival, else why: 'no_progress', 'timeout', 'no_player', 'fall'.
    The client takes a server setang into its own movement only while in front (game.py:783-785): unfocused, the
    player may walk the old way. Measured in the PC test list, not here."""
    until = time.monotonic() + within
    best, progressed = float('inf'), time.monotonic()
    jumped = False
    try:
        g.command(['noclip 0', '-forward', '+duck' if duck else '-duck'], wait=0.1)
        while True:
            eye = g.getpos()
            if not eye:
                return 'no_player'
            feet = [eye[0], eye[1], eye[2] - (46 if duck else cs2live.EYE)]
            dist = math.dist(feet[:2], goal[:2])
            if dist <= radius and abs(feet[2] - goal[2]) <= 18:
                return None
            if feet[2] - goal[2] < -256:
                return 'fall'
            metric = dist + abs(feet[2] - goal[2])
            if metric < best - 3:
                best, progressed = metric, time.monotonic()
            if time.monotonic() - progressed > 1.8:
                return 'no_progress'
            if time.monotonic() >= until:
                return 'timeout'
            ang = cs2live.look_at(eye[:3], [goal[0], goal[1], eye[2]])
            cmds = ['setang 0 %g 0' % ang[1], '+forward']
            if jump and not jumped and dist < 100:
                cmds.append('+jump')
                jumped = True
            g.command(cmds, wait=0)
            speed = 85 if duck else 250
            time.sleep(min(0.25, max(0.06, (dist - radius) / speed)))
            g.command(['-forward', '-jump'], wait=0)
    finally:
        with contextlib.suppress(Exception):
            g.command(['-forward', '-jump', '-duck'], wait=0)


def timing(g, start, goal, within: float = 30) -> dict:
    """Seconds from start to goal on foot (comp_timings, competitive.py:538): setpos at the start with noclip off, wait
    out the freeze time, then walk_to with real keys. Seconds include the controller's pauses."""
    g.command(['sv_cheats 1', '-forward', 'noclip 0', 'slot3', 'setpos %g %g %g' % tuple(start)], wait=0.4)
    t0 = time.monotonic()
    issue = walk_to(g, goal, radius=24, within=within)
    took = round(time.monotonic() - t0, 2)
    return {'ok': issue is None, 'seconds': took if issue is None else None, 'reason': issue, 'start': list(start),
            'goal': list(goal), 'metres': round(math.dist(start, goal) * 0.0254, 1)}


# ------------------------------------------------------------------ tester marks
MARK_CFG = 'autoport_mark'
MARK_BEGIN = 'AUTOPORT_MARK_BEGIN'
MARK_CFG_TEXT = ('// autoport tester mark (skink52): a marker, the eye position, the map and a frame. Read back by\n'
                 '// "livetest.py marks harvest" from the console.\n'
                 'echo %s\ngetpos\nstatus\njpeg_screenshot autoport_mark 90\n' % MARK_BEGIN)
_CHAT = re.compile(r'^\s*(?:\*[^*\s]{1,16}\*\s*)?\[[^\]]{1,32}\]\s.{0,96}?\u200e(?:\s*@\s*[^:]{0,64})?:\s(?P<text>.+)$')


def marks_cfg_path() -> str:
    """In the game's own cfg folder, so it never ships inside an addon (exec finds it from any addon session)."""
    return os.path.join(CS2, 'game', 'csgo', 'cfg', MARK_CFG + '.cfg')


def marks_install(g, key: str = 'F8') -> str:
    """Write the cfg and bind the key to it (marks.py:454-483). A key bound to something else of the user's is left
    alone. CS2 keeps binds in the user's key config, so the key works in later sessions too."""
    with open(marks_cfg_path(), 'w', encoding='utf-8') as f:
        f.write(MARK_CFG_TEXT)
    lines = g.query('bind %s' % key, r'" = "|not bound|isn\'t a valid key', timeout=3.0)
    text = '\n'.join(lines)
    if "isn't a valid key" in text:
        raise ValueError('%s is not a CS2 key name' % key)
    m = re.search(r'"%s"\s*=\s*"(.*)"' % re.escape(key), text, re.I)
    current = m.group(1) if m else ''
    if current and current != 'exec ' + MARK_CFG:
        return '%s not bound: it is bound to "%s"; pick a free key' % (key, current)
    g.command('bind %s "exec %s"' % (key, MARK_CFG), wait=0.2)
    return key


def marks_harvest(lines) -> list[dict]:
    """Marks in console lines (vconsole.Line, or text): eye position and view, map, frame, and the chat lines the tester
    typed after the mark (Y, text, Enter; the note), as marks.py:111-149 reads them."""
    texts = [(getattr(l, 'ms', 0), getattr(l, 'text', l)) for l in lines]
    begins = [i for i, (_, t) in enumerate(texts) if t.strip() == MARK_BEGIN]
    out = []
    for k, i in enumerate(begins):
        end = begins[k + 1] if k + 1 < len(begins) else len(texts)
        m = {'ms': texts[i][0], 'eye': None, 'ang': None, 'setpos': None, 'map': None, 'shot': None, 'notes': []}
        for ms, t in texts[i + 1:end]:
            if m['eye'] is None:
                p = cs2live.parse_getpos([t])
                if p:
                    m['eye'], m['ang'] = list(p[:3]), list(p[3:])
                    m['setpos'] = 'setpos %g %g %g;setang %g %g %g' % p
                    continue
            if m['map'] is None:
                name = cs2live.status_map([t])
                if name:
                    m['map'] = name
                    continue
            if m['shot'] is None:
                s = re.search(r'Screenshot written to:\s*(.+)', t)
                if s:
                    m['shot'] = s.group(1).strip()
                    continue
            c = _CHAT.match(t)
            if c and m['eye'] is not None and len(m['notes']) < 10:
                m['notes'].append(c.group('text').strip()[:200])
        m['note'] = ' / '.join(m['notes']) or None
        out.append(m)
    return out


# ------------------------------------------------------------------ script reload
def script_reload(g, targetname: str, cs_script: str, keyvalues: dict | None = None) -> list[str]:
    """Restart a map's point_script without reloading the map (scripting.py:243-297): Kill it and ent_create it again
    with the same keys. The script's state is gone, as after a round restart. The new code must be compiled first."""
    if not re.match(r'^[\w.-]+$', targetname):
        raise ValueError('targetname must be a plain name')
    kv = {'targetname': targetname, 'cs_script': cs_script, **(keyvalues or {})}
    if any('"' in str(x) for kv_ in kv.items() for x in kv_):
        raise ValueError('keyvalues cannot hold quotes')
    pairs = ' '.join('"%s" "%s"' % (k, v) for k, v in kv.items() if k not in ('classname', 'origin', 'angles'))
    out = g.command(['sv_cheats 1', 'ent_fire %s Kill' % targetname], wait=0.3)
    return out + g.command('ent_create point_script {%s}' % pairs, wait=1.0)


# ------------------------------------------------------------------ CLI
def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=vconsole.PORT)
    ap.add_argument('--netcon', type=int)
    ap.add_argument('--out', default=os.path.join(os.environ.get('CS2PORT', r'C:\source1\cs2port'), 'logs', 'autoport', 'ingame'))
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('reset')
    p = sub.add_parser('playtest'); p.add_argument('addon'); p.add_argument('map'); p.add_argument('--bots', type=int, default=10)
    p.add_argument('--seconds', type=int, default=60); p.add_argument('--player', action='store_true', help='play instead of spectating')
    p = sub.add_parser('mode'); p.add_argument('addon'); p.add_argument('map'); p.add_argument('--game-type', type=int, required=True)
    p.add_argument('--game-mode', type=int, required=True); p.add_argument('--bots', type=int, default=10); p.add_argument('--seconds', type=int, default=30)
    p = sub.add_parser('scenario'); p.add_argument('addon'); p.add_argument('map'); p.add_argument('steps')
    p.add_argument('--focus', action='store_true'); p.add_argument('--timeout', type=float, default=90)
    p = sub.add_parser('walk'); p.add_argument('xyz', nargs=3, type=float); p.add_argument('--within', type=float, default=15)
    p.add_argument('--radius', type=float, default=20)
    p = sub.add_parser('timing'); p.add_argument('addon'); p.add_argument('map')
    p.add_argument('--start', nargs=3, type=float, required=True); p.add_argument('--goal', nargs=3, type=float, required=True)
    p = sub.add_parser('probe'); p.add_argument('action', choices=('install', 'remove')); p.add_argument('addon')
    p.add_argument('--compile', action='store_true')
    p = sub.add_parser('physics'); p.add_argument('names', nargs='+')
    p = sub.add_parser('marks'); p.add_argument('action', choices=('install', 'harvest')); p.add_argument('--key', default='F8')
    p.add_argument('--seconds', type=float, default=5)
    p = sub.add_parser('reload'); p.add_argument('targetname'); p.add_argument('cs_script'); p.add_argument('kv', nargs='*')
    a = ap.parse_args(argv)
    if a.cmd == 'probe':
        res = probe_install(a.addon, a.compile) if a.action == 'install' else {'removed': probe_remove(a.addon)}
        print(json.dumps(res, indent=1)); return 0
    try:
        g = cs2live.connect(a.port, a.netcon)
    except (GameError, vconsole.ConsoleError) as e:
        print(e, file=sys.stderr); return 2
    try:
        with cs2live.exclusive('livetest ' + a.cmd, wait=60):
            if a.cmd == 'reset':
                res = g.reset()
            elif a.cmd == 'playtest':
                res = playtest(g, a.map, a.bots, a.seconds, not a.player, a.out, a.addon)
            elif a.cmd == 'mode':
                res = mode_playtest(g, a.addon, a.map, a.game_type, a.game_mode, a.bots, a.seconds, a.out)
            elif a.cmd == 'scenario':
                g.addon = a.addon
                if not cs2live.status_has_map(g.status(), a.map):
                    load = g.load_map(a.map, a.addon)
                    if not load['ok']:
                        raise GameError(load['reason'])
                res = scenario(g, json.load(open(a.steps, encoding='utf-8')), a.timeout, a.focus, a.out)
            elif a.cmd == 'walk':
                res = {'reason': walk_to(g, a.xyz, a.radius, a.within)}
            elif a.cmd == 'timing':
                res = timing(g, a.start, a.goal)
            elif a.cmd == 'physics':
                res = physics_probe(g, a.names)
            elif a.cmd == 'marks':
                if a.action == 'install':
                    res = {'key': marks_install(g, a.key)}
                else:
                    g.c.wait_for(lambda t: False, a.seconds)
                    res = {'marks': marks_harvest(g.c.since(0))}
            elif a.cmd == 'reload':
                res = {'console': script_reload(g, a.targetname, a.cs_script, dict(x.split('=', 1) for x in a.kv))}
        print(json.dumps(res, indent=1, default=str))
        return 0 if res.get('ok', True) else 1
    except (GameError, vconsole.ConsoleError, ValueError) as e:
        print(e, file=sys.stderr); return 2
    finally:
        g.c.close()


if __name__ == '__main__':
    sys.exit(main())
