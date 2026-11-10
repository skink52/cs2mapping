"""Adds the damage skins (MaterialGroups scorched=1, wrecked=2) to every already converted frame vmdl, then compiles them.
usage: python -I tools/damage_skins.py [--no-compile] [--only key,key]   (frames.py does the same through mdl2cs2 --damage-skins for new conversions)"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.join(os.path.dirname(os.path.dirname(PROJ)), 'create')
sys.path.insert(0, HERE); sys.path.insert(0, CREATE)
import damage_tex, frames as FR
OUT = os.path.join(PROJ, 'out', 'addon')
only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
vm = []
# textures first: every existing damage vmat gets its pngs (re)made from the current colour map (apply_vmdl skips vmdls that already
# have the groups, so without this a tuning change or a deleted png never reached frames converted earlier)
import re as _re
for sv in sorted(glob.glob(os.path.join(OUT, 'materials', 'ifr', 'frames', '*', '*_scorched.vmat'))):
    key = os.path.basename(os.path.dirname(sv))
    if only and key not in only: continue
    base = sv[:-len('_scorched.vmat')] + '.vmat'
    if not os.path.exists(base): continue
    mm = _re.search(r'TextureColor "([^"]+)"', open(base, encoding='utf-8').read())
    cp = mm and os.path.join(OUT, mm.group(1).replace('/', os.sep))
    if cp and os.path.exists(cp): damage_tex.variants(cp, force=True)
print('damage textures regenerated'); sys.stdout.flush()
for p in sorted(glob.glob(os.path.join(OUT, 'models', 'ifr', 'frames', '*', '*.vmdl'))):
    key = os.path.basename(os.path.dirname(p))
    if only and key not in only: continue
    rel = os.path.relpath(p, OUT).replace(os.sep, '/')
    n = damage_tex.apply_vmdl(OUT, rel); print('%-50s %s' % (rel, ('%d materials' % n) if n else 'unchanged')); sys.stdout.flush()
    vm.append(rel)
if '--no-compile' not in sys.argv:
    work = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work']
    dirs = sorted({os.path.dirname(v) for v in vm}) + sorted({v.replace('models/', 'materials/', 1).rsplit('/', 1)[0] for v in vm})
    res = FR.compile_models(OUT, dirs, vm, os.path.join(work, 'logs', 'rc_damage.log'))
    bad = [v for v, r in res.items() if not r[0]]
    for v, r in res.items(): print('compile %-50s %s %.1fs %s' % (v, 'OK' if r[0] else 'FAIL', r[1], '; '.join(r[2])[:120])); sys.stdout.flush()
    mp = os.path.join(OUT, '_gen', 'models.json'); data = json.load(open(mp, encoding='utf-8'))   # frames whose vmdls compiled get skins = 3
    for k, fr in data.get('frames', {}).items():
        vs = [fr.get('legs'), fr.get('upper')]
        if all((v is None) or (v in res and res[v][0]) for v in vs) and any(v in res for v in vs): fr['skins'] = 3
    json.dump(data, open(mp, 'w', encoding='utf-8'), indent=1)
    print('models.json: skins=3 on', sum(1 for f in data['frames'].values() if f.get('skins')), 'frames')
    sys.exit(1 if bad else 0)
