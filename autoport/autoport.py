"""Unattended CS:GO -> CS2 port: BSP in, built addon out, no agent or human needed until the end.

  python autoport.py <bsp or folder> [...] [bspname=addon ...] [--from STEP] [--force] [--no-build] [--wait-cs2 MINUTES]

Reuses cs2port/tools and the PC batch files unchanged. Every long step runs under watchdog.py. A step that fails ends that map only; the
run moves on to the next one. Nothing is pushed or committed.

Steps: prep deliver import root stage_c fixups passes credit build report. Finished steps are skipped when a run is restarted;
--from STEP redoes that step and the ones after it (and counts the earlier ones as done).

Output: <work>/autoport_runs/<time>/cleanup_list.md (+ .json), which is what's left for an agent or a playtest, and step logs next to it.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = os.environ.get('CS2PORT', r'C:\source1\cs2port')
TOOLS = os.path.join(PORT, 'tools')
WORK = os.path.join(PORT, 'work')
S1 = r'C:\source1'
CS2 = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
sys.path[:0] = [HERE, TOOLS]
import pclocal, ports, vmapedit as V, assets

STEPS = ['prep', 'deliver', 'import', 'root', 'stage_c', 'fixups', 'passes', 'credit', 'build', 'report']
SPAWNS = ('info_player_terrorist', 'info_player_counterterrorist')
MIN_VIS_AIR = 0.1   # billion cubic units; the smallest real map logged so far has 0.9
BUILD_NOISE = {'scripts/detail_prop_types.vdata_c'}   # in every build log on the PC, working maps included

# TO CHECK text -> stage_d pass that deals with it. Anything fixed here is left off the cleanup list.
AUTO_PASSES = [(r'projection depth', 'overlaydepth'), (r'probecover adds volumes', 'probecover'), (r'game_ui', 'gameui'), (r'stage_d origindup|origindup', 'origindup')]
# TO CHECK lines only someone in the game can answer; the rest are work for an agent
PLAYTEST = r'pops in or out|flicker|compare a few rooms|feel wrong|seams after the bake|counter fed by|check they|in game'

class StepFail(Exception): pass

def read(path):
    try: raw = open(path, 'rb').read()
    except OSError: return ''
    return raw.decode('utf-16', 'replace') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')

class Map:
    def __init__(s, bsp, addon, run_dir):
        s.bsp, s.addon, s.run_dir = bsp, addon, run_dir
        s.state_path = os.path.join(WORK, 'autoport_state', addon + '.json')
        s.state = json.load(open(s.state_path)) if os.path.exists(s.state_path) else {'done': [], 'seconds': {}, 'resolved': [], 'issues': [], 'maps': [addon]}
        s.failed = None
        s.content = os.path.join(CS2, 'content', 'csgo_addons', addon)
        s.vmap = os.path.join(s.content, 'maps', addon + '.vmap')
        s.out = os.path.join(WORK, 'out', addon, 'maps', addon + '.vmap')
    def save(s):
        os.makedirs(os.path.dirname(s.state_path), exist_ok=True)
        json.dump(s.state, open(s.state_path, 'w'), indent=1)
    def issue(s, kind, text):
        if text and not any(i['text'] == text for i in s.state['issues']): s.state['issues'].append({'kind': kind, 'text': text})
    def log(s, name): return os.path.join(s.run_dir, '%s_%s.log' % (s.addon, name))
    def run(s, name, cmd, stall=600, limit=3600, extra=()):
        """A command under the watchdog. Returns its exit code; a hang or runaway goes on the cleanup list."""
        code = subprocess.call([sys.executable, os.path.join(HERE, 'watchdog.py'), '--stall', str(stall), '--max', str(limit), '--label', '%s %s' % (s.addon, name),
                                '--report', os.path.join(s.run_dir, 'watchdog.jsonl'), '--log', s.log(name)] + list(extra) + ['--'] + cmd, stdin=subprocess.DEVNULL)
        if code in (124, 125): s.issue('blocker', '%s %s and was killed by the watchdog: see %s' % (name, 'hung' if code == 124 else 'ran past its time limit', s.log(name)))
        return code
    def tool(s, name, *args, **kw): return s.run(name, [sys.executable, os.path.join(TOOLS, name + '.py')] + list(args), **kw)

# ------------------------------------------------------------------ steps
def prep(m, a):
    text = read(os.path.join(PORT, 'existing_ports.txt')); base = os.path.splitext(os.path.basename(m.bsp))[0]
    hits = ports.check(text, [base])[base][1]
    if hits and not a.force: raise StepFail('already in existing_ports.txt (use --force to port it anyway): %s' % '; '.join(l for _, l in hits))
    m.issue('agent', 'Duplicate check on the internet not done (Steam Workshop, GameBanana): do it before publishing this port.')
    out = os.path.join(WORK, 'prep')
    env = dict(os.environ, OUT=out, BSPSRC=os.path.join(HERE, 'bspsrc.bat'))
    with open(m.log('prep'), 'ab') as f:
        code = subprocess.call([sys.executable, os.path.join(TOOLS, 'prep.py'), m.bsp, '%s=%s' % (base, m.addon)], env=env, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if code: raise StepFail('prep.py exit %d, see %s' % (code, m.log('prep')))

def deliver(m, a):
    pclocal.deliver([os.path.join(WORK, 'prep', m.addon, 'manifest.json')], a.force)
    if not any(re.match(re.escape(m.addon) + r'(\s|$)', l) for l in read(os.path.join(PORT, 'existing_ports.txt')).splitlines()):
        subprocess.check_call([sys.executable, os.path.join(TOOLS, 'ports.py'), 'add', os.path.join(PORT, 'existing_ports.txt'), m.addon], stdout=subprocess.DEVNULL)

def import_(m, a):
    if os.path.exists(m.vmap + '.imported'): os.remove(m.vmap + '.imported')   # a new import replaces stage C's starting point
    queue = os.path.join(PORT, 'queue.txt'); keep = read(queue)
    done = os.path.join(PORT, 'logs', 'stage_b_done.txt'); seen = len(read(done).splitlines())
    open(queue, 'w').write(m.addon + '\n')
    try: m.run('import', ['cmd', '/c', os.path.join(PORT, 'run_import.bat')], stall=900, limit=4 * 3600)
    finally: open(queue, 'w', newline='').write(keep)
    lines = read(done).splitlines()[seen:]
    if m.addon + ' OK' not in lines or not os.path.exists(m.vmap): raise StepFail('import failed: logs\\%s_import.log' % m.addon)
    t = read(os.path.join(PORT, 'logs', m.addon + '_cleanup.log'))
    bad = re.search(r'Models failed \(import / compile\): (\d+) / (\d+)', t); nosrc = re.search(r'Textures with no source found anywhere: (\d+)', t)
    rep = os.path.join(m.content, 'maps', m.addon + '_cleanup_report.txt')
    if bad and (int(bad.group(1)) or int(bad.group(2))): m.issue('agent', 'Models failed to import/compile: %s / %s. See WHY MISSING in %s' % (bad.group(1), bad.group(2), rep))
    if nosrc and int(nosrc.group(1)): m.issue('agent', '%s textures have no source anywhere. See WHY MISSING in %s' % (nosrc.group(1), rep))
    for p in glob.glob(os.path.join(m.content, 'materials', '**', '* *'), recursive=True):
        m.issue('agent', 'Material paths have spaces (first: %s): run tools/matnames.py, then the assets pass.' % p); break

def root(m, a): pclocal.root(m.addon, WORK)

def stage_c(m, a):
    pristine = m.vmap + '.imported'
    if os.path.exists(pristine): shutil.copyfile(pristine, m.vmap)   # stage C wants the importer's vmap, even on a rerun
    else: shutil.copyfile(m.vmap, pristine)
    for tries in range(6):
        if m.tool('stage_c', m.addon, WORK, stall=600, limit=2 * 3600): raise StepFail('stage_c.py failed, see ' + m.log('stage_c'))
        need = json.load(open(os.path.join(WORK, 'out', m.addon + '_result.json'))).get('need_paths', [])
        emb = os.path.join(WORK, 'embedded', m.addon); new = [n for n in need if not os.path.exists(os.path.join(emb, n))]
        have = [n for n in new if os.path.exists(os.path.join(CS2, 'csgo', n))]
        for n in have:
            os.makedirs(os.path.dirname(os.path.join(emb, n)), exist_ok=True)
            shutil.copyfile(os.path.join(CS2, 'csgo', n), os.path.join(emb, n))
        if not have:   # nothing more to feed it
            if new: m.issue('agent', 'Stage C could not find these CS:GO files: ' + ', '.join(sorted(new)))
            return
    m.issue('agent', 'Stage C still asked for more CS:GO files after 6 runs: see ' + m.log('stage_c'))

def vmf_has(m, cls): return ('"classname" "%s"' % cls) in read(os.path.join(S1, 'maps', m.addon + '.vmf'))
def todo_lines(m): return [l[len('- TO CHECK: '):] for l in read(os.path.join(os.path.dirname(m.out), m.addon + '_cleanup_log.txt')).splitlines() if l.startswith('- TO CHECK: ')]

def fixups(m, a):
    if 'missing a needed subkey' in read(os.path.join(PORT, 'logs', m.addon + '_import.log')):
        if m.tool('disprestore', m.out, m.bsp, m.out): m.issue('agent', 'disprestore.py failed: the dropped displacements are still missing. See ' + m.log('disprestore'))
    if any('did damage in CS:GO' in t for t in todo_lines(m)):
        if m.tool('laserhurt', m.out, os.path.join(S1, 'maps', m.addon + '.vmf'), m.out): m.issue('agent', 'laserhurt.py failed, see ' + m.log('laserhurt'))
        else: m.state['resolved'].append('did damage in CS:GO')
    if vmf_has(m, 'env_particle_glow'):
        if m.tool('glowfix', m.out, m.out, os.path.join(WORK, 'out', m.addon)): m.issue('agent', 'glowfix.py failed, see ' + m.log('glowfix'))
    if vmf_has(m, 'sky_camera'):
        skybox(m)
    pclocal.apply(m.addon, WORK)

def skybox(m):
    """Split off the 3D skybox, unless the automatic box took a player spawn with it (then the box needs a person or an agent to choose it)."""
    before = len(V.Map(m.out).by_class(*SPAWNS)); keep = m.out + '.presky'; shutil.copyfile(m.out, keep)
    sky = os.path.join(os.path.dirname(m.out), m.addon + '_3dskybox.vmap'); name = m.addon
    code = m.tool('skysplit', m.out, m.out, sky, name)
    ok = code == 0 and len(V.Map(m.out).by_class(*SPAWNS)) == before
    if ok:
        m.state['maps'] = [m.addon + '_3dskybox', m.addon]; m.state['resolved'].append('CS:GO 3D skybox')
        m.issue('agent', 'Skybox split automatically: compare %s_3dskybox.vmap with the map using tools/vmap_preview.py; give skysplit.py a box if it took the wrong geometry.' % m.addon)
    else:
        shutil.copyfile(keep, m.out)
        if os.path.exists(sky): os.remove(sky)
        m.issue('agent', 'skysplit.py %s: 3D skybox left in the map. Pick a box with tools/vmap_preview.py and run skysplit.py by hand.' % ('failed' if code else 'would have moved player spawns'))
    os.remove(keep)

def passes(m, a):
    todo = read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')); chosen = []
    for pat, name in AUTO_PASSES:
        if re.search(pat, todo): chosen.append((pat, name))
    mp = V.Map(m.vmap)
    if any('water' in x.lower() for x in assets.mesh_materials(mp)) and not mp.by_class('func_water'): chosen.append(('', 'water'))
    chosen.append(('', 'visfit'))   # always last: fixups changed the geometry stage C fitted its hints to
    names = ','.join(n for _, n in chosen)
    if m.tool('stage_d', m.addon, WORK, names, stall=600, limit=2 * 3600):
        m.issue('blocker', 'stage_d.py %s failed, so vis hints may not fit the map: see %s' % (names, m.log('stage_d'))); return
    m.state['resolved'] += [p for p, _ in chosen if p]
    pclocal.apply(m.addon, WORK)
    if vis_air(m) < MIN_VIS_AIR:   # visfit found almost no play space, which is what a map open to the void looks like
        if m.tool('stage_d', m.addon, WORK, 'visfit_detail', stall=600, limit=2 * 3600): m.issue('blocker', 'stage_d.py visfit_detail failed, see ' + m.log('stage_d')); return
        pclocal.apply(m.addon, WORK)
        if vis_air(m) < MIN_VIS_AIR: m.issue('agent', 'Vis hints are still mostly Lowest (visfit_detail found %.1f billion cubic units of play space), so culling will be poor: fit hints by hand.' % vis_air(m))
        else: m.issue('playtest', 'Vis hints came from visfit_detail because plain visfit found no play space: look for pop-in.')

def vis_air(m):
    found = re.findall(r'visfit[^:]*: ([\d.]+) billion cubic units of playable air', read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')))
    return float(found[-1]) if found else 0.0

def credit(m, a):
    for name in m.state['maps']:
        if name.endswith('_3dskybox'): continue
        p = os.path.join(CS2, 'game', 'csgo_addons', m.addon, 'maps', name + '.txt')
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w').write('COMMUNITYMAPCREDITS:\nPorted to CS2 by skink52\n')
    m.issue('agent', 'Loading screen credit has no original author yet: add "Original map by <author>" to game\\csgo_addons\\%s\\maps\\%s.txt.' % (m.addon, m.addon))

def compile_(m, a, budget=False):
    done = os.path.join(PORT, 'logs', 'stage_d_done.txt'); seen = len(read(done).splitlines())
    lines = ['%s %s' % (m.addon, n) for n in m.state['maps']]
    extra = ['--slow-phase', 'Building map visibility', 'Visibility complete', str(a.vis_budget * 60)] if budget else []
    code = m.run('build', ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(PORT, 'build_maps.ps1')] + lines, stall=1800, limit=8 * 3600, extra=extra)
    return code, [l for l in read(done).splitlines()[seen:] if m.addon in l]

def missing(blog):
    return sorted(set(re.findall(r'Failed loading resource "([^"]+)"', read(blog))) - BUILD_NOISE)

def fixrefs_helped(m):
    t = read(os.path.join(PORT, 'logs', m.addon + '_fixrefs.log'))
    count = lambda label: int((re.search(label + r': (\d+)', t) or [0, 0])[1])
    return count('Models attempted') > count('Failed imports') + count('Failed model compiles') or 'material entries' in t and not re.search(r'\b0 material entries', t)

def build(m, a):
    if a.no_build: raise StepFail('--no-build: stopped before the build')
    deadline = time.time() + a.wait_cs2 * 60
    while subprocess.run(['tasklist', '/FI', 'IMAGENAME eq cs2.exe', '/NH'], capture_output=True, text=True).stdout.lower().count('cs2.exe'):
        if time.time() > deadline: raise StepFail('CS2 / Hammer stayed open for %d minutes, so the build was skipped' % a.wait_cs2)
        time.sleep(60)
    code, res = compile_(m, a, budget=True)
    if code in (124, 127):   # a stalled or slow build is nearly always the vis merge
        m.tool('stage_d', m.addon, WORK, 'visfit_lean'); pclocal.apply(m.addon, WORK)
        m.issue('playtest', 'The first build %s, so vis hints were replaced with visfit_lean and it was rebuilt: look for pop-in.' % ('hung' if code == 124 else 'spent over %g minutes in vis' % a.vis_budget))
        code, res = compile_(m, a)
    blog = os.path.join(PORT, 'logs', m.addon + '_build.log')
    refs = os.path.join(m.content, 'maps', m.addon + '_fix_refs.txt')
    if missing(blog) and not m.tool('gibfix', blog, refs) and '"file"' in read(refs):
        m.run('fixrefs', ['cmd', '/c', os.path.join(PORT, 'run_fixrefs.bat'), m.addon], stall=900, limit=2 * 3600)
        if fixrefs_helped(m): code, res = compile_(m, a)   # a full rebuild is only worth it if something new was imported
    left = missing(blog)
    if left: m.issue('agent', '%d resources failed to load in the build (first 20): %s. Build log: %s; import attempt: logs\\%s_fixrefs.log' % (len(left), ', '.join(left[:20]), blog, m.addon))
    if not res or any('FAILED' in l for l in res): raise StepFail('build failed: %s. Log: %s and logs\\%s_assets.log' % ('; '.join(res) or 'no result line', blog, m.addon))

def report(m, a):
    log = read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt'))
    dropped = re.search(r'(\d+) outputs missing with the target still there', log)
    if dropped and int(dropped.group(1)): m.issue('agent', '%s map outputs were lost: see maps\\%s_dropped_io.txt' % (dropped.group(1), m.addon))
    for line in log.splitlines():
        if not line.startswith('- TO CHECK: '): continue
        t = line[len('- TO CHECK: '):]
        if any(r and re.search(r, t) for r in m.state['resolved']): continue
        m.issue('playtest' if re.search(PLAYTEST, t) else 'agent', t)
    m.issue('agent', 'TTT game mode not applied: run projects/cs2mapTTT/tools/ttt_convert.py and build_data.py if this map should run TTT.' if m.addon.startswith('ttt_') else '')
    m.issue('agent', 'Record the port in the repo: ports/%s/ README + cleanup log + scripts, and a CHANGELOG.md line.' % m.addon)
    try: subprocess.run([sys.executable, os.path.join(TOOLS, 'vmap_preview.py'), m.vmap, os.path.join(m.run_dir, m.addon + '_preview.png')], capture_output=True, timeout=900)
    except subprocess.TimeoutExpired: pass

FUNCS = dict(prep=prep, deliver=deliver, root=root, stage_c=stage_c, fixups=fixups, passes=passes, credit=credit, build=build, report=report)
FUNCS['import'] = import_

# ------------------------------------------------------------------ run
def run_map(m, a):
    if a.from_step:
        m.state['done'] = STEPS[:STEPS.index(a.from_step)]
        if a.from_step == 'prep': m.state.update(issues=[], resolved=[], maps=[m.addon], seconds={})
    for step in STEPS:
        if step in m.state['done']: continue
        print('[%s] %s %s' % (time.strftime('%H:%M:%S'), m.addon, step), flush=True); t0 = time.time()
        try:
            FUNCS[step](m, a); m.state['done'].append(step)
        except StepFail as e:
            m.failed = '%s: %s' % (step, e)
        except Exception as e:   # one map must never stop the run
            m.failed = '%s: %s: %s' % (step, type(e).__name__, e)
        m.state['seconds'][step] = round(time.time() - t0)
        m.save()
        if m.failed:
            print('   FAILED ' + m.failed, flush=True)
            if STEPS.index(step) > STEPS.index('passes'): report(m, a)   # the stage C notes still belong on the list
            m.save(); return

PROMPT = '''Unattended port run finished. An agent should work through "Agent work" below, per the repo's CLAUDE.md and docs/porting/pipeline.md
(tools in C:\\source1\\cs2port\\tools, working root C:\\source1\\cs2port\\work; rebuild with `python C:\\source1\\cs2port\\autoport\\autoport.py <bsp> --from build`).
"Playtest" items need someone in the game. Each map's steps took the times shown.'''

def write_list(maps, run_dir):
    with open(os.path.join(run_dir, 'cleanup_list.md'), 'w', encoding='utf-8') as f:
        f.write('# Port cleanup list\n\n' + PROMPT + '\n')
        for m in maps:
            f.write('\n## %s: %s\n\nBSP: `%s`\n' % (m.addon, 'FAILED at ' + m.failed if m.failed else 'built', m.bsp))
            f.write('Time: ' + ', '.join('%s %ds' % kv for kv in m.state['seconds'].items()) + '\n')
            for kind, title in (('blocker', 'Blockers'), ('agent', 'Agent work'), ('playtest', 'Playtest')):
                items = [i['text'] for i in m.state['issues'] if i['kind'] == kind]
                if items: f.write('\n### %s\n\n' % title + ''.join('- [ ] %s\n' % x for x in items))
    json.dump([{'addon': m.addon, 'bsp': m.bsp, 'failed': m.failed, 'done': m.state['done'], 'seconds': m.state['seconds'], 'issues': m.state['issues']} for m in maps],
              open(os.path.join(run_dir, 'cleanup_list.json'), 'w'), indent=1)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inputs', nargs='+', help='BSP files, folders of BSPs, bspname=addon')
    ap.add_argument('--from', dest='from_step', choices=STEPS)
    ap.add_argument('--force', action='store_true', help='port maps already in existing_ports.txt, overwrite differing files')
    ap.add_argument('--no-build', action='store_true')
    ap.add_argument('--wait-cs2', type=float, default=30, help='minutes to wait for CS2 / Hammer to close before skipping a build')
    ap.add_argument('--vis-budget', type=float, default=20, help='minutes the vis compile may take before the build restarts with visfit_lean hints')
    a = ap.parse_args()
    names = dict(i.split('=', 1) for i in a.inputs if '=' in i); bsps = []
    for i in a.inputs:
        if '=' in i: continue
        bsps += sorted(glob.glob(os.path.join(i, '*.bsp'))) if os.path.isdir(i) else [i]
    run_dir = os.path.join(WORK, 'autoport_runs', time.strftime('%Y%m%d_%H%M%S')); os.makedirs(run_dir)
    maps = []
    for b in bsps:
        base = os.path.splitext(os.path.basename(b))[0]
        m = Map(os.path.abspath(b), names.get(base, ports.clean_name(base)), run_dir); maps.append(m)
        run_map(m, a)
        write_list(maps, run_dir)   # written after every map, so a dead PC still leaves a list
    print('Cleanup list: ' + os.path.join(run_dir, 'cleanup_list.md'))
    return 1 if any(m.failed for m in maps) else 0

if __name__ == '__main__':
    sys.exit(main())
