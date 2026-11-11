"""MCP server (stdio, JSON-RPC 2.0, no dependencies) exposing skink52's CS2 map tools to any MCP client (Claude Code, Claude Desktop ...).

  python tools/mcp_server.py                 serve on stdin / stdout (one JSON message per line; logs go to stderr)
  python tools/mcp_server.py --list          print the tool names and exit

Register it, e.g. in Claude Code (from C:\\source1):  claude mcp add cs2mapping -- python C:\\source1\\cs2mapping\\tools\\mcp_server.py
(on the PC the tools run from C:\\source1\\cs2port\\tools; point at that copy if it is the deployed one).

Tools (read-only unless marked WRITES):
  guide                 list / read this repo's docs (tool index, pipeline, gotchas, creation guide) a section at a time
  list_maps             addons and their .vmap files under <CS2>/content/csgo_addons (one folder level, never recursive)
  map_info              entity counts by class, mesh / material counts, world bounds
  entity_info           an entity class from the installed FGDs (keys, defaults, choices, I/O), or a search
  validate_map          fgdcheck.py: classes, keys, values, I/O, key targets, missing assets
  check_map_problems    mapcheck.py report (no fixes): excluded / unknown classes, dangling I/O, switched static lights, overflow ...
  sanity_check          mapsanity.py: spawns on floors with headroom, sun / sky, probes, lightmap res, nav seeds, buyzones
  analyze_build_log     rcompile.py analyze: errors, missing assets, stage, hints of a build / compile log
  stage_pass            WRITES <root>/out: run_pass.py (stage C steps), stage_d.py (stage D passes) or stage_c.py on a port root (job)
  build_map             WRITES the game addon: rcompile.py map with a preset (job; dry_run shows the command)
  compile_assets        WRITES the game addon: rcompile.py asset on content files (job)
  job_status            state, exit code, log tail and parsed result of a job
  job_cancel            STOPS a running job (kills its process; partial output may be left behind)
  map_backups           WRITES the backup store: tiered compressed copies (mapbackup.py): list, save, restore, pin, scan
  visual_check          visualcheck.py: floating props, props in walls / each other, z-fighting, open meshes
  release_plan          release.py dry run: the files a one-map release addon needs, missing / stale compiled files, PUBLISH.md
  prop_search, prop_note  stock prop atlas (propatlas.py) with real sizes and your own notes
  material_create       WRITES the addon: create/matkit.py (patterns, photos, variants, signs, decals; glass / water / emissive)
  sound_create          WRITES the addon: create/sndkit.py (synth presets or WAV import + a sound event)
  model_build           WRITES the addon: create/blenderkit.py (headless Blender templates / scripts / imports; dry run by default)
  mechanics_build       WRITES the addon: create/mechkit.py (abilities, minigames, drone / car / turret, weapons, hide and seek, story,
                        modes; tested on the mock engine first)
  status, catalog_info  what is installed; what the generators offer (styles, presets, themes, modes, kits, templates ...)
  script_api            search Valve's cs_script declarations (point_script.d.ts)
  script_write          WRITES <content>/maps/scripts/<name>.js after node --check and a mock-engine run
  asset_search          stock (and addon) materials / models / sounds / particles by words
  map_edit              WRITES a map: create/mapops.py batch (primitives, mesh edits + CSG + UVs, entities and I/O, layouts, buildings,
                        streets, kits, competitive plans, courses, effects, mechanics) as a job; backs the map up before overwriting it
  + live-game tools from autoport/: any autoport/*.py that defines MCP_TOOLS (see below) is imported and its tools are added.

Live-game plug-in contract (for autoport's VConsole / launch / playtest modules): a module-level
  MCP_TOOLS = [{'name': str, 'description': str, 'inputSchema': {JSON schema}, 'fn': callable(**arguments) -> JSON-able}]
Only files whose text contains "MCP_TOOLS" are imported, so nothing else in autoport/ runs. Names clashing with ours are skipped.

Long work (builds, stage passes) runs as a background job so the client is never blocked: the call waits up to `wait` seconds (default 20),
then returns the job id; poll job_status. Child processes start without a console window (no focus stealing).

The idea of an MCP server in front of CS2 map tools, its tool split (validate / build / job_status / guide by section) and the job pattern come
from cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT), which uses the MCP Python SDK; this is a fresh, stdlib-only server over
skink52's own tools. Protocol: modelcontextprotocol.io specification 2025-06-18 (stdio transport, lifecycle, tools).
"""
import glob, io, json, os, re, subprocess, sys, threading, time, traceback, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

SERVER = {'name': 'cs2mapping', 'title': "skink52's CS2 map tools", 'version': '1.0.0'}
VERSIONS = ['2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05']   # newest first
INSTRUCTIONS = ('CS2 map tools for ports and original addons. Read-only checks first (validate_map, check_map_problems, sanity_check), '
                'then stage_pass / build_map, which run as jobs: poll job_status. guide() lists the repo docs; read tools/README.md for '
                'what each port pass does before running one.')
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def log(*a):
    print('[cs2mapping-mcp]', *a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------------------------------------ jobs
class Job:
    def __init__(self, kind, title, argv, cwd, parse=None, timeout=None):
        self.id = '%s-%s' % (kind, uuid.uuid4().hex[:8])
        self.kind, self.title, self.argv, self.cwd, self.parse, self.timeout = kind, title, argv, cwd, parse, timeout
        self.lines, self.code, self.started, self.ended, self.proc, self.error = [], None, time.time(), None, None, None
        self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()

    def _run(self):
        try:
            self.proc = subprocess.Popen(self.argv, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         text=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW)
            for line in self.proc.stdout:
                self.lines.append(line.rstrip('\n'))
                if self.timeout and time.time() - self.started > self.timeout:
                    self.proc.kill(); self.lines.append('[job] killed after %d s' % self.timeout); break
            self.code = self.proc.wait()
        except Exception as ex:
            self.error = str(ex); self.code = -1
        self.ended = time.time()

    def state(self, tail=20):
        running = self.ended is None
        out = {'job': self.id, 'title': self.title, 'state': 'running' if running else ('done' if self.code == 0 else 'failed'),
               'exit_code': self.code, 'seconds': round((self.ended or time.time()) - self.started, 1), 'lines': len(self.lines),
               'log_tail': self.lines[-tail:] if tail else []}
        if self.error: out['error'] = self.error
        if not running and self.parse:
            try: out['result'] = self.parse('\n'.join(self.lines))
            except Exception as ex: out['result_error'] = str(ex)
        return out


JOBS = {}


def start_job(kind, title, argv, cwd, wait=20, parse=None, timeout=None):
    j = Job(kind, title, argv, cwd, parse, timeout)
    JOBS[j.id] = j
    j.thread.join(max(0.0, float(wait or 0)))
    return j.state()


# ------------------------------------------------------------------------------------------------ tools
TOOLS = {}


# Tools that can replace or delete something that already exists (a map, a script, compiled or generated files, a backup): for these
# destructiveHint is true. A writer not listed only adds (prop_note keeps its own notes file). Everything else is read-only.
# Stopping a job counts: a compile or a map edit killed half way leaves partial output behind, so job_cancel is destructive, and so is
# job_status, which still takes cancel=true for older clients (a hint describes the most a tool can do, not its usual call).
DESTRUCTIVE = {'stage_pass', 'build_map', 'compile_assets', 'map_backups', 'material_create', 'sound_create', 'model_build', 'mechanics_build',
               'map_edit', 'script_write', 'job_status', 'job_cancel'}


def tool(name, description, props=None, required=(), writes=False):
    def deco(fn):
        schema = {'type': 'object', 'properties': props or {}, 'additionalProperties': False}
        if required: schema['required'] = list(required)
        TOOLS[name] = {'name': name, 'description': description, 'inputSchema': schema, 'fn': fn,
                       'annotations': {'readOnlyHint': not writes, 'destructiveHint': bool(writes and name in DESTRUCTIVE), 'openWorldHint': False}}
        return fn
    return deco


S = lambda d, **k: dict({'type': 'string', 'description': d}, **k)
B = lambda d: {'type': 'boolean', 'description': d}
N = lambda d: {'type': 'number', 'description': d}


def cs2():
    import fgdcat
    return fgdcat.cs2_root()


def _vmap(path):
    if not path or not path.lower().endswith('.vmap'): raise ValueError('give the path of a .vmap file')
    if not os.path.exists(path): raise FileNotFoundError(path)
    return path


def _docs():
    out = {}
    for p in [os.path.join(REPO, 'tools', 'README.md'), os.path.join(REPO, 'create', 'README.md'), os.path.join(REPO, 'autoport', 'README.md'),
              os.path.join(REPO, 'CAPABILITIES.md')] + sorted(glob.glob(os.path.join(REPO, 'docs', '*', '*.md'))):
        if os.path.exists(p): out[os.path.relpath(p, REPO).replace('\\', '/')] = p
    return out


@tool('guide', 'Repo docs one at a time. No doc: the list of docs with their first heading. doc: the file (paged by offset).',
      {'doc': S('a path from the list, e.g. tools/README.md or docs/reference/cs2-gotchas.md'), 'offset': N('character offset'),
       'length': N('characters to return (default 20000)')})
def t_guide(doc=None, offset=0, length=20000):
    docs = _docs()
    if not doc:
        def head(p):
            with open(p, encoding='utf-8', errors='replace') as f:
                for ln in f:
                    if ln.startswith('#'): return ln.strip('# \n')
            return ''
        return {'docs': [{'doc': k, 'title': head(v)} for k, v in docs.items()]}
    key = doc.replace('\\', '/').lstrip('/')
    if key not in docs: raise ValueError('unknown doc %r; call guide() for the list' % doc)
    with open(docs[key], encoding='utf-8', errors='replace') as f: t = f.read()
    o, n = int(offset or 0), int(length or 20000)
    return {'doc': key, 'size': len(t), 'offset': o, 'text': t[o:o + n], 'more': o + n < len(t)}


@tool('list_maps', 'Addons under <CS2>/content/csgo_addons and their maps (maps/*.vmap, one level). addon limits it to one addon.',
      {'addon': S('addon folder name'), 'contains': S('only addons whose name contains this')})
def t_list_maps(addon=None, contains=None):
    root = os.path.join(cs2(), 'content', 'csgo_addons')
    if not os.path.isdir(root): raise FileNotFoundError(root)
    names = [addon] if addon else sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)))
    if contains: names = [n for n in names if contains.lower() in n.lower()]
    out = []
    for n in names:
        maps = sorted(glob.glob(os.path.join(root, n, 'maps', '*.vmap')))
        out.append({'addon': n, 'maps': [{'path': p, 'mb': round(os.path.getsize(p) / 1e6, 2)} for p in maps]})
    return {'content_root': root, 'addons': out}


@tool('map_info', 'Summary of a .vmap: entity counts by class, named entities, meshes, materials, world bounds.',
      {'vmap': S('path of the .vmap'), 'top': N('how many classes to list (default 40)')}, ['vmap'])
def t_map_info(vmap, top=40):
    import collections, vmapedit as V
    m = V.Map(_vmap(vmap))
    ents = m.entities()
    counts = collections.Counter(m.cls(e) for e in ents)
    meshes = [n for n, _ in m.walk() if m.type(n) == b'CMapMesh']
    mats = set()
    for n in meshes:
        md = m.g(n, b'meshData')
        for x in (m.g(md, b'materials') or []) if md is not None else []:
            mats.add(x.decode('utf-8', 'replace') if isinstance(x, (bytes, bytearray)) else str(x))
    lo, hi = [1e18] * 3, [-1e18] * 3
    for n in meshes:
        for p in m.mesh_points(n):
            for i in range(3): lo[i] = min(lo[i], p[i]); hi[i] = max(hi[i], p[i])
    return {'map': os.path.basename(vmap), 'entities': len(ents), 'named': sum(1 for e in ents if m.name(e)),
            'classes': dict(counts.most_common(int(top or 40))), 'class_count': len(counts), 'meshes': len(meshes),
            'materials': len(mats), 'bounds': [lo, hi] if meshes else None}


@tool('entity_info', 'An entity class from the installed CS2 FGDs (kind, keys with type / default / choices, inputs, outputs), or classes '
      'matching search.', {'classname': S('e.g. trigger_multiple'), 'search': S('text in a class name or description'),
                           'keys': B('include the key list (default true)')})
def t_entity_info(classname=None, search=None, keys=True):
    import fgdcat
    cat = fgdcat.load()
    if search:
        return {'matches': [{'classname': n, 'kind': k, 'description': d[:200]} for n, k, d in cat.search(search)]}
    if not classname: raise ValueError('give classname or search')
    d = cat.describe(classname)
    if keys is False: d.pop('keyvalues', None)
    return d


@tool('validate_map', 'fgdcheck.py on a .vmap (read-only): unknown / excluded classes, unknown keys, bad values and choices, bad I/O, '
      'dangling targets, key targets naming nothing, missing assets and mesh materials.',
      {'vmap': S('path of the .vmap'), 'assets': B('check assets too (default true)'), 'addon': S('addon name if not under csgo_addons'),
       'only': S('comma-separated codes to keep'), 'limit': N('max findings returned (default 200)')}, ['vmap'])
def t_validate(vmap, assets=True, addon=None, only=None, limit=200):
    import fgdcheck
    res = fgdcheck.run(_vmap(vmap), addon, assets is not False)
    if only:
        keep = set(only.split(',')); res['findings'] = [f for f in res['findings'] if f['code'] in keep]
    res['returned'] = min(len(res['findings']), int(limit or 200)); res['findings'] = res['findings'][:int(limit or 200)]
    return res


@tool('check_map_problems', "mapcheck.py's report (read-only, nothing fixed): excluded / unknown classes, dangling outputs, bad inputs / outputs, "
      'baked switched lights, discos, int overflow, item_* in game_player_equip.', {'vmap': S('path of the .vmap')}, ['vmap'])
def t_mapcheck(vmap):
    import mapcheck, vmapedit as V
    m = V.Map(_vmap(vmap))
    found, _, _ = mapcheck.check(m, fix=False)
    import collections
    return {'map': os.path.basename(vmap), 'counts': dict(collections.Counter(k for k, _ in found)),
            'findings': [{'kind': k, 'text': t} for k, t in found[:300]]}


@tool('sanity_check', 'mapsanity.py (read-only): spawns on floors with 72 u headroom and spacing, sun / sky, light probes over spawns, '
      'lightmap resolution, nav seeds, buyzones.', {'vmap': S('path of the .vmap'),
      'mode': S('classic, minigame (default), course or story', enum=['classic', 'minigame', 'course', 'story'])}, ['vmap'])
def t_sanity(vmap, mode='minigame'):
    import mapsanity
    return mapsanity.run(_vmap(vmap), mode or 'minigame')


@tool('analyze_build_log', 'Read a resourcecompiler / build_maps.ps1 / Hammer build log: summary, errors, missing assets, stage, nav areas, hints.',
      {'path': S('path of the log')}, ['path'])
def t_analyze(path):
    import rcompile
    return rcompile.analyze(rcompile.read_log(path))


@tool('stage_pass', 'WRITES <root>/out/<addon>: port passes on a cloud-style root. stage "C" runs run_pass.py with stage C step keys, '
      '"D" runs stage_d.py passes, "C-full" runs stage_c.py (all steps). Step keys: tools/README.md (guide). Runs as a job.',
      {'stage': S('C, D or C-full', enum=['C', 'D', 'C-full']), 'addon': S('addon name'), 'root': S('working root (see tools/README.md)'),
       'steps': S('comma-separated step / pass keys (not for C-full)'), 'wait': N('seconds to wait before returning (default 20)'),
       'timeout': N('kill after this many seconds (default 7200)')}, ['stage', 'addon', 'root'], writes=True)
def t_stage_pass(stage, addon, root, steps=None, wait=20, timeout=7200):
    if not os.path.isdir(root): raise FileNotFoundError(root)
    if stage != 'C-full' and not steps: raise ValueError('steps is required for stage C / D')
    if steps and not re.fullmatch(r'[A-Za-z0-9_]+(,[A-Za-z0-9_]+)*', steps): raise ValueError('steps: comma-separated keys only')
    script = {'C': 'run_pass.py', 'D': 'stage_d.py', 'C-full': 'stage_c.py'}[stage]
    argv = [sys.executable, os.path.join(HERE, script), addon, root] + ([steps] if stage != 'C-full' else [])
    return start_job('stage', '%s %s %s' % (script, addon, steps or ''), argv, HERE, wait, None, timeout)


@tool('build_map', 'WRITES game/csgo_addons/<addon>/maps: compile a .vmap with resourcecompiler (rcompile.py). Presets: fast, nav, full, final, '
      'entities, lighting. Runs as a job (full / final take many minutes; keep CS2 open from before to after, or closed). dry_run returns '
      'the command only.', {'vmap': S('path of the .vmap'), 'preset': S('preset', enum=['fast', 'nav', 'full', 'final', 'entities', 'lighting']),
      'novis': B('leave out -vis'), 'dry_run': B('only show the command'), 'wait': N('seconds to wait (default 20)'),
      'timeout': N('kill after this many seconds (default 10800)')}, ['vmap'], writes=True)
def t_build(vmap, preset='fast', novis=False, dry_run=False, wait=20, timeout=10800):
    import rcompile
    _vmap(vmap)
    if dry_run: return {'argv': rcompile.map_argv(vmap, preset or 'fast', novis=bool(novis))}
    argv = [sys.executable, os.path.join(HERE, 'rcompile.py'), 'map', vmap, '--preset', preset or 'fast', '--json'] + (['--novis'] if novis else [])
    parse = lambda text: json.loads(text[text.find('{'):]) if '{' in text else None
    return start_job('build', 'build %s (%s)' % (os.path.basename(vmap), preset), argv, HERE, wait, parse, timeout)


@tool('compile_assets', 'WRITES the game addon: compile content files (.vmat .vmdl .vtex .vpcf .vsndevts ...) with resourcecompiler. Job.',
      {'paths': {'type': 'array', 'items': {'type': 'string'}, 'description': 'content file paths'}, 'force': B('recompile even if up to date'),
       'wait': N('seconds to wait (default 60)')}, ['paths'], writes=True)
def t_compile(paths, force=False, wait=60):
    for p in paths:
        if not os.path.exists(p): raise FileNotFoundError(p)
    argv = [sys.executable, os.path.join(HERE, 'rcompile.py'), 'asset'] + list(paths) + ['--json'] + (['--force'] if force else [])
    parse = lambda text: json.loads(text[text.find('{'):]) if '{' in text else None
    return start_job('compile', 'compile %d asset(s)' % len(paths), argv, HERE, wait, parse, 1800)


def _cancel(j):
    """kill a running job's process -> True when one was killed. The job's own output (a half-built .vpk in the compiler's temp folder,
    a map edit's .part file) may be left behind; nothing already in place is removed."""
    if j.proc and j.ended is None:
        j.proc.kill(); j.lines.append('[job] cancelled'); return True
    return False


@tool('job_status', 'State of a job (running / done / failed), exit code, log tail and parsed result. No job: all jobs. Reading is all it '
      'does unless cancel=true, which stops the job like job_cancel (kept for older clients; prefer job_cancel).',
      {'job': S('job id'), 'wait': N('seconds to wait for it to finish (default 0)'), 'tail': N('log lines (default 20)'),
       'cancel': B('stop the job (deprecated: use job_cancel)')}, writes=True)
def t_job(job=None, wait=0, tail=20, cancel=False):
    if not job: return {'jobs': [j.state(0) for j in JOBS.values()]}
    j = JOBS.get(job)
    if j is None: raise ValueError('no job %r' % job)
    if cancel: _cancel(j)
    j.thread.join(max(0.0, float(wait or 0)))
    return j.state(int(tail if tail is not None else 20))


@tool('job_cancel', 'Stop a running job (a build, an asset compile, a map edit) by killing its process. What it had already written stays; '
      'a build stopped half way leaves partial output in the compiler\'s temp folder and the addon as it was. Returns the job state '
      'and whether anything was stopped.',
      {'job': S('job id'), 'wait': N('seconds to wait for the process to end (default 5)'), 'tail': N('log lines (default 20)')}, ['job'],
      writes=True)
def t_job_cancel(job, wait=5, tail=20):
    j = JOBS.get(job)
    if j is None: raise ValueError('no job %r' % job)
    stopped = _cancel(j)
    j.thread.join(max(0.0, float(wait if wait is not None else 5)))
    out = j.state(int(tail if tail is not None else 20)); out['cancelled'] = stopped
    return out


# ------------------------------------------------------------------------------------------------ round 2: backups, visuals, release, assets,
# generators, mechanics (create/ modules; the ones that write maps run in a child process: tools/dmx.py and create/dmx.py share a name)
CREATE = os.path.join(REPO, 'create')


def _create(name):
    if CREATE not in sys.path: sys.path.append(CREATE)     # appended: tools/ modules keep their names
    import importlib
    return importlib.import_module(name)


A = lambda d, items=None: {'type': 'array', 'description': d, **({'items': items} if items else {})}
O = lambda d: {'type': 'object', 'description': d}


@tool('map_backups', 'Tiered compressed map backups (tools/mapbackup.py). action: list (default), save, restore (to=path writes elsewhere; '
      'restoring over the map first backs it up), pin, scan (every changed map of a content addon).',
      {'action': S('list, save, restore, pin, scan', enum=['list', 'save', 'restore', 'pin', 'scan']), 'vmap': S('map path (save / list / restore)'),
       'stamp': S('backup stamp (restore / pin; restore defaults to latest)'), 'to': S('restore into this file instead'),
       'label': S('pin label'), 'addon_content': S('content addon folder (scan)'), 'store': S('backup store folder')}, writes=True)
def t_backups(action='list', vmap=None, stamp=None, to=None, label='pinned', addon_content=None, store=None):
    import mapbackup
    st = mapbackup.Store(store)
    if action == 'scan': return {'saved': st.scan(addon_content)}
    if not vmap: raise ValueError('vmap is required')
    if action == 'save': return st.save(vmap, 'mcp') or {'skipped': 'same bytes as the newest copy'}
    if action == 'restore': return st.restore(vmap, stamp or 'latest', to)
    if action == 'pin': st.pin(vmap, stamp, label); return {'pinned': stamp}
    return {'store': st.root, 'backups': st.entries(vmap)}


@tool('visual_check', 'visualcheck.py (read-only): floating props, props in walls / in each other, z-fighting, open meshes. Reads stock '
      'model bounds with Node (cached). box limits it to x0,y0,z0,x1,y1,z1.',
      {'vmap': S('path of the .vmap'), 'box': A('[x0, y0, z0, x1, y1, z1]', {'type': 'number'}), 'zfight': B('include z-fighting (default true)'),
       'limit': N('max findings (default 200)')}, ['vmap'])
def t_visual(vmap, box=None, zfight=True, limit=200):
    import visualcheck
    b = (box[:3], box[3:]) if box else None
    return visualcheck.run(_vmap(vmap), None, zfight is not False, b, limit=int(limit or 200))


@tool('release_plan', 'Plan a one-map release addon (tools/release.py, DRY RUN: nothing is copied or uploaded): every addon file the map '
      'uses, compiled files missing or stale, missing references, upload size and the PUBLISH.md text.',
      {'vmap': S('path of the .vmap'), 'name': S('new addon name (default: the map name)'), 'files': B('include the file lists (default false)')}, ['vmap'])
def t_release(vmap, name=None, files=False):
    import release
    s = release.Plan(_vmap(vmap), name).build().summary()
    if not files:
        for k in ('sources', 'compiled'): s[k] = len(s[k])
    return s


@tool('prop_search', 'Stock prop atlas (tools/propatlas.py): models whose path (or your note tags) has every word; sizes=true adds real bounds.',
      {'words': S('e.g. "wood crate"'), 'limit': N('max results (default 30)'), 'sizes': B('read bounds (Node)')}, ['words'])
def t_props(words, limit=30, sizes=False):
    import propatlas
    return propatlas.Atlas().search(words, int(limit or 30), bool(sizes))


@tool('prop_note', 'Keep a note on a stock model (category, tags, front axis, mount) for later searches.',
      {'model': S('models/...vmdl'), 'category': S('category'), 'tags': A('tags', {'type': 'string'}), 'front': S('+x, -x, +y or -y'),
       'mount': S('floor, wall or ceiling'), 'text': S('free text')}, ['model'], writes=True)
def t_prop_note(model, category=None, tags=None, front=None, mount=None, text=None):
    import propatlas
    return propatlas.Atlas().note(model, category, tags or [], front, mount, text)


@tool('material_create', 'Write a material into an addon (create/matkit.py): source pattern (solid, noise, bricks, tiles, planks, checker, stripes, '
      'plaster, cobbles), image (a photo: crop, delight, seamless), variant (tint / saturation / brightness of a _color.png), sign (text plate) '
      'or decal (text or transparent image). kind: complex, emissive, glass, water, decal.',
      {'content': S('addon content folder'), 'name': S('material name'), 'source': S('pattern, image, variant, sign or decal',
       enum=['pattern', 'image', 'variant', 'sign', 'decal']), 'value': S('the pattern name, image path, source png or text'),
       'color': S('#rrggbb'), 'color2': S('#rrggbb'), 'kind': S('complex, emissive, glass, water, decal'), 'dir': S('materials/<sub> (default materials/gen)'),
       'roughness': N('0..1'), 'tint': S('#rrggbb (variant)'), 'saturation': N('variant'), 'brightness': N('variant')},
      ['content', 'name', 'source', 'value'], writes=True)
def t_material(content, name, source, value, color=None, color2=None, kind=None, dir='materials/gen', roughness=None, tint=None,
               saturation=1.0, brightness=1.0):
    mk = _create('matkit')
    h = None
    if source == 'pattern': alb, h = mk.generate(value, 512, color, color2)
    elif source == 'image': alb, h = mk.from_image(value)
    elif source == 'variant': alb = mk.variant(value, tint, saturation, brightness)
    else: alb = mk.text_image(value, (512, 128), color or '#203040', '#101010' if source == 'decal' else '#f0f0e8', transparent=source == 'decal')
    kind = kind or ('decal' if source == 'decal' else 'complex')
    return {'material': mk.write_material(content, dir, name, alb, h, kind, roughness)}


@tool('sound_create', 'Synthesise (preset: beep, alarm, hum, wind, rain, drone, click, whoosh, rumble, charge, zap) or import a WAV into '
      '<content>/sounds/gen/, then optionally add a sound event (kind 3d, flat or music) to soundevents_addon.vsndevts (create/sndkit.py).',
      {'content': S('addon content folder'), 'name': S('sound name'), 'preset': S('preset'), 'file': S('WAV to import instead'),
       'seconds': N('length'), 'loop': B('loop markers'), 'event': S('event name to add'), 'event_kind': S('3d, flat or music'),
       'range': N('3d: silent at this distance')}, ['content', 'name'], writes=True)
def t_sound(content, name, preset=None, file=None, seconds=2.0, loop=False, event=None, event_kind='3d', range=2000):
    sk = _create('sndkit')
    if file:
        x, rate = sk.read_wav(file); rel = sk.write(content, name, sk.resample(x, rate), bool(loop))
    else:
        rel = sk.write(content, name, sk.synth(preset or 'beep', float(seconds or 2)), bool(loop))
    out = {'vsnd': rel}
    if event: out['event'] = sk.event(content, event, rel, event_kind or '3d', float(range or 2000))
    return out


@tool('model_build', 'A prop through headless Blender (create/blenderkit.py): template (crate, barrel, pallet, table, lamp, pipe, sandbags, fence), '
      'a bpy script or an import (.obj .fbx .glb .blend) -> FBX + collision + .vmdl. dry_run (default true) writes nothing and returns the script, the vmdl text and the files it would '
      'write; dry_run false with blender false writes the script and vmdl only; dry_run false runs Blender.',
      {'content': S('addon content folder'), 'name': S('model name'), 'template': S('template'), 'size': A('[W, D, H]', {'type': 'number'}),
       'script': S('bpy script path'), 'import_file': S('model file'), 'material': S('vmat path'), 'dry_run': B('write nothing (default true)'), 'blender': B('start Blender when not a dry run (default true)')},
      ['content', 'name'], writes=True)
def t_model(content, name, template=None, size=None, script=None, import_file=None, material='materials/dev/reflectivity_50.vmat', dry_run=True, blender=True):
    bk = _create('blenderkit')
    return bk.build(content, name, template, tuple(size) if size else None, script, import_file, material, dry_run=dry_run is not False,
                    no_blender=blender is False)


@tool('mechanics_build', 'cs_script mechanics (create/mechkit.py): bundle abilities / minigames / controls / weapons / hideseek / story / mode '
      'from a config into maps/scripts/<name>.js + a themed HUD in the addon; test=true runs it on the mock engine first (Node).',
      {'config': O('mechkit config'), 'content': S('addon content folder (omit to only test)'), 'name': S('script name (default mech)'),
       'test': B('run on the mock engine (default true)'), 'seconds': N('mock seconds (default 40)')}, ['config'], writes=True)
def t_mech(config, content=None, name='mech', test=True, seconds=40):
    mk = _create('mechkit')
    out = {}
    if test is not False:
        code, text = mk.test(config, int(seconds or 40))
        out['mock'] = {'exit_code': code, 'tail': text.strip().splitlines()[-6:]}
        if code != 0: out['written'] = []; return out
    if content: out['written'] = mk.build(config, content, name or 'mech')
    return out


@tool('map_edit', 'WRITES a map: run a batch of create/ operations (create/mapops.py: primitives, mesh_edit with bevel / CSG / UV / paint, '
      'entity, connect, brush, layout, building, street_front, district, street, junction, fence, bank, scatter, kit, competitive, course, fx, '
      'mechanics) on in_vmap and save out_vmap. All or nothing; the nodes go in vis group `group`, which a re-run replaces; overwriting the '
      'input backs it up first. dry_run checks the batch without saving. Hammer must not have the map open.',
      {'in_vmap': S('source .vmap'), 'out_vmap': S('output .vmap (may be the same)'), 'ops': A('operations', {'type': 'object'}),
       'group': S('vis group (default gen)'), 'content': S('addon content folder (default: the folder above maps/)'), 'dry_run': B('do not save'),
       'wait': N('seconds to wait (default 60)')}, ['in_vmap', 'out_vmap', 'ops'], writes=True)
def t_map_edit(in_vmap, out_vmap, ops, group='gen', content=None, dry_run=False, wait=60):
    _vmap(in_vmap)
    job = {'in': in_vmap, 'out': out_vmap, 'ops': ops, 'group': group or 'gen', 'dry_run': bool(dry_run)}
    if content: job['content'] = content
    import tempfile
    fd, path = tempfile.mkstemp(prefix='mapops_', suffix='.json'); os.close(fd)
    with open(path, 'w', encoding='utf-8') as f: json.dump(job, f)
    parse = lambda text: json.loads(text.strip().splitlines()[-1]) if text.strip() else None
    return start_job('map_edit', 'map_edit %s (%d ops)' % (os.path.basename(out_vmap), len(ops)),
                     [sys.executable, os.path.join(CREATE, 'mapops.py'), path], CREATE, wait, parse, 1800)


@tool('status', 'What is installed: CS2 path, resourcecompiler, FGDs, VPKs, Node (for bounds and the mock engine), Blender, the backup store.')
def t_status():
    import fgdcat, rcompile, mapbackup, shutil as sh
    root = fgdcat.cs2_root()
    bk = _create('blenderkit')
    return {'cs2': root, 'cs2_found': os.path.isdir(root), 'resourcecompiler': os.path.exists(rcompile.compiler_path(root)),
            'fgd_files': len(fgdcat.fgd_paths(root)), 'vpks': [s for s in ('csgo', 'core') if os.path.exists(os.path.join(root, 'game', s, 'pak01_dir.vpk'))],
            'node': sh.which('node'), 'blender': bk.find_blender(), 'backup_store': mapbackup.default_store(), 'tools': len(TOOLS)}


@tool('script_api', "Search Valve's cs_script API declarations (create/test/point_script.d.ts) for a word: matching lines with their context.",
      {'query': S('e.g. Teleport, OnPlayerJump, CustomHudLayout'), 'limit': N('max hits (default 20)')}, ['query'])
def t_script_api(query, limit=20):
    path = os.path.join(CREATE, 'test', 'point_script.d.ts')
    with open(path, encoding='utf-8') as f: lines = f.read().splitlines()
    q = query.lower(); hits = []
    for i, ln in enumerate(lines):
        if q in ln.lower() and not ln.strip().startswith(('*', '/**')):
            ctx = [l.strip() for l in lines[max(0, i - 3):i] if l.strip().startswith(('*', '/**'))]
            hits.append({'line': i + 1, 'decl': ln.strip(), 'doc': ' '.join(c.strip('/* ') for c in ctx)[:300]})
            if len(hits) >= int(limit or 20): break
    return {'file': 'create/test/point_script.d.ts', 'hits': hits}


@tool('script_write', 'WRITES <content>/maps/scripts/<name>.js after checking it: JavaScript syntax (node --check) and a run on the mock engine '
      '(create/test/mock_point_script.mjs). Refuses to write a script that fails unless force=true.',
      {'content': S('addon content folder'), 'name': S('script name'), 'code': S('the cs_script source'), 'seconds': N('mock seconds (default 30)'),
       'force': B('write even if the checks fail')}, ['content', 'name', 'code'], writes=True)
def t_script_write(content, name, code, seconds=30, force=False):
    import shutil as sh, tempfile
    import safepath
    try: safepath.addon_name(name)                   # the script's file name: one component, so it stays in maps/scripts
    except ValueError as ex: return {'error': 'bad script name: %s' % ex}
    node = sh.which('node')
    out = {}
    if node:
        with tempfile.TemporaryDirectory(prefix='script_') as d:
            js = os.path.join(d, name + '.js')
            with open(js, 'w', encoding='utf-8') as f: f.write(code)
            r = subprocess.run([node, os.path.join(CREATE, 'test', 'mock_point_script.mjs'), js, 'players=6', 'seconds=%d' % int(seconds or 30)],
                               capture_output=True, text=True, timeout=600, creationflags=NO_WINDOW)
            out['mock'] = {'exit_code': r.returncode, 'tail': (r.stdout + r.stderr).strip().splitlines()[-8:]}
    else:
        out['mock'] = 'node not found: not checked'
    ok = not node or out['mock']['exit_code'] == 0
    if ok or force:
        p = os.path.join(content, 'maps', 'scripts', name + '.js'); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='\n') as f: f.write(code)
        out['written'] = p; out['cs_script_key'] = 'maps/scripts/%s.vjs' % name
    return out


@tool('asset_search', 'Stock CS2 assets by words in their path: kind material, model, sound, particle (pak01 file lists; addon files with '
      'addon_content).', {'kind': S('material, model, sound or particle', enum=['material', 'model', 'sound', 'particle']), 'words': S('words'),
      'addon_content': S('also search this addon content folder'), 'limit': N('max (default 40)')}, ['kind', 'words'])
def t_asset_search(kind, words, addon_content=None, limit=40):
    import fgdcat, vpk
    ext = {'material': '.vmat', 'model': '.vmdl', 'sound': '.vsnd', 'particle': '.vpcf'}[kind]
    ws = words.lower().split(); hits = []
    for sub in ('csgo', 'core'):
        p = os.path.join(fgdcat.cs2_root(), 'game', sub, 'pak01_dir.vpk')
        if not os.path.exists(p): continue
        hits += [f[:-2] for f in vpk.VPK(p).files if f.endswith(ext + '_c') and all(w in f for w in ws)]
    if addon_content and os.path.isdir(addon_content):
        top = {'material': 'materials', 'model': 'models', 'sound': 'sounds', 'particle': 'particles'}[kind]
        src = {'.vsnd': ('.wav', '.mp3')}.get(ext, (ext,))
        for dp, _, fs in os.walk(os.path.join(addon_content, top)):
            for fn in fs:
                if fn.lower().endswith(src):
                    rel = os.path.relpath(os.path.join(dp, fn), addon_content).replace('\\', '/')
                    if all(w in rel.lower() for w in ws): hits.append(os.path.splitext(rel)[0] + ext + '  (addon)')
    hits = sorted(set(hits), key=lambda h: (len(h), h))
    return {'matches': len(hits), 'assets': hits[:int(limit or 40)]}


@tool('catalog_info', 'What the generators offer: building styles, light presets, HUD themes, game modes, kits and their parts, blender templates, '
      'material patterns, sound presets, effects.')
def t_catalog():
    gb, gl, mk, gg, gk, bk, mt, sk, fx = (_create(n) for n in ('gen_buildings', 'gen_light', 'mechkit', 'gen_gameplay', 'gen_kits', 'blenderkit',
                                                              'matkit', 'sndkit', 'fxkit'))
    kits = {}
    for f in sorted(os.listdir(gk.KITS)):
        if f.endswith('.json'):
            k = gk.load(f[:-5]); kits[f[:-5]] = [{'key': p['key'], 'mount': p.get('mount', 'floor'), 'tags': p.get('tags', [])} for p in k['parts']]
    return {'building_styles': sorted(gb.STYLES), 'light_presets': sorted(gl.PRESETS), 'hud_themes': sorted(mk.THEMES), 'modes': sorted(gg.MODES),
            'kits': kits, 'blender_templates': sorted(bk.TEMPLATES), 'material_patterns': list(mt.PATTERNS), 'sound_presets': list(sk.PRESETS),
            'effects': sorted(fx.EFFECTS)}


def load_plugins(folder=None):
    """autoport/*.py files that define MCP_TOOLS; returns the names added"""
    folder = folder or os.environ.get('CS2MCP_PLUGIN_DIR') or os.path.join(REPO, 'autoport')
    added = []
    if not os.path.isdir(folder): return added
    if folder not in sys.path: sys.path.append(folder)
    for p in sorted(glob.glob(os.path.join(folder, '*.py'))):
        try:
            with open(p, encoding='utf-8', errors='replace') as f:
                if 'MCP_TOOLS' not in f.read(): continue
            import importlib
            mod = importlib.import_module(os.path.splitext(os.path.basename(p))[0])
            for t in getattr(mod, 'MCP_TOOLS', []) or []:
                if t['name'] in TOOLS: log('plugin tool %s from %s clashes, skipped' % (t['name'], p)); continue
                schema = t.get('inputSchema') or {'type': 'object', 'properties': {}}
                TOOLS[t['name']] = {'name': t['name'], 'description': t.get('description', ''), 'inputSchema': schema, 'fn': t['fn'],
                                    'annotations': t.get('annotations') or {'readOnlyHint': False, 'destructiveHint': True, 'openWorldHint': True}}   # a plugin that says nothing is assumed able to change things
                added.append(t['name'])
        except Exception as ex:
            log('plugin %s not loaded: %s' % (p, ex))
    return added


# ------------------------------------------------------------------------------------------------ protocol
def _err(id_, code, msg, data=None):
    e = {'code': code, 'message': msg}
    if data is not None: e['data'] = data
    return {'jsonrpc': '2.0', 'id': id_, 'error': e}


def _ok(id_, result):
    return {'jsonrpc': '2.0', 'id': id_, 'result': result}


def call_tool(name, args):
    t = TOOLS[name]
    schema = t['inputSchema']; props = schema.get('properties', {})
    missing = [k for k in schema.get('required', []) if k not in args]
    if missing: return {'content': [{'type': 'text', 'text': 'missing argument(s): %s' % ', '.join(missing)}], 'isError': True}
    if schema.get('additionalProperties') is False:
        extra = [k for k in args if k not in props]
        if extra: return {'content': [{'type': 'text', 'text': 'unknown argument(s): %s' % ', '.join(extra)}], 'isError': True}
    try:
        buf = io.StringIO(); old = sys.stdout; sys.stdout = buf        # tools that print must not corrupt the protocol stream
        try: res = t['fn'](**args)
        finally: sys.stdout = old
        if buf.getvalue(): log('%s printed: %s' % (name, buf.getvalue()[-500:]))
        text = json.dumps(res, ensure_ascii=False, default=str)
        out = {'content': [{'type': 'text', 'text': text}], 'isError': False}
        if isinstance(res, dict): out['structuredContent'] = json.loads(text)
        return out
    except Exception as ex:
        log('tool %s failed: %s' % (name, traceback.format_exc()))
        return {'content': [{'type': 'text', 'text': '%s: %s' % (type(ex).__name__, ex)}], 'isError': True}


def handle(msg, state):
    """one JSON-RPC message -> response dict or None (notifications)"""
    if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0' or not isinstance(msg.get('method', ''), str):
        return _err(msg.get('id') if isinstance(msg, dict) else None, -32600, 'Invalid Request')
    method, id_, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
    is_note = 'id' not in msg
    if method is None: return None                                 # a response to something we never sent
    if method == 'initialize':
        want = params.get('protocolVersion')
        state['version'] = want if want in VERSIONS else VERSIONS[1]
        return _ok(id_, {'protocolVersion': state['version'], 'capabilities': {'tools': {'listChanged': False}},
                         'serverInfo': SERVER, 'instructions': INSTRUCTIONS})
    if method == 'notifications/initialized': state['ready'] = True; return None
    if method.startswith('notifications/'): return None
    if is_note: return None
    if method == 'ping': return _ok(id_, {})
    if method == 'tools/list':
        return _ok(id_, {'tools': [{k: v for k, v in t.items() if k != 'fn'} for t in TOOLS.values()]})
    if method == 'tools/call':
        name = params.get('name'); args = params.get('arguments') or {}
        if name not in TOOLS: return _err(id_, -32602, 'Unknown tool: %s' % name)
        if not isinstance(args, dict): return _err(id_, -32602, 'arguments must be an object')
        return _ok(id_, call_tool(name, args))
    return _err(id_, -32601, 'Method not found: %s' % method)


def serve(inp=None, out=None):
    inp = inp or sys.stdin.buffer; out = out or sys.stdout.buffer
    state = {'version': None, 'ready': False}
    lock = threading.Lock()
    def send(obj):
        with lock:
            out.write((json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')); out.flush()
    for raw in inp:
        line = raw.decode('utf-8', 'replace').strip()
        if not line: continue
        try:
            msg = json.loads(line)
        except ValueError:
            send(_err(None, -32700, 'Parse error')); continue
        if isinstance(msg, list):
            res = [r for r in (handle(m, state) for m in msg) if r is not None]
            if res: send(res)
            continue
        r = handle(msg, state)
        if r is not None: send(r)


def main(argv):
    added = load_plugins()
    if '--list' in argv:
        for n in TOOLS: print(n)
        return 0
    log('ready: %d tools%s' % (len(TOOLS), (' (plugins: %s)' % ', '.join(added)) if added else ''))
    serve()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
