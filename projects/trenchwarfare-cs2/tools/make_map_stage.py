"""deploy_tw.py chain stage 0b (short front, 18 Nov 2026): tools/make_map.py with the chain's --in / --out, generated assets to out/addon.
usage: python tools/make_map_stage.py --in <moved user map> --out <generated map> [--addon out/addon]"""
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--addon', default=os.path.join(HERE, '..', 'out', 'addon'))
a = ap.parse_args()
sys.exit(subprocess.call([sys.executable, '-u', os.path.join(HERE, 'make_map.py'), a.inp, a.out, a.addon]))
