"""deploy_tw.py chain stage 0b (short front, 18 Nov 2026): tools/make_map.py with the chain's --in / --out (generated assets to out/addon),
then tools/patch_uniforms.py on its output (the hidden tw_uniform_N precache props the script's SetModel needs; make_map does not make them).
usage: python tools/make_map_stage.py --in <moved user map> --out <generated map> [--addon out/addon] [--players <addon with models/tw/players>]"""
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--addon', default=os.path.join(HERE, '..', 'out', 'addon'))
ap.add_argument('--players', default=r'C:\source1\links\content_addons\mg_trenchwarfare')
a = ap.parse_args()
tmp = a.out + '.gen.vmap'
rc = subprocess.call([sys.executable, '-u', os.path.join(HERE, 'make_map.py'), a.inp, tmp, a.addon])
if rc: sys.exit(rc)
rc = subprocess.call([sys.executable, '-u', os.path.join(HERE, 'patch_uniforms.py'), tmp, a.out, a.players])
if rc: sys.exit(rc)
os.remove(tmp)
