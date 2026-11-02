"""Polish pass for maps that are already ported: today's fixes on each map's current vmap, keeping every hand edit (no stage C rerun).

  python polish.py [--only roundcfg] <addon> [...]          (or --all-ports: every ports/<addon> that has a content vmap)

Per map, in this order, on the content vmap (backed up first as <map>.vmap.bak_polish_<time>):
  roundcfg     round setup commands: freezetime 0, roundtime 600, sv_airaccelerate 2000, mp_limitteams 0 on one-team maps, mp_solid_teammates 0
               on mg_ maps (stage_c.round_setup; only what's missing)
  fire         env_fire -> stock fire particles + burn triggers (firefx; skipped where they exist)
  respawnable  prop_physics_respawnable -> prop_physics + template respawn
  mapcheck     dangling outputs, classes CS2 removes or replaces
  zfight       covered faces hidden, partly overlapping materials separated
  propexplode  model explosions copied onto props
  lightwall    lights moved off walls they were blowing out
  uvflip       upside-down torch textures
and vmdlfix on the addon's models. --only roundcfg does just the first (the maps that only need the new commands).
Writes C:\\source1\\cs2port\\logs\\autoport\\polish_<time>.md: what each step did per map, and what is left for a person. Builds nothing.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(r'C:\source1\cs2port', 'tools')]
from common import CS2, LOGS, PORT, REPO, TOOLS, WORK
import vmapedit as V, stage_c, firefx, respawnable, mapcheck, zfight, propexplode, lightwall, uvflip

class Ctx:
    """the parts of stage C's context the passes use"""
    def __init__(s, addon):
        s.addon = addon; s.log = []; s.todo = []; s.files = {}; s.cs2v = None; s.content = os.path.join(CS2, 'content', 'csgo_addons', addon); s.root = WORK
    def write(s, rel, data): s.files[rel] = data if isinstance(data, bytes) else data.encode()

def polish(addon, only=None):
    vm = os.path.join(CS2, 'content', 'csgo_addons', addon, 'maps', addon + '.vmap')
    if not os.path.exists(vm): return {'addon': addon, 'skipped': 'no %s.vmap' % addon}
    if not V.Map(vm).entities():   # older prefab-split imports keep the entities in prefabs/<map>/<map>_gameplay.vmap (jb_yeetnam)
        g = glob.glob(os.path.join(os.path.dirname(vm), 'prefabs', '*', '*_gameplay.vmap'))
        if len(g) != 1: return {'addon': addon, 'skipped': 'no entities in %s.vmap and %d gameplay prefabs' % (addon, len(g))}
        vm = g[0]
    stamp = time.strftime('%Y%m%d_%H%M%S'); shutil.copy2(vm, vm + '.bak_polish_' + stamp)
    m = V.Map(vm); c = Ctx(addon); r = {'addon': addon, 'backup': os.path.basename(vm) + '.bak_polish_' + stamp, 'done': [], 'left': []}
    stage_c.round_setup(m, c)
    r['done'] += c.log; c.log = []
    if only != 'roundcfg':
        n0 = len(m.by_class('info_particle_system'))
        firefx.run(m, c)
        r['done'] += c.log; r['left'] += c.todo; c.log, c.todo = [], []
        r['done'].append(respawnable.run(m))
        found, removed, dropped = mapcheck.check(m, fix=True)
        r['done'].append('entity check: %d removed or converted, %d dangling outputs removed' % (removed, dropped))
        r['left'] += ['entity check: %s' % t for k, t in found if k in ('excluded', 'unknown', 'bad_input', 'bad_output')][:15]
        pairs, hidden, moved, partial = zfight.run(m, c.content, True)
        r['done'].append('z-fighting: %d covered faces hidden, %d faces moved forward' % (len(hidden), len(moved)))
        vis = [p for p in partial if zfight.visible(p)]
        if vis: r['left'].append('z-fighting: %d overlaps still flicker (rotated meshes), first at %s' % (len(vis), ' '.join(map(str, vis[0]['at']))))
        ch = propexplode.run(m, [os.path.join(WORK, 'embedded', addon), os.path.join(CS2, 'csgo')])
        r['done'].append('explosions: %d props given their model\'s' % len(ch))
        mv, sk = lightwall.run(m, 24.0)
        r['done'].append('lights: %d moved off walls (%d could not move without crossing a face)' % (len(mv), sk))
        r['done'].append('upside-down torch textures flipped: %d' % uvflip.run(m, ['torch']))
    m.save(vm)
    for rel, data in c.files.items():
        p = os.path.join(c.content, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
    if only != 'roundcfg' and os.path.isdir(os.path.join(c.content, 'models')):
        out = subprocess.run([sys.executable, os.path.join(TOOLS, 'vmdlfix.py'), os.path.join(c.content, 'models')], capture_output=True, text=True).stdout
        n = re.findall(r'(\d+) bodygroup choices named', out)
        if n and int(n[-1]): r['done'].append('models: %s empty bodygroup choices named' % n[-1])
    # map-spawn server commands the port turned into script commands (Cmd_<n>) would undo the 2000; the repo copy in ports/<addon>/scripts too
    for f in glob.glob(os.path.join(c.content, 'maps', 'scripts', '*.js')) + glob.glob(os.path.join(REPO, 'ports', addon, 'scripts', '*.js')):
        s = open(f, encoding='utf-8', newline='').read(); old = sorted(set(re.findall(r'sv_airaccelerate\s+(?!2000\b)\d+', s)))
        if not old: continue
        shutil.copy2(f, f + '.bak_polish_' + stamp) if not f.startswith(REPO) else None
        open(f, 'w', encoding='utf-8', newline='').write(re.sub(r'sv_airaccelerate\s+(?!2000\b)\d+', 'sv_airaccelerate 2000', s))
        r['done'].append('script %s: %s -> sv_airaccelerate 2000' % (os.path.relpath(f, REPO) if f.startswith(REPO) else os.path.basename(f), ', '.join(old)))
    return r

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('addons', nargs='*'); ap.add_argument('--only', choices=['roundcfg']); ap.add_argument('--all-ports', action='store_true')
    a = ap.parse_args()
    names = a.addons or (sorted(os.path.basename(p) for p in glob.glob(os.path.join(REPO, 'ports', '*')) if os.path.isdir(p)) if a.all_ports else [])
    if not names: ap.error('which maps?')
    rows = []
    for n in names:
        t0 = time.time()
        try: r = polish(n, a.only)
        except Exception as e: r = {'addon': n, 'error': '%s: %s' % (type(e).__name__, e)}
        r['seconds'] = round(time.time() - t0); rows.append(r)
        print('%-30s %s' % (n, r.get('error') or r.get('skipped') or '%d done, %d left (%ds)' % (len(r['done']), len(r['left']), r['seconds'])), flush=True)
    os.makedirs(LOGS, exist_ok=True)
    path = os.path.join(LOGS, 'polish_%s.md' % time.strftime('%Y%m%d_%H%M%S'))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# Polish pass %s\n\nMaps changed in place, each backed up first. Nothing is built yet.\n' % time.strftime('%Y-%m-%d %H:%M'))
        for r in rows:
            f.write('\n## %s\n\n' % r['addon'])
            if r.get('error') or r.get('skipped'): f.write('**%s**\n' % (r.get('error') or r.get('skipped'))); continue
            f.write('Backup: `%s`\n\n' % r['backup'] + ''.join('- %s\n' % d for d in r['done'] if d))
            if r['left']: f.write('\nFor a person:\n\n' + ''.join('- [ ] %s\n' % x for x in r['left']))
    json.dump(rows, open(path[:-3] + '.json', 'w'), indent=1)
    print('Report: ' + path)

if __name__ == '__main__':
    main()
