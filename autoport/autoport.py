"""Unattended CS:GO -> CS2 ports: name the maps, come back to built addons. Maps with problems wait for Claude while the others build.

  python autoport.py                      ask for the maps (one line or several), show the plan, confirm, run
  python autoport.py <maps...> [options]  names, paths, folders, wildcards, @list.txt, bspname=addon
  python autoport.py review ...           the feedback line for Claude (python autoport.py review --help)
  python autoport.py serve                pick up where things stand: prepare, build, wait for reviews

Reuses cs2port/tools and the PC batch files unchanged. Every long step runs under watchdog.py. Nothing is pushed or committed.
Steps: prep deliver import root stage_c fixups passes profile credit audit | build report. Maps go through every step up to audit first,
then those with nothing held back build while the rest wait. Anything missing, wrong or unknown goes in logs/autoport/<date>.log.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time, traceback

from common import *
sys.path[:0] = [HERE, TOOLS]
import pclocal, ports, vmapedit as V, assets, profiles, review, launch

SPAWNS = ('info_player_terrorist', 'info_player_counterterrorist')
MIN_VIS_AIR = 0.1   # billion cubic units; the smallest real map logged so far has 0.9
BUILD_NOISE = {'scripts/detail_prop_types.vdata_c'}   # in every build log on the PC, working maps included
# TO CHECK text -> stage_d pass that deals with it. Anything fixed here is left off the cleanup list.
AUTO_PASSES = [(r'projection depth', 'overlaydepth'), (r'probecover adds volumes', 'probecover'), (r'game_ui', 'gameui'), (r'origindup', 'origindup')]
AGENT_PROMPT = 'We\'re on autoport review. Read cs2mapping/autoport/REVIEW.md, then run: python C:\\source1\\cs2port\\autoport\\autoport.py review list, and work through the held maps.'

class StepFail(Exception): pass

class Map:
    StepFail = StepFail
    def __init__(s, addon, run_dir, bsp=None, opts=None):
        s.addon, s.run_dir, s.opts = addon, run_dir, opts
        s.state = load_state(addon) if os.path.exists(state_path(addon)) else {'done': [], 'seconds': {}, 'resolved': [], 'issues': [], 'maps': [addon], 'status': 'queued', 'failed': None, 'force': False}
        if bsp: s.state['bsp'] = bsp
        s.bsp = s.state.get('bsp', '')
        s.profile = profiles.detect(addon); s.state['profile'] = s.profile.name; s.state['run_dir'] = run_dir
        s.step = ''
        s.content = os.path.join(CS2, 'content', 'csgo_addons', addon)
        s.vmap = os.path.join(s.content, 'maps', addon + '.vmap')
        s.out = os.path.join(WORK, 'out', addon, 'maps', addon + '.vmap')
    @property
    def status(s): return s.state['status']
    def set_status(s, status):
        s.state['status'] = status; s.save()
    def save(s):
        os.makedirs(STATE, exist_ok=True)
        tmp = state_path(s.addon) + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(s.state, f, indent=1)
        os.replace(tmp, state_path(s.addon))
    def note(s, kind, text, reopen=False):
        """The one exception handler for maps: everything found about a map comes through here and lands in the dated log and the map's list."""
        if not text: return
        for i in s.state['issues']:
            if i['text'] == text:
                if reopen and i['cleared']: i['cleared'] = ''; log(kind, s.addon, s.step, 'again: ' + text)
                return
        s.state['issues'].append({'kind': kind, 'text': text, 'step': s.step, 'cleared': ''})
        log(kind, s.addon, s.step, text)
    def clear(s, note):
        for i in open_issues(s.state, HOLD_KINDS): i['cleared'] = note
        s.state['failed'] = None
    def rewind(s, step):
        """Forget a step and the ones after it, with what they found."""
        later = STEPS[STEPS.index(step):]
        s.state['done'] = [d for d in s.state['done'] if d not in later]
        s.state['issues'] = [i for i in s.state['issues'] if i['step'] not in later or i['cleared']]
        s.state['failed'] = None
        if step == 'prep': s.state.update(issues=[], resolved=[], maps=[s.addon], seconds={})
    def log(s, name): return os.path.join(s.run_dir, '%s_%s.log' % (s.addon, name))
    def run(s, name, cmd, stall=600, limit=3600, extra=()):
        """A command under the watchdog. Returns its exit code; a hang or runaway is noted, and any Python crash inside its log too."""
        path = s.log(name); seen = len(read(path))
        code = subprocess.call([sys.executable, os.path.join(HERE, 'watchdog.py'), '--stall', str(stall), '--max', str(limit), '--label', '%s %s' % (s.addon, name),
                                '--report', os.path.join(s.run_dir, 'watchdog.jsonl'), '--log', path] + list(extra) + ['--'] + cmd, stdin=subprocess.DEVNULL)
        if code in (124, 125): s.note('error', '%s %s and was killed by the watchdog: see %s' % (name, 'hung' if code == 124 else 'ran past its time limit', path))
        t = read(path)[seen:]
        if 'Traceback (most recent call last)' in t and name not in ('import', 'build'):   # Valve's importer always ends in a traceback at prefab_refs
            s.note('error', '%s crashed: %s. See %s' % (name, t.strip().splitlines()[-1][:200], path))
        return code
    def tool(s, name, *args, **kw): return s.run(name, [sys.executable, os.path.join(TOOLS, name + '.py')] + list(args), **kw)
    def apply(s):
        wait_closed(s)
        pclocal.apply(s.addon, WORK)

def cs2_running():
    return 'cs2.exe' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq cs2.exe', '/NH'], capture_output=True, text=True, errors='replace').stdout.lower()

def wait_closed(m):
    """CS2 and Hammer are both cs2.exe. Nothing edits or builds a map under them, and leaving one open costs waiting time rather than a failed map."""
    if not cs2_running(): return
    print('   CS2 / Hammer is open: waiting for it to close before touching %s...' % m.addon, flush=True)
    log('review', m.addon, m.step, 'Waiting for CS2 / Hammer to close')
    while cs2_running(): time.sleep(30)

# ------------------------------------------------------------------ preparation steps
def prep(m):
    if not os.path.isfile(m.bsp): raise StepFail('BSP not found: %s' % m.bsp)
    with open(m.bsp, 'rb') as f:
        if f.read(4) != b'VBSP': raise StepFail('Not a BSP file (bad header): %s' % m.bsp)
    if shutil.disk_usage(PORT).free < 10e9: raise StepFail('Under 10 GB free on the C drive')
    text = read(os.path.join(PORT, 'existing_ports.txt')); base = os.path.splitext(os.path.basename(m.bsp))[0]
    hits = [h for h in ports.check(text, [base])[base][1] if profiles.counts_as_duplicate(m.profile, h[1])]
    if hits and not m.state['force']: raise StepFail('Already in existing_ports.txt (--force to port it anyway): %s' % '; '.join(l for _, l in hits))
    env = dict(os.environ, OUT=os.path.join(WORK, 'prep'), BSPSRC=os.path.join(HERE, 'bspsrc.bat'))
    with open(m.log('prep'), 'ab') as f:
        code = subprocess.call([sys.executable, os.path.join(TOOLS, 'prep.py'), m.bsp, '%s=%s' % (base, m.addon)], env=env, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if code: raise StepFail('prep.py exit %d, see %s and %%TEMP%%\\autoport_bspsrc.log' % (code, m.log('prep')))

def deliver(m):
    try: pclocal.deliver([os.path.join(WORK, 'prep', m.addon, 'manifest.json')], m.state['force'])
    except SystemExit as e: raise StepFail(str(e))
    if not any(re.match(re.escape(m.addon) + r'(\s|$)', l) for l in read(os.path.join(PORT, 'existing_ports.txt')).splitlines()):
        subprocess.check_call([sys.executable, os.path.join(TOOLS, 'ports.py'), 'add', os.path.join(PORT, 'existing_ports.txt'), m.addon], stdout=subprocess.DEVNULL)

def import_(m):
    if os.path.exists(m.vmap + '.imported'): os.remove(m.vmap + '.imported')   # a new import replaces stage C's starting point
    for z in glob.glob(os.path.join(PORT, 'assets', m.addon + '.*.zip')):      # run_import.bat stops at .4.zip
        n = re.search(r'\.(\d+)\.zip$', z)
        if n and int(n.group(1)) > 4:
            subprocess.call([os.path.join(os.environ['SystemRoot'], 'System32', 'tar.exe'), '-xkf', z, '-C', os.path.join(CS2, 'csgo')], stderr=subprocess.DEVNULL)
    queue = os.path.join(PORT, 'queue.txt'); keep = read(queue)
    done = os.path.join(PORT, 'logs', 'stage_b_done.txt'); seen = len(read(done).splitlines())
    open(queue, 'w').write(m.addon + '\n')
    try: m.run('import', ['cmd', '/c', os.path.join(PORT, 'run_import.bat')], stall=900, limit=4 * 3600)
    finally: open(queue, 'w', newline='').write(keep)
    lines = read(done).splitlines()[seen:]
    if m.addon + ' OK' not in lines or not os.path.exists(m.vmap): raise StepFail('Import failed: logs\\%s_import.log' % m.addon)
    t = read(os.path.join(PORT, 'logs', m.addon + '_cleanup.log'))
    bad = re.search(r'Models failed \(import / compile\): (\d+) / (\d+)', t); nosrc = re.search(r'Textures with no source found anywhere: (\d+)', t)
    rep = os.path.join(m.content, 'maps', m.addon + '_cleanup_report.txt')
    if bad and (int(bad.group(1)) or int(bad.group(2))): m.note('missing', 'Models failed to import/compile: %s / %s. See WHY MISSING in %s' % (bad.group(1), bad.group(2), rep))
    if nosrc and int(nosrc.group(1)): m.note('missing', '%s textures have no source anywhere. See WHY MISSING in %s' % (nosrc.group(1), rep))
    imp = read(os.path.join(PORT, 'logs', m.addon + '_import.log'))
    res = re.search(r'OK: \d+ imported, (\d+) failed, \d+ skipped, (\d+) unknown', imp)
    if res and int(res.group(1)): m.note('missing', 'Importer: %s files failed. See logs\\%s_import.log' % (res.group(1), m.addon))
    if res and int(res.group(2)): m.note('unknown', 'Importer: %s files of unknown type. See logs\\%s_import.log' % (res.group(2), m.addon))
    for p in glob.glob(os.path.join(m.content, 'materials', '**', '* *'), recursive=True):
        m.note('missing', 'Material paths have spaces (first: %s): run tools/matnames.py, then the assets pass.' % p); break

def root(m): pclocal.root(m.addon, WORK)

def stage_c(m):
    wait_closed(m)
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
            if new: m.note('missing', 'Stage C could not find these CS:GO files: ' + ', '.join(sorted(new)))
            return
    m.note('missing', 'Stage C still asked for more CS:GO files after 6 runs: see ' + m.log('stage_c'))

def vmf_has(m, cls): return ('"classname" "%s"' % cls) in read(os.path.join(S1, 'maps', m.addon + '.vmf'))
def out_todos(m): return [l[len('- TO CHECK: '):] for l in read(os.path.join(os.path.dirname(m.out), m.addon + '_cleanup_log.txt')).splitlines() if l.startswith('- TO CHECK: ')]

def fixups(m):
    dropped = read(os.path.join(PORT, 'logs', m.addon + '_import.log')).count('missing a needed subkey')
    if dropped:
        if m.tool('disprestore', m.out, m.bsp, m.out): m.note('missing', 'disprestore.py failed: %d dropped displacements are still missing. See %s' % (dropped, m.log('disprestore')))
        else:
            added = re.findall(r'added (\d+) meshes', read(m.log('disprestore')))
            if added and int(added[-1]) != dropped: m.note('missing', 'The import dropped %d displacements but disprestore.py rebuilt %s.' % (dropped, added[-1]))
    if any('did damage in CS:GO' in t for t in out_todos(m)):
        if m.tool('laserhurt', m.out, os.path.join(S1, 'maps', m.addon + '.vmf'), m.out): m.note('io', 'laserhurt.py failed, so damaging lasers are only visual: see ' + m.log('laserhurt'))
        else: m.state['resolved'].append('did damage in CS:GO')
    if vmf_has(m, 'env_particle_glow'):
        if m.tool('glowfix', m.out, m.out, os.path.join(WORK, 'out', m.addon)): m.note('minor', 'glowfix.py failed, see ' + m.log('glowfix'))
    if vmf_has(m, 'sky_camera'): skybox(m)
    m.apply()

def skybox(m):
    """Split off the 3D skybox, unless the automatic box took a player spawn with it (then the box needs a person or an agent to choose it)."""
    before = len(V.Map(m.out).by_class(*SPAWNS)); keep = m.out + '.presky'; shutil.copyfile(m.out, keep)
    sky = os.path.join(os.path.dirname(m.out), m.addon + '_3dskybox.vmap'); name = m.addon
    code = m.tool('skysplit', m.out, m.out, sky, name)
    ok = code == 0 and len(V.Map(m.out).by_class(*SPAWNS)) == before
    if ok:
        m.state['maps'] = [m.addon + '_3dskybox', m.addon]; m.state['resolved'].append('CS:GO 3D skybox')
        m.note('review', 'Skybox split automatically: compare the two previews in %s; give skysplit.py a box if it took the wrong geometry.' % m.run_dir)
    else:
        shutil.copyfile(keep, m.out)
        if os.path.exists(sky): os.remove(sky)
        m.state['maps'] = [m.addon]
        m.note('missing', 'skysplit.py %s: the 3D skybox is still ordinary geometry in the map. Pick a box with tools/vmap_preview.py and run skysplit.py by hand.' % ('failed' if code else 'would have moved player spawns'))
    os.remove(keep)

def vis_air(m):
    found = re.findall(r'visfit[^:]*: ([\d.]+) billion cubic units of playable air', read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')))
    return float(found[-1]) if found else 0.0

def passes(m):
    todo = read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')); chosen = []
    for pat, name in AUTO_PASSES:
        if re.search(pat, todo): chosen.append((pat, name))
    chosen += [('', p) for p in m.profile.passes]
    mp = V.Map(m.vmap)
    if any('water' in x.lower() for x in assets.mesh_materials(mp)) and not mp.by_class('func_water'): chosen.append(('', 'water'))
    chosen.append(('', m.profile.vis))   # always last: fixups changed the geometry stage C fitted its hints to
    names = ','.join(n for _, n in chosen)
    if m.tool('stage_d', m.addon, WORK, names, stall=600, limit=2 * 3600): raise StepFail('stage_d.py %s failed, so vis hints may not fit the map: see %s' % (names, m.log('stage_d')))
    m.state['resolved'] += [p for p, _ in chosen if p]
    m.apply()
    if vis_air(m) < MIN_VIS_AIR and m.profile.vis != 'visfit_detail':   # visfit found almost no play space, which is what a map open to the void looks like
        if m.tool('stage_d', m.addon, WORK, 'visfit_detail', stall=600, limit=2 * 3600): raise StepFail('stage_d.py visfit_detail failed, see ' + m.log('stage_d'))
        m.apply()
        if vis_air(m) >= MIN_VIS_AIR: m.note('playtest', 'Vis hints came from visfit_detail because plain visfit found no play space: look for pop-in.')
    if vis_air(m) < MIN_VIS_AIR: m.note('missing', 'Vis hints are still mostly Lowest (%.1f billion cubic units of play space found), so culling will be poor: fit hints by hand.' % vis_air(m))

def profile(m):
    for extra in m.profile.extras: profiles.EXTRAS[extra](m)

def credit(m):
    for name in m.state['maps']:
        if name.endswith('_3dskybox'): continue
        p = os.path.join(CS2, 'game', 'csgo_addons', m.addon, 'maps', name + '.txt')
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w').write('COMMUNITYMAPCREDITS:\nPorted to CS2 by skink52\n')
    hints = [os.path.relpath(f, os.path.join(WORK, 'embedded', m.addon)) for f in glob.glob(os.path.join(WORK, 'embedded', m.addon, '**', '*'), recursive=True) if re.search(r'credit|readme|author', os.path.basename(f), re.I)]
    world = re.search(r'"classname" "worldspawn".*?\n\s*(?:solid|\})', read(os.path.join(S1, 'maps', m.addon + '.vmf')), re.S)
    said = [x for x in re.findall(r'"(?:comment|message|author)" "([^"]+)"', world.group(0)) if 'Decompiled by' not in x] if world else []   # BSPSource signs its own output
    m.note('review', 'Loading screen credit has no original author yet: add "Original map by <author>" to game\\csgo_addons\\%s\\maps\\%s.txt.%s' % (m.addon, m.addon, (' Leads: ' + '; '.join(said + hints)[:300]) if said or hints else ''))
    m.note('review', 'Loading screen images: add at least two (autoport does not make them; docs/porting/pipeline.md, Loading-screen background images).')

def audit(m):
    """Everything left over from the preparation steps, sorted, before anyone decides what can build."""
    cl = read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt'))
    dropped = re.findall(r'(\d+) outputs missing with the target still there', cl)
    if dropped and int(dropped[-1]): m.note('missing', '%s map outputs were lost: see maps\\%s_dropped_io.txt' % (dropped[-1], m.addon))
    for line in cl.splitlines():
        if not line.startswith('- TO CHECK: '): continue
        t = line[len('- TO CHECK: '):]
        if any(r and re.search(r, t) for r in m.state['resolved']): continue
        m.note(profiles.classify_todo(t), t)
    if m.profile.name == 'unknown': m.note('unknown', 'Unknown map type: no rule for this prefix, so it only got the standard steps. Add a row to autoport/profiles.py if it needs more.')
    entity_audit(m)
    for name in m.state['maps']:
        vm = os.path.join(m.content, 'maps', name + '.vmap')
        try: subprocess.run([sys.executable, os.path.join(TOOLS, 'vmap_preview.py'), vm, os.path.join(m.run_dir, name + '_preview.png')], capture_output=True, timeout=900)
        except subprocess.TimeoutExpired: m.note('minor', 'vmap_preview.py timed out on ' + name)
    m.note('review', 'Record the port in the repo: ports/%s/ README + cleanup log + scripts, and a CHANGELOG.md line.' % m.addon)

def entity_audit(m):
    vmf = read(os.path.join(S1, 'maps', m.addon + '.vmf'))
    had = set(re.findall(r'"classname" "([^"]+)"', vmf)); have = set()
    for name in m.state['maps']:
        vm = os.path.join(m.content, 'maps', name + '.vmap')
        if os.path.exists(vm):
            mp = V.Map(vm); have |= {mp.cls(e) for e in mp.entities()}
    gone = {c for c in had - have - profiles.KNOWN_GONE if not re.match(r'(ttt_|weapon_ttt|weapon_zm|item_)', c)}
    if gone: m.note('unknown', 'Entity classes in the CS:GO map that vanished with no known conversion: %s. Find them in the VMF and decide what they did.' % ', '.join(sorted(gone)))

# ------------------------------------------------------------------ build
def compile_(m, budget=False):
    done = os.path.join(PORT, 'logs', 'stage_d_done.txt'); seen = len(read(done).splitlines())
    lines = ['%s %s' % (m.addon, n) for n in m.state['maps']]
    extra = ['--slow-phase', 'Building map visibility', 'Visibility complete', str(m.opts.vis_budget * 60)] if budget else []
    code = m.run('build', ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(PORT, 'build_maps.ps1')] + lines, stall=1800, limit=8 * 3600, extra=extra)
    return code, [l for l in read(done).splitlines()[seen:] if m.addon in l]

def missing(blog):
    return sorted(set(re.findall(r'Failed loading resource "([^"]+)"', read(blog))) - BUILD_NOISE)

def fixrefs_helped(m):
    t = read(os.path.join(PORT, 'logs', m.addon + '_fixrefs.log'))
    count = lambda label: int((re.search(label + r': (\d+)', t) or [0, 0])[1])
    return count('Models attempted') > count('Failed imports') + count('Failed model compiles') or 'material entries' in t and not re.search(r'\b0 material entries', t)

def build(m):
    wait_closed(m)
    code, res = compile_(m, budget=True)
    if code in (124, 127):   # a stalled or slow build is nearly always the vis merge
        m.tool('stage_d', m.addon, WORK, 'visfit_lean'); m.apply()
        m.note('playtest', 'The first build %s, so vis hints were replaced with visfit_lean and it was rebuilt: look for pop-in.' % ('hung' if code == 124 else 'spent over %g minutes in vis' % m.opts.vis_budget))
        code, res = compile_(m)
    blog = os.path.join(PORT, 'logs', m.addon + '_build.log')
    refs = os.path.join(m.content, 'maps', m.addon + '_fix_refs.txt')
    if missing(blog) and not m.tool('gibfix', blog, refs) and '"file"' in read(refs):
        m.run('fixrefs', ['cmd', '/c', os.path.join(PORT, 'run_fixrefs.bat'), m.addon], stall=900, limit=2 * 3600)
        if fixrefs_helped(m): code, res = compile_(m)   # a full rebuild is only worth it if something new was imported
    left = missing(blog)
    if left: m.note('missing', '%d resources failed to load in the build (first 20): %s. Build log: %s; import attempt: logs\\%s_fixrefs.log' % (len(left), ', '.join(left[:20]), blog, m.addon))
    if not res or any('FAILED' in l for l in res): raise StepFail('Build failed: %s. Log: %s and logs\\%s_assets.log' % ('; '.join(res) or 'no result line', blog, m.addon))

BUILD_KNOWN = r'ERROR_FILEOPEN|RESOURCE COMPILE ERROR|empty resource weak-reference|ERROR: \d+ compiled|Compile ERRORS|These errors|-noassert|Add-Content|FullyQualifiedErrorId|CategoryInfo'

def report(m):
    """Read the build's logs for what its summary doesn't say."""
    t = read(os.path.join(PORT, 'logs', m.addon + '_build.log')) + read(os.path.join(PORT, 'logs', m.addon + '_assets.log'))
    errs = sorted(set(re.findall(r'RESOURCE COMPILE ERROR: ([^\r\n]+)', t)))
    if errs: m.note('missing', '%d compile errors (first 8): %s. See logs\\%s_assets.log' % (len(errs), '; '.join(e[:100] for e in errs[:8]), m.addon))
    if 'unrecognized parent' in t: m.note('io', 'The build log says "unrecognized parent": a parented entity was dropped. See logs\\%s_build.log' % m.addon)
    if 'Failed to create physics hulls' in t: m.note('minor', 'Some meshes got no physics hull: look for missing collisions. See logs\\%s_build.log' % m.addon)
    other = sorted({l.strip()[:140] for l in t.splitlines() if re.search(r'\b(ERROR|FATAL)\b|Assertion', l) and not re.search(BUILD_KNOWN, l)})
    if other: m.note('unknown', 'Lines in the build logs no rule knows (first 5): ' + ' | '.join(other[:5]))
    if m.profile.name == 'ttt': profiles.ttt_check(m)

FUNCS = {'prep': prep, 'deliver': deliver, 'import': import_, 'root': root, 'stage_c': stage_c, 'fixups': fixups, 'passes': passes, 'profile': profile, 'credit': credit, 'audit': audit, 'build': build, 'report': report}

# ------------------------------------------------------------------ the worker
def run_steps(m, steps):
    for step in steps:
        if step in m.state['done']: continue
        m.step = step
        print('[%s] %s %s' % (time.strftime('%H:%M:%S'), m.addon, step), flush=True)
        log('info', m.addon, step, 'started'); t0 = time.time()
        try:
            FUNCS[step](m); m.state['done'].append(step)
        except StepFail as e:
            m.state['failed'] = '%s: %s' % (step, e); m.note('error', 'Stopped at %s: %s' % (step, e), reopen=True)
        except Exception as e:   # one map must never stop the run
            m.state['failed'] = '%s: %s: %s' % (step, type(e).__name__, e); m.note('error', 'Stopped at %s: %s: %s' % (step, type(e).__name__, e), reopen=True)
            log('error', m.addon, step, traceback.format_exc())
        m.state['seconds'][step] = round(time.time() - t0)
        m.save()
        if m.state['failed']:
            print('   FAILED ' + m.state['failed'], flush=True); return False
    return True

def holding(m):
    kinds = [k for k in HOLD_KINDS if not (m.opts.allow_missing and k == 'missing')]
    return open_issues(m.state, kinds)

def prepare(m):
    m.set_status('preparing')
    run_steps(m, PREP_STEPS)
    m.set_status('held' if m.state['failed'] or holding(m) else 'ready')

def build_map(m):
    m.set_status('building')
    run_steps(m, BUILD_STEPS)
    m.set_status('held' if m.state['failed'] or holding(m) else 'built')

def recommend(held, ready):
    print('\n' + '=' * 78)
    print('%d map%s need Claude before building:' % (len(held), '' if len(held) == 1 else 's'))
    for m in held: print('  %-34s %s' % (m.addon, review.counts(m.state)))
    print('\nRecommended: open Claude Code in C:\\source1 and paste this (it is on your clipboard):\n  %s' % AGENT_PROMPT)
    try: subprocess.run(['clip'], input=AGENT_PROMPT.encode('ascii', 'replace'))
    except OSError: pass
    print('\nLog: %s\nList: %s' % (today_log(), CLEANUP))
    if ready: print('\nBuilding the %d good map%s now: %s' % (len(ready), '' if len(ready) == 1 else 's', ', '.join(m.addon for m in ready)))
    print('Maps build by themselves as Claude marks them ready, even if this window is closed.')
    print('=' * 78 + '\n', flush=True)

def handle(c, maps, a, run_dir):
    addon, note = c.get('addon'), c.get('note', '')
    if c['cmd'] == 'add':
        m = Map(addon, run_dir, c['bsp'], a); m.state['force'] = c.get('force', False)
        if c.get('from'): m.rewind(c['from'])
        for n in c.get('notes', []): m.note(n[0], n[1])
        m.set_status('queued'); maps[addon] = m; return
    if addon not in maps: maps[addon] = Map(addon, run_dir, None, a)
    m = maps[addon]
    print('[%s] review: %s %s: %s' % (time.strftime('%H:%M:%S'), c['cmd'], addon, note), flush=True)
    if c['cmd'] == 'ready':
        m.clear(note); m.rewind('build'); m.set_status('ready')
    elif c['cmd'] == 'accept':
        m.clear(note); m.set_status('built')
    elif c['cmd'] == 'redo':
        m.rewind(c['step']); m.set_status('queued' if c['step'] in PREP_STEPS else 'ready')   # what earlier steps found still stands
    elif c['cmd'] == 'hold':
        m.note('io', 'Held by hand: ' + note, reopen=True); m.set_status('held')
    elif c['cmd'] in ('skip', 'close'):
        m.set_status('skipped' if c['cmd'] == 'skip' else 'closed')

def read_inbox(maps, a, run_dir):
    if not os.path.isdir(INBOX): return
    for f in sorted(os.listdir(INBOX)):
        if not f.endswith('.json'): continue
        p = os.path.join(INBOX, f)
        try:
            handle(json.load(open(p, encoding='utf-8')), maps, a, run_dir)
        except Exception as e:
            log('error', None, 'inbox', '%s: %s' % (f, traceback.format_exc()))
        os.remove(p)

def write_list(maps):
    """The list for agents: every map not closed. Rewritten whenever anything changes, so a dead PC still leaves one."""
    os.makedirs(LOGS, exist_ok=True)
    with open(CLEANUP, 'w', encoding='utf-8') as f:
        f.write('# Port cleanup list\n\nUpdated %s. Held maps first need the steps in autoport/REVIEW.md. Daily log: `%s`.\n' % (time.strftime('%Y-%m-%d %H:%M'), today_log()))
        for m in maps.values():
            if m.status == 'closed': continue
            f.write('\n## %s: %s (%s)\n\nBSP: `%s`\n' % (m.addon, m.status, m.profile.label, m.bsp))
            if m.state['failed']: f.write('\nFailed at %s\n' % m.state['failed'])
            f.write('Time: ' + ', '.join('%s %ds' % kv for kv in m.state['seconds'].items()) + '\n')
            for kind, title in (('error', 'Errors (hold the build)'), ('missing', 'Missing (holds the build)'), ('unknown', 'Unknown (holds the build)'), ('io', 'I/O (holds the build)'),
                                ('minor', 'Minor, safe to build'), ('review', 'Agent work, safe to build'), ('playtest', 'Playtest')):
                items = [i['text'] for i in open_issues(m.state, (kind,))]
                if items: f.write('\n### %s\n\n' % title + ''.join('- [ ] %s\n' % x for x in items))

def serve(a):
    take_lock()
    run_dir = os.path.join(WORK, 'autoport_runs', time.strftime('%Y%m%d_%H%M%S')); os.makedirs(run_dir, exist_ok=True)
    maps = {x: Map(x, run_dir, None, a) for x in all_addons()}
    for m in maps.values():   # left unfinished by a crash or a closed window
        if m.status == 'preparing': m.set_status('queued')
        if m.status == 'building': m.set_status('ready')
    announced = set(); waiting = False
    try:
        while True:
            read_inbox(maps, a, run_dir)
            write_list(maps)
            todo = [m for m in maps.values() if m.status == 'queued']
            if todo:
                prepare(todo[0]); waiting = False; continue
            held = [m for m in maps.values() if m.status == 'held']; ready = [m for m in maps.values() if m.status == 'ready']
            new = [m for m in held if m.addon not in announced]
            if new:
                recommend(held, ready); announced |= {m.addon for m in new}
            announced &= {m.addon for m in held}
            if a.no_build: break
            if ready:
                build_map(ready[0]); waiting = False; continue
            if not held or a.no_wait: break
            if not waiting:
                print('[%s] Waiting for Claude: %s' % (time.strftime('%H:%M:%S'), ', '.join(m.addon for m in held)), flush=True); waiting = True
            time.sleep(15)
    finally:
        write_list(maps)
        try: os.remove(LOCK)
        except OSError: pass
    print('\nDone. Built: %s' % (', '.join(m.addon for m in maps.values() if m.status == 'built') or 'none'))
    left = [m.addon for m in maps.values() if m.status in ('held', 'ready')]
    if left: print('Still waiting: %s. Marking one ready with "review" starts the worker again.' % ', '.join(left))
    print('List: %s\nLog: %s' % (CLEANUP, today_log()))
    return 1 if left else 0

def main():
    for s in (sys.stdout, sys.stderr): s.reconfigure(errors='replace')
    install_excepthook()
    argv = sys.argv[1:]
    if argv[:1] == ['review']: return review.main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('maps', nargs='*', help='names, BSP paths, folders, wildcards, @list.txt, bspname=addon (or serve)')
    ap.add_argument('--from', dest='from_step', choices=STEPS, help='redo this step and the ones after it')
    ap.add_argument('--force', action='store_true', help='port maps already in existing_ports.txt, overwrite differing files')
    ap.add_argument('--no-build', action='store_true', help='stop before building; run "serve" to build later')
    ap.add_argument('--no-wait', action='store_true', help='build the good maps, then exit instead of waiting for reviews')
    ap.add_argument('--allow-missing', action='store_true', help='let maps with missing assets build; only errors, unknowns and I/O hold them back')
    ap.add_argument('--vis-budget', type=float, default=20, help='minutes vis may take before the build restarts with visfit_lean hints')
    ap.add_argument('--yes', action='store_true', help='no questions: skip the confirmation on an interactive launch')
    ap.add_argument('--dry-run', action='store_true', help='show the plan and stop')
    ap.add_argument('--no-online', action='store_true', help='skip the Steam Workshop and GameBanana search')
    a = ap.parse_args(argv)
    if a.maps == ['serve']: return serve(a)
    interactive = not a.maps
    names_in = launch.read_map_list() if interactive else a.maps
    names = dict(i.split('=', 1) for i in names_in if '=' in i and not os.path.exists(i))
    bsps, not_found = launch.resolve([i for i in names_in if i.split('=')[0] not in names], interactive)
    if not bsps:
        print('No maps found: %s' % ', '.join(not_found)); return 1
    print('Checking %d map%s...' % (len(bsps), '' if len(bsps) == 1 else 's'), flush=True)
    plans = launch.build_plan(bsps, names, not a.no_online)
    err, warn = launch.preflight(any(p.profile.name == 'ttt' for p in plans))
    for w in warn: print('Warning: ' + w); log('review', None, 'preflight', w)
    for e in err: print('CANNOT START: ' + e); log('error', None, 'preflight', e)
    if err: return 1
    if a.dry_run:
        launch.show_plan(plans, not_found); return 0
    if interactive and not a.yes:
        if not launch.confirm(plans, not_found): return 0
    else:
        launch.show_plan(plans, not_found)
    for t in not_found: log('missing', None, 'launch', 'Not found, so not ported: %s' % t)
    for p in plans:
        if not p.go: continue
        notes = [['review', 'Existing CS2 port online: ' + h] for h in p.online]
        if p.problem: notes.append(['review', 'Online duplicate search failed, so duplicates are unknown: ' + p.problem])
        started = os.path.exists(state_path(p.addon))
        if started and not a.from_step and load_state(p.addon)['status'] not in ('held',): print('%s already went through autoport (use --from STEP to redo it). Picking up where it stands.' % p.addon); continue
        post_command({'cmd': 'add', 'addon': p.addon, 'bsp': p.bsp, 'force': bool(a.force or p.force), 'from': a.from_step, 'notes': notes})
    if worker_pid():
        print('A worker is already running (pid %d): the maps were added to its queue.' % worker_pid()); return 0
    return serve(a)

if __name__ == '__main__':
    sys.exit(main())
