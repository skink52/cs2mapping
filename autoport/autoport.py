"""Unattended CS:GO -> CS2 ports: name the maps, come back to built addons. Maps with problems wait for Claude while the others build.

  python autoport.py                      ask for the maps (one line or several), show the plan, confirm, run
  python autoport.py <maps...> [options]  names, paths, folders, wildcards, @list.txt, bspname=addon
  python autoport.py review ...           the feedback line for Claude (python autoport.py review --help)
  python autoport.py serve                pick up where things stand: prepare, build, wait for reviews

Reuses cs2port/tools and the PC batch files unchanged. Every long step runs under watchdog.py. Nothing is pushed or committed.
Steps: prep deliver import root stage_c fixups passes profile credit audit | build report. Maps go through every step up to audit first,
then those with nothing held back build while the rest wait. Anything missing, wrong or unknown goes in logs/autoport/<date>.log.
"""
import argparse, collections, glob, json, os, re, shutil, subprocess, sys, time, traceback

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
    if os.path.isdir(os.path.join(m.content, 'models')):   # cs_mdl_import leaves bodygroup choices unnamed, which CS2 won't compile
        m.tool('vmdlfix', os.path.join(m.content, 'models'))
        n = re.findall(r'vmdlfix: (\d+) bodygroup choices named', read(m.log('vmdlfix')))
        if n and int(n[-1]): m.note('minor', 'vmdlfix.py named %s empty bodygroup choices, so those models compile now. See %s' % (n[-1], m.log('vmdlfix')))

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
    explode(m, m.out)
    if vmf_has(m, 'prop_physics_respawnable'):
        if m.tool('respawnable', m.out, m.out): m.note('error', 'respawnable.py failed, so prop_physics_respawnable props are still an unknown class: see ' + m.log('respawnable'))
        else: m.note('playtest', 'prop_physics_respawnable props are prop_physics + point_template now: break one and check it comes back after its RespawnTime.')
    if vmf_has(m, 'env_particle_glow'):
        if m.tool('glowfix', m.out, m.out, os.path.join(WORK, 'out', m.addon)): m.note('minor', 'glowfix.py failed, see ' + m.log('glowfix'))
    if vmf_has(m, 'sky_camera'): skybox(m)
    m.apply()

def explode(m, vm):
    """Model explosions cs_mdl_import drops (prop_data explosive_damage / radius) onto every prop that relied on them."""
    if m.tool('propexplode', vm, vm, os.path.join(CS2, 'csgo'), os.path.join(WORK, 'embedded', m.addon)):
        m.note('error', 'propexplode.py failed, so explosive props may not explode: see ' + m.log('propexplode')); return
    n = re.findall(r"props given their model's explosion: (\d+)", read(m.log('propexplode')))
    if n and int(n[-1]):
        m.note('minor', "%s props given their CS:GO model's explosion (cs_mdl_import drops it): see %s" % (n[-1], m.log('propexplode')))
        m.note('playtest', 'Explosive props: shoot an explosive barrel or gas can and check it explodes.')

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
    if vmf_has(m, 'move_rope') or vmf_has(m, 'keyframe_rope'): chosen.append(('', 'ropes'))   # stage C does it too; this covers maps redone from here
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
    checks(m)

MAPCHECK_KIND = {'excluded': 'unknown', 'unknown': 'unknown', 'bad_input': 'io', 'bad_output': 'io', 'dangling': 'minor', 'converted': 'review', 'baked_switch': 'playtest'}

def checks(m):
    """Hammer's Check for Problems (mapcheck.py) and z-fighting (zfight.py) on every map of the addon, fixing what has one right answer."""
    for name in m.state['maps']:
        vm = os.path.join(m.content, 'maps', name + '.vmap'); out = os.path.join(WORK, 'out', m.addon, 'maps', name + '.vmap')
        if m.tool('mapcheck', vm, out): raise StepFail('mapcheck.py failed on %s, see %s' % (name, m.log('mapcheck')))
        m.apply()
        groups = collections.defaultdict(list)
        for kind, text in (l.split('\t', 1) for l in last_run(read(m.log('mapcheck')).splitlines()) if '\t' in l):
            if kind in MAPCHECK_KIND: groups[kind].append(text)
        for kind, items in groups.items():
            what = {'excluded': 'entities of a class CS2 removes', 'unknown': 'entities of a class CS2 does not have', 'bad_input': 'outputs to an input the target lacks',
                    'bad_output': 'outputs the entity lacks', 'dangling': 'outputs to names nothing has (removed: they did nothing in CS:GO either)', 'converted': 'entities, inputs or switched lights converted to their CS2 equivalent', 'baked_switch': 'switched lights still baked'}[kind]
            m.note(MAPCHECK_KIND[kind], 'Entity check (%s): %d %s: %s' % (name, len(items), what, '; '.join(sorted(set(items))[:8])[:900]))
        if m.tool('zfight', vm, out, m.content): raise StepFail('zfight.py failed on %s, see %s' % (name, m.log('zfight')))
        m.apply()
        summary = lambda: {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', (last_run(read(m.log('zfight')).splitlines()) or [''])[-1])}
        z = summary()
        m.tool('zfight', vm, m.content)   # check again after the fix: one moved face can settle several pairs, so the fix run's own count is too high
        after = summary(); z['partial'], z['visible'] = after.get('partial', 0), after.get('visible', 0)
        part = [l.split('\t', 1)[1] for l in last_run(read(m.log('zfight')).splitlines()) if l.startswith('partial\t')]
        if z.get('hidden') or z.get('nudged'):
            m.note('minor', 'Z-fighting (%s): %d fully covered faces set to toolsnodraw, as vbsp would have dropped them; %d smaller faces moved %s units forward where two materials overlapped.' % (name, z.get('hidden', 0), z.get('nudged', 0), '0.25'))
        if z.get('nudged'): m.note('playtest', 'Z-fighting (%s): %d faces were moved 0.25 units to stop flicker; look at them in game (tools/zfight.py lists where).' % (name, z['nudged']))
        if m.tool('lightwall', vm, out, '24'): m.note('error', 'lightwall.py failed on %s, see %s' % (name, m.log('lightwall')))
        else:
            m.apply()
            lw = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', (last_run(read(m.log('lightwall')).splitlines()) or [''])[-1])}
            if lw.get('moved'): m.note('minor', 'Lights (%s): %d moved off walls they would have blown out.' % (name, lw['moved']))
            if lw.get('skipped'): m.note('playtest', 'Lights (%s): %d sit close to a wall but couldn\'t move without crossing a face: look for bright spots.' % (name, lw['skipped']))
        if not m.tool('uvflip', vm, out, 'torch'):
            m.apply()
            fl = re.findall(r'flipped=(\d+)', read(m.log('uvflip')))
            if fl and int(fl[-1]): m.note('minor', 'Upside-down torch textures flipped (%s): %s faces.' % (name, fl[-1]))
        if z.get('visible'): m.note('missing', 'Z-fighting (%s): %d overlaps between different materials still flicker after the fix (rotated meshes, or faces already moved for another overlap; first: %s). Move or cut one face of each.' % (name, z['visible'], ' | '.join(part[:4])))
        elif z.get('partial'): m.note('minor', 'Z-fighting (%s): %d small or same-material overlaps left (first: %s).' % (name, z['partial'], ' | '.join(part[:3])))

def last_run(lines):
    """A step log collects every run; the latest run is everything after the summary line before the last one."""
    ends = [i for i, l in enumerate(lines) if l.startswith('summary\t')]
    return lines[(ends[-2] + 1 if len(ends) > 1 else 0):(ends[-1] + 1 if ends else len(lines))]

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
    """build_maps.ps1 for every map of the addon. build_mode 'entities' / 'lighting' (set by "review redo <addon> build --mode ...") does skink52's
    partial Hammer builds, which start from the current .vpk: no vis, so no vis budget either."""
    done = os.path.join(PORT, 'logs', 'stage_d_done.txt'); seen = len(read(done).splitlines())
    mode = m.state.get('build_mode', 'full')
    lines = [('%s %s %s' % (mode, m.addon, n)) if mode != 'full' else '%s %s' % (m.addon, n) for n in m.state['maps']]
    extra = ['--slow-phase', 'Building map visibility', 'Visibility complete', str(m.opts.vis_budget * 60)] if budget and mode == 'full' else []
    code = m.run('build', ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(PORT, 'build_maps.ps1')] + lines, stall=1800, limit=8 * 3600, extra=extra)
    return code, [l for l in read(done).splitlines()[seen:] if m.addon in l]

def build_log(path):
    """A build log as plain lines. Partial builds run with -html, which writes HTML-escaped text joined by <br/>."""
    import html
    t = read(path)
    return html.unescape(t.replace('<br/>', '\n')) if '<br/>' in t else t

def missing(blog):
    return sorted(set(re.findall(r'Failed loading resource "([^"]+)"', build_log(blog))) - BUILD_NOISE)

def fixrefs_helped(m):
    t = read(os.path.join(PORT, 'logs', m.addon + '_fixrefs.log'))
    count = lambda label: int((re.search(label + r': (\d+)', t) or [0, 0])[1])
    return count('Models attempted') > count('Failed imports') + count('Failed model compiles') or 'material entries' in t and not re.search(r'\b0 material entries', t)

def gibs(m):
    """Before the build: every model the addon imported either has gibs that exist, or (Metal / Wooden / Glass propdata with none) gets CS:GO's
    generic chunks from gibfix.py, as CS:GO broke them. Missing gib models are imported with run_fixrefs.bat, so the build has them."""
    import vpk
    pak = vpk.VPK(os.path.join(CS2, 'game', 'csgo', 'pak01_dir.vpk'))
    vmdls = glob.glob(os.path.join(m.content, 'models', '**', '*.vmdl'), recursive=True)
    if not vmdls: return
    refs = os.path.join(m.content, 'maps', m.addon + '_fix_refs.txt'); empty = os.path.join(m.run_dir, 'no_build_log.txt'); open(empty, 'w').close()
    part = os.path.join(m.run_dir, m.addon + '_gib_refs.txt'); seen = len(read(m.log('gibfix')))
    for i in range(0, len(vmdls), 40): m.tool('gibfix', empty, part, *vmdls[i:i + 40])   # gibfix rewrites its refs file each call, so read it from the log
    glog = read(m.log('gibfix'))[seen:]
    generic = glog.count('generic gibs added to')
    have = lambda p: os.path.exists(os.path.join(m.content, p)) or os.path.exists(os.path.join(CS2, 'game', 'csgo_addons', m.addon, p + '_c')) or pak.has(p + '_c')
    wanted = {l.strip() for l in glog.splitlines() if re.match(r'models/\S+\.mdl$', l.strip())}
    wanted |= {p[:-5] + '.mdl' for v in vmdls if 'BreakPiece' in read(v) for p in re.findall(r'model = "(models/[^"]+\.vmdl)"', read(v))}
    lost = sorted(w for w in wanted if not have(w[:-4] + '.vmdl'))
    with open(refs, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('importfilelist\n{\n' + ''.join('\t"file"\t"%s"\n' % w for w in lost) + '}\n')
    if lost:
        m.run('fixrefs', ['cmd', '/c', os.path.join(PORT, 'run_fixrefs.bat'), m.addon], stall=900, limit=2 * 3600)
        still = [p for p in lost if not have(p[:-4] + '.vmdl')]
        if still: m.note('missing', 'Gib models that break-pieces need but could not be imported (first 10): %s' % ', '.join(still[:10]))
    if generic or lost: m.note('minor', 'Gib check: %d models given generic CS:GO chunks, %d missing gib models imported before the build.' % (generic, len(lost)))

def build(m):
    wait_closed(m)
    gibs(m)
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
    m.state['build_mode'] = 'full'   # a partial build is a one-off; the next one is full unless asked again

BUILD_KNOWN = r'ERROR_FILEOPEN|RESOURCE COMPILE ERROR|empty resource weak-reference|ERROR: \d+ compiled|Compile ERRORS|These errors|-noassert|Add-Content|FullyQualifiedErrorId|CategoryInfo'

def report(m):
    """Read the build's logs for what its summary doesn't say."""
    t = build_log(os.path.join(PORT, 'logs', m.addon + '_build.log')) + build_log(os.path.join(PORT, 'logs', m.addon + '_assets.log'))
    errs = sorted(set(re.findall(r'RESOURCE COMPILE ERROR: ([^\r\n]+)', t)))
    if errs: m.note('missing', '%d compile errors (first 8): %s. See logs\\%s_assets.log' % (len(errs), '; '.join(e[:100] for e in errs[:8]), m.addon))
    if 'unrecognized parent' in t: m.note('io', 'The build log says "unrecognized parent": a parented entity was dropped. See logs\\%s_build.log' % m.addon)
    if 'Failed to create physics hulls' in t: m.note('minor', 'Some meshes got no physics hull: look for missing collisions. See logs\\%s_build.log' % m.addon)
    other = sorted({l.strip()[:140] for l in t.splitlines() if re.search(r'\b(ERROR|FATAL)\b|Assertion', l) and not re.search(BUILD_KNOWN, l)})
    if other: m.note('unknown', 'Lines in the build logs no rule knows (first 5): ' + ' | '.join(other[:5]))
    if m.profile.name == 'ttt': profiles.ttt_check(m)

PREFIXES = r'^(ttt|mg|jb|ba_jail|ba|de|cs|ar|dm|gg|aim|awp|fy|surf|bhop|kz|ze|zm|hns|am)_'

def pretty(addon):
    words = re.sub(PREFIXES, '', addon).split('_')
    return ' '.join(w[:1].upper() + w[1:] for w in words if w)

def description(m):
    """A Steam Workshop description (BBCode, Steam's 8,000-character limit) in the content addon folder, as '<addon> STEAM DESCRIPTION.txt'.
    Written from what the port actually has. A copy someone has edited is never overwritten: the new one goes next to it as .new.txt."""
    import hashlib
    vmf = read(os.path.join(S1, 'maps', m.addon + '.vmf'))
    count = lambda cls: vmf.count('"classname" "%s"' % cls)
    credit = read(os.path.join(CS2, 'game', 'csgo_addons', m.addon, 'maps', m.addon + '.txt'))
    author = (re.findall(r'Original map by ([^\r\n/]+)', credit) or [''])[0].strip()
    title = ('TTT ' if m.profile.name == 'ttt' else '') + pretty(m.addon)
    who = "%s's %s" % (author, pretty(m.addon)) if author else pretty(m.addon)
    items = []
    script = read(os.path.join(m.content, 'maps', 'scripts', m.addon + '_io.js'))
    data = os.path.join(WORK, 'ttt_project', 'maps', m.addon + '.json')
    if m.profile.name == 'ttt' and os.path.exists(data):
        d = json.load(open(data))
        if d.get('buttons'): items.append('[*][b]Traitor traps:[/b] %d traitor buttons. Traitors aim at them and press E.' % len(d['buttons']))
        if d.get('checks'): items.append('[*][b]Traitor tester:[/b] the map\'s own tester works.')
    weapons = sum(n for c, n in collections.Counter(re.findall(r'"classname" "(weapon_\w+)"', vmf)).items())
    if weapons: items.append('[*][b]Weapons:[/b] %d placed around the map.' % weapons)
    if count('prop_physics_respawnable'): items.append('[*][b]Breakables come back:[/b] %d props respawn where they were a while after they break.' % count('prop_physics_respawnable'))
    if 'Score_' in script: items.append('[*][b]Finish score:[/b] reaching the end awards points, as in CS:GO.')
    if re.search(r'push', script, re.I): items.append('[*][b]Push pads[/b] work as in CS:GO.')
    if count('move_rope') or count('keyframe_rope'): items.append('[*][b]Ropes and cables[/b] rebuilt for CS2.')
    if count('func_water_analog') or 'water' in read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')).lower(): items.append('[*][b]Water[/b] you can swim in.')
    map_section = '\n[h2]The map[/h2]\n[list]\n' + '\n'.join(items) + '\n[/list]\n' if items else ''
    limits = []
    if 'env_fog_controller' in read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')): limits.append('[*]No fog: CS2 has no CS:GO fog controller.')
    if m.profile.name != 'ttt': limits.append('[*]Ported with automated tools and checked by hand; report anything that looks or plays wrong in the comments.')
    hosting = []
    if 'mp_roundtime' in read(os.path.join(m.content, 'maps', m.addon + '_cleanup_log.txt')) or 'mp_roundtime' in script:
        hosting.append('[*]The map sets [i]mp_freezetime 0[/i] and [i]mp_roundtime[/i] itself. Servers that block point_servercommand need them set by hand.')
    credits = ('Original map by %s. ' % (author or '[ORIGINAL AUTHOR]')) + 'Ported to CS2 by skink52' + ('; TTT script by skink52 with AI assistance.' if m.profile.name == 'ttt' else ' with AI-assisted tools.')
    songs = [l.strip() for l in read(os.path.join(m.content, 'sounds', 'port_music', 'credits.txt')).splitlines() if l.strip()]   # coursemusic.py
    if songs: credits += '\n\n[h2]Music[/h2]\n[list]\n' + ''.join('[*]%s\n' % s for s in songs) + '[/list]'
    tpl = read(os.path.join(HERE, 'templates', 'ttt_description.txt' if m.profile.name == 'ttt' else 'port_description.txt'))
    text = tpl.format(title=title, original_credit=who, original_credit_cap=who[:1].upper() + who[1:], map_section=map_section, known_limits=''.join(l + '\n' for l in limits),
                      hosting=''.join(h + '\n' for h in hosting), credits=credits)
    path = os.path.join(m.content, '%s STEAM DESCRIPTION.txt' % m.addon)
    md5 = hashlib.md5(text.encode()).hexdigest()
    if os.path.exists(path) and hashlib.md5(read(path).encode()).hexdigest() != m.state.get('description_md5'):
        path = path[:-4] + '.new.txt'; m.note('review', 'The Steam description was edited by hand, so the new one is next to it: ' + path)
    with open(path, 'w', encoding='utf-8', newline='\r\n') as f: f.write(text)
    if not path.endswith('.new.txt'): m.state['description_md5'] = md5
    if len(text) > 8000: m.note('review', 'Steam description is %d characters, over Steam\'s 8,000: shorten %s' % (len(text), path))
    if not author: m.note('review', 'Steam description says [ORIGINAL AUTHOR]: fill in the original mapper in %s (and the loading screen credit).' % path)
    m.note('review', 'Steam description written: %s. Check the title (%s) and add screenshots before publishing.' % (path, title))

FUNCS = {'prep': prep, 'deliver': deliver, 'import': import_, 'root': root, 'stage_c': stage_c, 'fixups': fixups, 'passes': passes, 'profile': profile, 'credit': credit, 'audit': audit, 'build': build, 'report': report, 'description': description}

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
        if c.get('mode'): m.state['build_mode'] = c['mode']
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
