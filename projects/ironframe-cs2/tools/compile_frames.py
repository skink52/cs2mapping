"""Copies every frame's models + materials folders into the scratch addon and compiles all frame vmdls (their materials and textures
compile with them), e.g. after tools/upgrade_materials.py. Check `tasklist | findstr resourcecompiler` first: one compile at a time.
usage: python -I tools/compile_frames.py [--only key,key]      prints one line per vmdl; log <work>/logs/rc_frames.log; exit 1 on a failure"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import frames as FR
OUT = os.path.join(PROJ, 'out', 'addon')
only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
vm = []
for p in sorted(glob.glob(os.path.join(OUT, 'models', 'ifr', 'frames', '*', '*.vmdl'))):
    if only and os.path.basename(os.path.dirname(p)) not in only: continue
    vm.append(os.path.relpath(p, OUT).replace(os.sep, '/'))
work = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))['paths']['work']
dirs = sorted({os.path.dirname(v) for v in vm}) + sorted({v.replace('models/', 'materials/', 1).rsplit('/', 1)[0] for v in vm})
print('%d vmdls, %d folders' % (len(vm), len(dirs)), flush=True)
res = FR.compile_models(OUT, dirs, vm, os.path.join(work, 'logs', 'rc_frames.log'))
bad = [v for v, r in res.items() if not r[0]]
for v, r in res.items(): print('compile %-50s %s %.1fs %s' % (v, 'OK' if r[0] else 'FAIL', r[1], '; '.join(r[2])[:160]), flush=True)
print('%d compiled, %d failed' % (len(res) - len(bad), len(bad)))
sys.exit(1 if bad else 0)
