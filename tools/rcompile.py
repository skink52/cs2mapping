"""resourcecompiler wrapper: one map with a named preset, single assets, and a build-log reader that says what went wrong.

  python rcompile.py asset <content file> [...] [--force] [--log FILE] [--json]      compile assets (.vmat .vmdl .vtex .vpcf .vsndevts ...)
  python rcompile.py map <map.vmap> [--preset fast|nav|full|final|entities|lighting] [--novis] [--threads N] [--log FILE] [--dry-run] [--json]
  python rcompile.py analyze <build log> [--json]                                    read a log someone else wrote (build_maps.ps1, Hammer)
  python rcompile.py presets                                                         the flags of every preset

A map build can take an hour: run it under the hang watchdog, e.g.
  python C:\\source1\\cs2port\\autoport\\watchdog.py --label "build mg_x" --expect 900 --heartbeat 60 --stall 900 --max 2700 --log logs\\mg_x_rc.log
         -- python rcompile.py map <vmap> --preset full --log logs\\mg_x_rc.log
and keep CS2 open from before the build to after it, or closed throughout (docs/porting/pipeline.md; build_maps.ps1 header).
The compiler runs without a console window (no focus stealing). It writes the .vpk to game\\csgo_addons\\<addon>\\maps\\ directly
(build_maps.ps1 instead goes through Hammer's outroot and copies; use that for the porting queue).

Result (JSON with --json): ok, exit_code, seconds, output (.vpk when fresh), summary {compiled, failed, skipped}, errors, warnings,
missing_assets, stage (last stage seen), nav_areas, hints (known causes and what to do).
ok = exit 0, no "N failed", no crash, and for maps a .vpk newer than the start.

Presets and log reading follow compiler.py in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT), merged with the full / final
argument lists skink52's build_maps.ps1 uses (steam audio, -rebake_surfacegraph) and the problems autoport.py looks for. Fresh code.
"""
import argparse, html, json, os, re, subprocess, sys, time

CS2_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
BASE = ['-fshallow', '-maxtextureres', '256', '-quiet', '-unbufferedio', '-noassert']
TAIL = ['-breakpad', '-nop4']
_SA = ['-sareverb', '-sareverb_threads', '{t}', '-sapaths', '-sacustomdata', '-sacustomdata_threads', '{t}']
PRESETS = {
    'fast': ['-world', '-phys', '-nolightmaps'],                                       # geometry, collision, entities; no baked light
    'nav': ['-world', '-phys', '-nav', '-gridnav', '-nolightmaps'],                     # + bot nav, still no bake
    'full': ['-world', '-rebake_surfacegraph', '-bakelighting', '-lightmapMaxResolution', '1024', '-lightmapVRadQuality', '1',
             '-phys', '-vis', '-nav'] + _SA,                                           # build_maps.ps1 "full"
    'final': ['-world', '-rebake_surfacegraph', '-bakelighting', '-lightmapMaxResolution', '2048', '-lightmapVRadQuality', '2',
              '-phys', '-vis', '-nav'] + _SA,                                          # build_maps.ps1 "final" (release light)
    'entities': ['-entities', '-rebake_surfacegraph', '-bakelighting', '-lightmapMaxResolution', '2048', '-lightmapVRadQuality', '2'],
    'lighting': ['-world', '-rebake_surfacegraph', '-bakelighting', '-lightmapMaxResolution', '2048', '-lightmapVRadQuality', '2'],
}
PARTIAL = {'entities', 'lighting'}   # these update an existing .vpk (Hammer's partial builds); they need an earlier full build

_SUMMARY = re.compile(r'(\d+)\s+compiled,\s+(\d+)\s+failed(?:,\s+(\d+)\s+skipped)?', re.I)
_ERROR = re.compile(r'\berror\b|\bfailed\b|\bfatal\b|access violation|0xc0000005|unable to|could not|cannot |too many charts|assertion', re.I)
_WARN = re.compile(r'\bwarning\b', re.I)
_NOISE = re.compile(r'\b0 failed|error\(s\): 0|errors: 0|no errors|failed: 0|_failed\b|errormodel|error\.vmdl|detail_prop_types\.vdata|'
                    r'fossilize|getfbxmaterialpath failed|-noassert|empty resource weak-reference', re.I)
_ASSET = r'([\w/\\.\- ]+?\.(?:vmat|vtex|vmdl|vpcf|vsnd|vsndevts|png|tga|psd|jpg|fbx|obj|dmx|smd|vmap|vsmart|vdata|vjs|vts|vxml|vcss|vpost)(?:_c)?)'
_MISSING = [re.compile(r'Failed loading resource "' + _ASSET + '"', re.I),
            re.compile(r'(?:missing|not found|can\'t find|cannot find|couldn\'t find|failed to (?:load|open))[^\n"]*?"?' + _ASSET, re.I),
            re.compile(r'ERROR_FILEOPEN[^\n]*?' + _ASSET, re.I)]
_COMPILE_ERR = re.compile(r'RESOURCE COMPILE ERROR: ([^\r\n]+)')
_NAV = re.compile(r'Nav mesh \([^)]*\) loaded with (\d+) nav areas', re.I)
STAGES = [(re.compile(p, re.I), label) for p, label in [
    (r'VRAD3 - Distributed Lighting Tool', 'baking light (VRAD3, GPU)'),
    (r'VIS3: Build partitioned PVS|Building map visibility', 'visibility (slow on open maps)'),
    (r'Generated clusters for \d+ regions', 'visibility: merging clusters'),
    (r'Visibility complete', 'visibility done'),
    (r'>>NAVGEN', 'nav mesh'),
    (r'CSGO Compute AI Data', 'bot data (one core, no progress lines)'),
    (r'steam ?audio|sareverb|sapaths', 'steam audio'),
    (r'Nav mesh \([^)]*\) loaded with', 'writing the map')]]
HINTS = [
    ('.vpk Failed', 'the compiled map is locked, usually because CS2 or Hammer has it loaded: load another map (or close the tools) and build again'),
    ('No lightmap resolution volumes', 'add a mesh with materials/tools/toolslightmapres.vmat over the play area for a proper lightmap resolution'),
    ('Too many charts', 'more lightmap charts than a 2048 atlas holds: merge or drop small render-only pieces, or split the map'),
    ('no walkable seeds present', 'the nav mesh is EMPTY: add point_nav_walkable / func_nav_markup WALKABLESEED on the floor near spawns'),
    ('Unable to remove', 'another light bake of this addon was running (one _vrad3 folder per addon): build again when it is done'),
    ('unrecognized parent', 'a parented entity was dropped by the compiler: check parentname values (fgdcheck.py reports key_target)'),
    ('Failed to create physics hulls', 'some meshes got no physics hull: look for missing collision in game'),
    ('RESOURCE COMPILE ERROR', 'an asset failed to compile: see errors; recompile it alone with "rcompile.py asset <file>" to read its own log'),
]
GPU_KEYS = ('gpu hang', 'device_lost', 'ray tracing', 'raytracing', 'vk_error', 'no suitable gpu')
GPU_HINT = 'baked light needs a GPU with hardware ray tracing and a current driver; without one use preset fast or nav'


def cs2_root():
    return os.environ.get('CS2_ROOT') or CS2_DEFAULT


def compiler_path(cs2=None):
    return os.path.join(cs2 or cs2_root(), 'game', 'bin', 'win64', 'resourcecompiler.exe')


def threads_default():
    return max(1, (os.cpu_count() or 4) - 2)       # leave room for the game, as build_maps.ps1 does


def preset_flags(preset, threads=None, novis=False):
    if preset not in PRESETS: raise ValueError('preset must be one of %s' % ', '.join(PRESETS))
    t = str(threads or threads_default())
    flags = [x.replace('{t}', t) for x in PRESETS[preset]]
    return [f for f in flags if f != '-vis'] if novis else flags


def map_argv(vmap, preset='fast', threads=None, novis=False, cs2=None, outroot=None):
    t = str(threads or threads_default())
    argv = [compiler_path(cs2), '-threads', t] + BASE + ['-i', _real(vmap)] + preset_flags(preset, t, novis) + TAIL
    if outroot: argv += ['-outroot', outroot]
    return argv


def _real(p):
    """the compiler finds the addon from the path, so junctions (C:\\source1\\links\\...) are resolved first"""
    return os.path.realpath(p).replace('\\', '/')


def asset_argv(paths, force=False, cs2=None, threads=None):
    argv = [compiler_path(cs2), '-threads', str(threads or threads_default()), '-nop4', '-quiet']
    for p in paths: argv += ['-i', _real(p)]
    return argv + (['-f'] if force else [])


def read_log(path):
    """a log as text: build_maps.ps1's Tee-Object writes UTF-16 with a BOM on Windows PowerShell 5.1"""
    with open(path, 'rb') as f: raw = f.read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'): return raw.decode('utf-16', 'replace')
    if raw[:3] == b'\xef\xbb\xbf': raw = raw[3:]
    return raw.decode('utf-8', 'replace')


def addon_and_map(vmap):
    """(addon, map name) from <CS2>/content/csgo_addons/<addon>/maps/<map>.vmap (or <addon>/maps/<map>.vmap through a junction)"""
    parts = os.path.normpath(os.path.abspath(vmap)).split(os.sep)
    low = [p.lower() for p in parts]
    name = os.path.splitext(parts[-1])[0]
    if 'csgo_addons' in low:
        i = len(low) - 1 - low[::-1].index('csgo_addons')
        return parts[i + 1], name
    return (parts[-3] if len(parts) > 2 and low[-2] == 'maps' else None), name


def compiled_map(vmap, cs2=None):
    """the .vpk the compiler writes for this map (subfolders under maps/ kept)"""
    addon, name = addon_and_map(vmap)
    if not addon: return None
    parts = os.path.normpath(os.path.abspath(vmap)).split(os.sep)
    low = [p.lower() for p in parts]
    i = len(low) - 1 - low[::-1].index('maps') if 'maps' in low[:-1] else len(parts) - 1
    sub = parts[i + 1:-1]
    return os.path.join(cs2 or cs2_root(), 'game', 'csgo_addons', addon, 'maps', *sub, name + '.vpk')


def plain(text):
    """build logs as plain lines: Hammer's builds log with -html (escaped text, <br/> line breaks, <font> colours)"""
    if '<br' in text or '<font' in text:
        text = re.sub(r'<[^>\n]{1,80}>', '', re.sub(r'<br\s*/?>', '\n', text))
    return html.unescape(text)


def _dedupe(items, limit):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x); out.append(x)
    return out[:limit], len(seen)


def analyze(text):
    """what a build or compile log says: summary, errors, warnings, missing assets, stage, nav areas, hints"""
    text = plain(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    summary = None
    for m in _SUMMARY.finditer(text):
        summary = {'compiled': int(m.group(1)), 'failed': int(m.group(2)), 'skipped': int(m.group(3) or 0)}
    errors, n_err = _dedupe([ln for ln in lines if _ERROR.search(ln) and not _NOISE.search(ln) and 'Failed loading resource' not in ln], 40)
    warnings, n_warn = _dedupe([ln for ln in lines if _WARN.search(ln) and not _NOISE.search(ln)], 40)
    missing = set()
    for rx in _MISSING:
        for m in rx.finditer(text):
            p = m.group(1).strip().replace('\\', '/')
            missing.add(p[:-2] if p.endswith('_c') else p)
    missing -= {'scripts/detail_prop_types.vdata'}
    stage, best = None, -1
    for rx, label in STAGES:
        for m in rx.finditer(text):
            if m.start() > best: best, stage = m.start(), label
    low = text.lower()
    hints = [h for key, h in HINTS if key.lower() in low]
    crashed = any('.mdmp' in e.lower() or 'access violation' in e.lower() or '0xc0000005' in e.lower() for e in errors)
    if any(k in e.lower() for e in errors for k in GPU_KEYS): hints.append(GPU_HINT)
    out = {'summary': summary, 'errors': errors, 'error_count': n_err, 'warnings': warnings, 'warning_count': n_warn,
           'compile_errors': sorted(set(_COMPILE_ERR.findall(text)))[:40], 'missing_assets': sorted(missing)[:60],
           'stage': stage, 'crashed': crashed, 'hints': hints}
    nav = _NAV.findall(text)
    if nav: out['nav_areas'] = int(nav[-1])
    return out


def _run(argv, log, timeout, cwd=None):
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)          # no console window: never take focus from a fullscreen game
    t0 = time.time()
    with open(log, 'w', encoding='utf-8', errors='replace') if log else open(os.devnull, 'w') as f:
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, creationflags=flags,
                             text=True, encoding='utf-8', errors='replace')
        chunks = []
        try:
            for line in p.stdout:
                chunks.append(line); f.write(line); f.flush()
                if timeout and time.time() - t0 > timeout:
                    p.kill(); chunks.append('[rcompile] killed after %d s\n' % timeout); break
        finally:
            code = p.wait()
    return code, ''.join(chunks), round(time.time() - t0, 1)


def build_map(vmap, preset='fast', threads=None, novis=False, log=None, timeout=None, cs2=None):
    rc = compiler_path(cs2)
    if not os.path.exists(rc): raise FileNotFoundError('resourcecompiler.exe not found at %s' % rc)
    if not os.path.exists(vmap): raise FileNotFoundError(vmap)
    vpk = compiled_map(vmap, cs2)
    if preset in PARTIAL and not (vpk and os.path.exists(vpk)):
        raise RuntimeError('preset %s updates an existing build, and %s does not exist: build full first' % (preset, vpk))
    t0 = time.time()
    code, text, secs = _run(map_argv(vmap, preset, threads, novis, cs2), log, timeout, os.path.dirname(rc))
    res = analyze(text)
    fresh = bool(vpk and os.path.exists(vpk) and os.path.getmtime(vpk) >= t0 - 2)
    res.update({'exit_code': code, 'seconds': secs, 'output': vpk if fresh else None, 'preset': preset,
                'ok': code == 0 and fresh and not (res['summary'] or {}).get('failed') and not res['crashed']})
    if code == 0 and not fresh: res['note'] = 'the compiler exited 0 but wrote no new .vpk (%s)' % vpk
    return res


def compile_assets(paths, force=False, log=None, timeout=600, cs2=None):
    rc = compiler_path(cs2)
    if not os.path.exists(rc): raise FileNotFoundError('resourcecompiler.exe not found at %s' % rc)
    missing = [p for p in paths if not os.path.exists(p)]
    if missing: raise FileNotFoundError(', '.join(missing))
    code, text, secs = _run(asset_argv(paths, force, cs2), log, timeout, os.path.dirname(rc))
    res = analyze(text)
    res.update({'exit_code': code, 'seconds': secs, 'ok': code == 0 and not (res['summary'] or {}).get('failed') and not res['crashed']})
    return res


def _print(res, as_json):
    if as_json: print(json.dumps(res, indent=1)); return
    s = res.get('summary') or {}
    print('ok: %s  exit: %s  %s compiled, %s failed  stage: %s' % (res.get('ok', '-'), res.get('exit_code', '-'), s.get('compiled', '?'),
                                                               s.get('failed', '?'), res.get('stage') or '-'))
    for k in ('compile_errors', 'errors', 'missing_assets', 'hints'):
        for x in res.get(k) or []: print('%s\t%s' % (k, x))
    if 'nav_areas' in res: print('nav_areas\t%d' % res['nav_areas'])
    if res.get('output'): print('output\t%s' % res['output'])
    if res.get('note'): print('note\t%s' % res['note'])


def main(argv=None):
    ap = argparse.ArgumentParser(description='resourcecompiler wrapper and log reader')
    sub = ap.add_subparsers(dest='cmd', required=True)
    a1 = sub.add_parser('asset'); a1.add_argument('paths', nargs='+'); a1.add_argument('--force', action='store_true')
    a2 = sub.add_parser('map'); a2.add_argument('vmap'); a2.add_argument('--preset', default='fast', choices=list(PRESETS))
    a2.add_argument('--novis', action='store_true'); a2.add_argument('--threads', type=int); a2.add_argument('--dry-run', action='store_true')
    a2.add_argument('--timeout', type=float)
    a3 = sub.add_parser('analyze'); a3.add_argument('log')
    sub.add_parser('presets')
    for p in (a1, a2, a3): p.add_argument('--json', action='store_true')
    for p in (a1, a2): p.add_argument('--log')
    a = ap.parse_args(argv)
    if a.cmd == 'presets':
        for k in PRESETS: print('%-9s %s' % (k, ' '.join(preset_flags(k))))
        return 0
    if a.cmd == 'analyze':
        res = analyze(read_log(a.log)); _print(res, a.json)
        return 1 if (res['summary'] or {}).get('failed') or res['crashed'] else 0
    if a.cmd == 'map' and a.dry_run:
        print(subprocess.list2cmdline(map_argv(a.vmap, a.preset, a.threads, a.novis))); return 0
    try:
        res = build_map(a.vmap, a.preset, a.threads, a.novis, a.log, a.timeout) if a.cmd == 'map' else compile_assets(a.paths, a.force, a.log)
    except (FileNotFoundError, RuntimeError, ValueError) as ex:
        print('rcompile: %s' % ex, file=sys.stderr); return 2
    _print(res, a.json)
    return 0 if res['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
