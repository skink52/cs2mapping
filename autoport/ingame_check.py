"""In-game check of a built addon map: load it in the running CS2, read the console for N seconds, sort what it says the
way autoport sorts tool messages, and write a report. Stdlib only.

  python ingame_check.py <addon> [<map>] [--seconds 20] [--screenshot] [--views] [--bots N --play S]
                         [--port 29000 | --netcon PORT] [--plain-map] [--no-load] [--out DIR] [--launch [--keep]]

CS2 must already be running with its console open: CS2 Workshop Tools (Steam > Counter-Strike 2 > Launch CS2 Workshop
Tools; VConsole2 on TCP 29000), or any client started with -netconport PORT. Without one the check is skipped (exit 3).
--launch starts CS2 Workshop Tools itself, minimised and not activated (cs2live.launch_command lists the flags), and
stops it afterwards unless --keep; it refuses if any CS2 already runs. Never used by autoport unless asked.

What it reads: every line CS2 prints from the load command on, map script output included (Instance.Msg and map
`echo` reach the console client although console.log (-condebug) lacks them). Lines that look like problems are sorted
by LIVE_RULES into autoport's kinds (common.ALL_KINDS): error (the map failed to load, CS2 crashed), missing
(resources that failed to load), io (script errors, entity I/O errors), minor, and unknown for a problem line no rule
knows, so a new message can't slip past unread (the profiles.TODO_RULES idea). If the connection drops, the newest CS2
minidump written since the check began is read (crashdump.py).

Exit: 0 nothing that holds a build, 1 something that holds (missing/io/unknown), 2 load failed or CS2 crashed, 3 skipped.
Report: <out>/<addon>_ingame_<time>.md and .json (default C:\\source1\\cs2port\\logs\\autoport\\ingame).

Learned from Rmgs123/cs2-map-mcp (MIT; game.py load_map, playtest.py, gametest.py), re-written for autoport.
Written by Claude (AI) for skink52's autoport; not hand-written.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)   # appended: inside tools/mcp_server.py, tools/ modules keep priority
import crashdump  # noqa: E402
import cs2live  # noqa: E402
import vconsole  # noqa: E402

PORT_DIR = os.environ.get('CS2PORT', r'C:\source1\cs2port')
OUT = os.path.join(PORT_DIR, 'logs', 'autoport', 'ingame')
VMF_DIR = r'C:\source1\maps'

# A line is looked at only if it reads like a problem. "(?<!t)error" keeps "terrorist" out.
PROBLEM = re.compile(r"(?<!t)error|fail|missing|warning|can't|cannot|couldn't|could not|unable|invalid|not found|assert|uncaught|"
                     r'exception|unknown (?:command|input|entity|class|sound)|bad keyvalue|no such|has no (?:input|output)|'
                     r'no (?:input|output) named|unhandled input|unrecognized parent', re.I)

# first match wins; None = known noise. Same shape as profiles.TODO_RULES: (kind, regex).
LIVE_RULES = [
    (None, r'^Annotation:|^Graph Warning: animation/graphs/|Failed to set animgraph param e_(?:face|body)_idle|'
           r'Unable to determine cubemap texture|CQ: Server set re-sync|\b(?:errors|failed|missing|warnings?):? 0\b|no errors|'
           r'autoport_[be]_[0-9a-f]{12}|AUTOPORT_MARK_BEGIN|Steam(?:NetSockets|Networking)|GCClient|'
           r'Failed to find (?:dependency|resource) .*?_c\.vtex.*?compiled locally'),
    ('minor', r"Unknown command"),       # also our own fast-start cvars on a build without them; a map script's typo shows here too
    # the map didn't load, or the game stopped
    ('error', r"invalid map|can't find map|couldn't find map|failed to load map|map load failed|no such map|missing map|Host_Error|"
              r'FATAL ERROR|Sys_Error|Disconnect(?:ed)?:.*(?:error|failed|crash)|Engine Error'),
    # map scripts (cs_script); messages of the 5 Nov 2026 API (cs_script-notes.md) included
    ('io', r'Uncaught|(?:Type|Reference|Syntax|Range|Internal)Error|Invalid module specifier|Failed to (?:load|compile).*script|'
           r'invoked on an invalid entity|cs_script.*(?:error|fail)|point_script.*(?:error|fail)|Script (?:error|exception)|'
           r'JavaScript.*(?:error|exception)'),
    # entity I/O and spawning
    ('io', r"Couldn't find output named|unknown input|no (?:such )?input named|has no input|unhandled input|unrecognized parent|"
           r"parent .*not found|Unable to find (?:entity|target)|No entity (?:named|found)|Failed to (?:create|spawn) entity|"
           r"CreateEntityByName|Unknown entity (?:class|type)|unknown classname|Entity .*(?:has no|is missing|bad|invalid)|"
           r'ent_fire.*(?:not found|no target)|bad keyvalue|Invalid keyvalue'),
    # resources
    ('missing', r'\.(?:vmat|vmdl|vtex|vsnd|vpcf|vmesh|vphys|vsndevts|vsurf|vjs|vxml|vcss|vpost|vdata|vnmgraph|vrman|vwnod|vents|vmap|vwrld)(?:_c)?\b'),
    ('missing', r'(?:missing|failed to load|error loading|couldn\'t load|can\'t load|unable to load|could not (?:load|open|find)|'
                r'not found).*(?:resource|material|model|texture|sound|particle|asset|file)|'
                r'(?:resource|material|model|texture|particle|asset) .*(?:missing|not found|failed)|ERROR_FILEOPEN|error\.vmat'),
    # known, doesn't stop the map
    ('minor', r'sound ?event .*(?:not found|unknown|missing)|Unknown sound|precache|Precache|soundscape|navigation mesh|nav mesh|'
              r'\.nav\b|Ran out of|budget'),
]
_COMPILED = [(k, re.compile(p, re.I)) for k, p in LIVE_RULES]
HOLD = ('error', 'missing', 'unknown', 'io')        # common.HOLD_KINDS
CHANNEL_KIND = {'JavaScriptCompiler': 'io', 'Entity System': 'io', 'Entity Load Unserialize': 'io'}


def classify_line(text: str, chan: str = '') -> str | None:
    """autoport kind for one console line, or None when it isn't a problem (or is known noise)."""
    if not PROBLEM.search(text):
        return None
    for kind, rx in _COMPILED:
        if rx.search(text):
            return kind
    return CHANNEL_KIND.get(chan, 'unknown')


def normalise(text: str, names=()) -> str:
    """A line with the map's names and every number taken out, so the same engine message matches across maps."""
    t = text.strip().lower()
    for n in names:
        if n and '_' in n:                       # map and addon names (mg_x, de_dust2), not a plain word like "stock"
            t = t.replace(n.lower(), '<map>')
    return re.sub(r'\d+(?:\.\d+)?', '#', t)


def load_baseline(path: str) -> set:
    try:
        with open(path, encoding='utf-8') as f:
            return set(json.load(f).get('lines', []))
    except (OSError, ValueError):
        return set()


def classify(lines, baseline=frozenset(), names=()) -> dict[str, list[str]]:
    """{kind: [distinct lines, in order]} for console lines (vconsole.Line or str). Lines in the baseline (what a stock
    map prints on this PC, recorded with --record-baseline) are left out."""
    out: dict[str, list[str]] = {}
    for l in lines:
        text = getattr(l, 'text', l).strip()
        kind = classify_line(text, getattr(l, 'chan', ''))
        if kind and baseline and normalise(text, names) in baseline:
            continue
        if kind and text not in out.setdefault(kind, []):
            out[kind].append(text)
    return {k: v for k, v in out.items() if v}


def record_baseline(lines, names, path: str) -> int:
    """Add this run's problem lines to the baseline (run it on a stock map: ingame_check.py stock de_dust2 --plain-map
    --record-baseline). Returns how many lines it holds."""
    known = load_baseline(path)
    for l in lines:
        text = getattr(l, 'text', l)
        if classify_line(text, getattr(l, 'chan', '')):
            known.add(normalise(text, names))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'note': 'console problem lines a stock map prints on this PC; ingame_check.py leaves them out',
                   'lines': sorted(known)}, f, indent=1)
    return len(known)


NOTE_TITLE = {'error': 'In game, failures', 'missing': 'In game, resources that failed to load', 'io': 'In game, script or entity I/O errors',
              'unknown': 'In game, console lines no rule knows', 'minor': 'In game, minor console warnings'}


def notes(result: dict) -> list[tuple[str, str]]:
    """(kind, text) lines for autoport's m.note, one per kind; texts stay the same for the same findings."""
    out = []
    if result.get('crash'):
        c = result['crash']
        out.append(('error', 'CS2 crashed during the in-game check: %s (%s)%s' % (c['summary'], c['file'], '; ' + c['hint'] if c.get('hint') else '')))
    elif result.get('crashed'):
        out.append(('error', 'The console closed during the in-game check and no new crash dump was found: did CS2 quit?'))
    if result.get('load') and not result['load'].get('ok') and not result.get('crashed'):
        out.append(('error', 'The map did not load in game: %s' % result['load'].get('reason')))
    for kind, lines in result.get('issues', {}).items():
        first = 8 if kind in ('missing', 'io') else 5
        out.append((kind, '%s: %d (first %d): %s. Report: %s' % (NOTE_TITLE[kind], len(lines), min(first, len(lines)),
                                                                 ' | '.join(l[:160] for l in lines[:first]), result.get('report', ''))))
    if result.get('load', {}).get('ok') and not any(k in HOLD for k, _ in out):
        out.append(('playtest', 'In game: %s loaded in %s s and printed no errors in %d s; still play it (spawns, doors, scripts, finish).'
                    % (result['map'], result['load'].get('seconds'), result.get('seconds', 0))))
    return out


def spawn_views(addon: str, limit: int = 2) -> list[dict]:
    """A camera at the first T and CT spawn of the map's VMF (C:\\source1\\maps\\<addon>.vmf), as it faces."""
    try:
        with open(os.path.join(VMF_DIR, addon + '.vmf'), encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return []
    views = []
    for cls in ('info_player_terrorist', 'info_player_counterterrorist', 'info_player_start'):
        for block in re.findall(r'entity\s*\{(.*?)\n\}', text, re.S):
            if '"classname" "%s"' % cls in block:
                o = re.search(r'"origin" "([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', block)
                a = re.search(r'"angles" "([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', block)
                if o:
                    views.append({'name': '%s_%s' % (addon, cls.split('_')[-1]), 'pos': [float(v) for v in o.groups()],
                                  'ang': [0.0, float(a.group(2)) if a else 0.0, 0.0]})
                break
        if len(views) >= limit:
            break
    return views


def check(addon: str, map_name: str | None = None, seconds: float = 20, port: int = vconsole.PORT, netcon: int | None = None,
          screenshot: bool = False, views: bool = False, bots: int = 0, play: int = 0, plain: bool = False, no_load: bool = False,
          launch: bool = False, keep: bool = False, out_dir: str = OUT, load_timeout: float = 150, record: bool = False) -> dict:
    map_name = map_name or addon
    t0 = time.time()
    stamp = time.strftime('%Y%m%d_%H%M%S')
    os.makedirs(out_dir, exist_ok=True)
    result = {'addon': addon, 'map': map_name, 'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'seconds': seconds,
              'report': os.path.join(out_dir, '%s_ingame_%s.md' % (addon, stamp))}
    launched = None
    con_port = netcon or port
    if not vconsole.reachable(port=con_port):
        if not launch:
            result.update(skipped='no CS2 console on port %d: start CS2 Workshop Tools (or a client with -netconport), or pass --launch' % con_port)
            return _finish(result, [], out_dir, record)
        launched = cs2live.launch(addon, port=con_port, netcon=netcon)
        result['launched'] = launched
    g = None
    lines = []
    try:
        g = cs2live.connect(port, netcon, addon)
        g.addon = addon
        result['session_addon'] = getattr(g.c.wire, 'addon', None)
        with cs2live.exclusive('ingame_check ' + addon, wait=120):
            at = g.c.cursor()
            try:
                if no_load:
                    st = g.status()
                    result['load'] = {'ok': cs2live.status_has_map(st, map_name), 'reason': None if cs2live.status_has_map(st, map_name)
                                      else 'status does not name %s (--no-load)' % map_name, 'seconds': 0}
                else:
                    load = g.load_map(map_name, addon, plain=plain, timeout=load_timeout)
                    result['crashed'] = bool(load.pop('crashed', False))
                    load.pop('lines', None)
                    result['load'] = load
                if result['load']['ok'] and not result.get('crashed'):
                    g.c.wait_for(lambda t: False, seconds)          # collect; raises if the game goes away
                    if screenshot:
                        result['screenshot'] = g.console_screenshot('autoport_%s' % map_name)
                    if views:
                        result['views'] = g.views(spawn_views(addon), os.path.join(out_dir, '%s_%s' % (addon, stamp)), 'console')
                    if bots and play:
                        import livetest
                        pt = livetest.playtest(g, map_name, bots, play, True, out_dir, addon)
                        result['playtest'] = {k: pt[k] for k in ('ok', 'samples', 'error_count', 'script_errors', 'log') if k in pt}
            except vconsole.ConsoleError as e:
                result['crashed'] = True
                result['console_error'] = str(e)
            lines = g.c.since(at)
    except (cs2live.GameError, vconsole.ConsoleError) as e:
        result['crashed'] = result.get('crashed') or isinstance(e, vconsole.ConsoleError)
        result['failed'] = str(e)
    finally:
        if g is not None:
            g.c.close()
        if launched and not keep:
            result['stopped'] = cs2live.stop(launched['pid'])
    if result.get('crashed') or result.get('failed'):
        dump = crashdump.newest(since=t0)
        if dump:
            r = crashdump.report(dump)
            result['crash'] = {k: r[k] for k in ('file', 'path', 'summary', 'hint', 'pid', 'console_tail')}
    return _finish(result, lines, out_dir, record)


def _finish(result: dict, lines, out_dir: str, record: bool = False) -> dict:
    names = (result['addon'], result['map'])
    base = os.path.join(out_dir, 'baseline.json')
    if record:
        result['baseline_lines'] = record_baseline(lines, names, base)
    result['issues'] = classify(lines, load_baseline(base), names)
    result['notes'] = notes(result)
    result['console_lines'] = len(lines)
    holds = [k for k, _ in result['notes'] if k in HOLD]
    result['exit'] = 3 if result.get('skipped') else 2 if 'error' in holds else 1 if holds else 0
    write_report(result, lines)
    return result


def write_report(result: dict, lines):
    md = result['report']
    w = ['# In-game check: %s' % result['map'], '',
         '- Addon `%s`, started %s, console read for %s s after the load.' % (result['addon'], result['started'], result['seconds'])]
    if result.get('skipped'):
        w += ['- **Skipped:** %s' % result['skipped']]
    load = result.get('load')
    if load:
        w += ['- Load: %s (`%s`, %s s, mp_freezetime %s, player in game: %s)' % (
            'ok' if load.get('ok') else 'FAILED: %s' % load.get('reason'), load.get('command', 'status only'), load.get('seconds'),
            load.get('freezetime'), load.get('player'))]
    if result.get('crash'):
        c = result['crash']
        w += ['- **CS2 crashed:** %s, `%s`%s' % (c['summary'], c['path'], ' - ' + c['hint'] if c.get('hint') else '')]
    elif result.get('crashed') or result.get('failed'):
        w += ['- **Console lost:** %s' % (result.get('console_error') or result.get('failed'))]
    if result.get('screenshot'):
        w += ['- Screenshot: `%s`' % result['screenshot']]
    for s in (result.get('views') or {}).get('shots', []):
        w += ['- View %s: `%s`' % (s['name'], s['path'])]
    if result.get('playtest'):
        w += ['- Bot playtest: %s' % json.dumps(result['playtest'])[:400]]
    w += ['', '## Findings', '']
    if result['notes']:
        w += ['| Kind | Note |', '|---|---|'] + ['| %s | %s |' % (k, t.replace('|', '/')) for k, t in result['notes']]
    else:
        w += ['Nothing to note.']
    for kind, items in result.get('issues', {}).items():
        w += ['', '### %s (%d)' % (kind, len(items)), ''] + ['- `%s`' % i.replace('`', "'")[:300] for i in items[:60]]
    if result.get('crash', {}).get('console_tail'):
        w += ['', '## Console tail from the crash dump', '', '```'] + result['crash']['console_tail'][-20:] + ['```']
    w += ['', '## Console (%d lines; all in the .json)' % len(lines), '', '```'] + [getattr(l, 'text', l)[:300] for l in lines[-80:]] + ['```', '']
    with open(md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(w))
    with open(md[:-3] + '.json', 'w', encoding='utf-8') as f:
        json.dump({**{k: v for k, v in result.items() if k != 'launched'}, 'launched': bool(result.get('launched')),
                   'console': [{'ms': getattr(l, 'ms', 0), 'chan': getattr(l, 'chan', ''), 'text': getattr(l, 'text', l)} for l in lines]},
                  f, indent=1, default=str)


def run_for_autoport(m, seconds: float = 20, launch: bool = False, **kw) -> int:
    """The autoport step: check m.addon in the running CS2 and note what it finds on the map (m.note). Skipped, with a
    playtest note, when no CS2 console is open. Returns the check's exit code. kw go to check() (port, out_dir ...)."""
    r = check(m.addon, m.addon, seconds, launch=launch, **kw)
    if r.get('skipped'):
        m.note('playtest', 'In-game check not run (%s). With CS2 Workshop Tools open: python C:\\source1\\cs2port\\autoport\\ingame_check.py %s'
               % (r['skipped'].split(':')[0], m.addon))
        return r['exit']
    for kind, text in r['notes']:
        m.note(kind, text, reopen=kind in HOLD)
    m.note('review', 'In-game report: ' + r['report'])
    return r['exit']


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('addon')
    ap.add_argument('map', nargs='?', help='map name in the addon (default: the addon name)')
    ap.add_argument('--seconds', type=float, default=20, help='how long to read the console after the load')
    ap.add_argument('--port', type=int, default=vconsole.PORT)
    ap.add_argument('--netcon', type=int, help='plain-text netcon port (-netconport) instead of VConsole2')
    ap.add_argument('--screenshot', action='store_true', help='jpeg_screenshot once loaded (no focus needed)')
    ap.add_argument('--views', action='store_true', help='console screenshots from the first T and CT spawn of the VMF')
    ap.add_argument('--bots', type=int, default=0, help='bots for a playtest after the read (with --play)')
    ap.add_argument('--play', type=int, default=0, help='seconds of bot playtest')
    ap.add_argument('--plain-map', action='store_true', help='load with "map <name>" instead of "map_workshop <addon> <map>"')
    ap.add_argument('--no-load', action='store_true', help='the map is already loaded: only read the console')
    ap.add_argument('--launch', action='store_true', help='start CS2 Workshop Tools (minimised) if no console is open')
    ap.add_argument('--keep', action='store_true', help='with --launch: leave the CS2 it started running')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--record-baseline', action='store_true', help='add the problem lines of this run to <out>/baseline.json (use on a stock map)')
    a = ap.parse_args(argv)
    r = check(a.addon, a.map, a.seconds, a.port, a.netcon, a.screenshot, a.views, a.bots, a.play, a.plain_map, a.no_load,
              a.launch, a.keep, a.out, record=a.record_baseline)
    if r.get('skipped'):
        print('Skipped: ' + r['skipped'])
    for kind, text in r['notes']:
        print('%-8s %s' % (kind.upper(), text))
    print('Report: ' + r['report'])
    return r['exit']


if __name__ == '__main__':
    sys.exit(main())
