"""stage_c without CS2's pak01_dir.vpk: stub CS2 VPK so sky/sounds passes can use the CS:GO source.

python3 run_c.py <addon> <root> [pass,pass...]
Default passes: merge,io,wall,equip,push,cmd,roundcfg,score,speed,gravity,dead,steam,sounds,soundscripts,overlays,sky,vis,beams,lights,radar.
Not in the default list: alpha, assets (need the CS2 VPK), and doors, overlayfix, facescale, matflags (run them later with
run_pass.py, or name them in the pass list).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vpk, stage_c
class Stub:
    files = {}
    def has(s, p): return False
_V = vpk.VPK
def fake(path):
    return Stub() if path.endswith('cs2_pak01_dir.vpk') else _V(path)
vpk.VPK = fake
addon, root = sys.argv[1], sys.argv[2]
passes = sys.argv[3].split(',') if len(sys.argv) > 3 else [p for p in ['merge','io','wall','equip','push','cmd','roundcfg','score','speed','gravity','dead','steam','sounds','soundscripts','overlays','sky','vis','beams','lights','radar'] ]
open(os.path.join(root, 'vpk', 'cs2_pak01_dir.vpk'), 'a').close()
c = stage_c.run(addon, root, passes)
for rel, data in c.files.items():
    p = os.path.join(c.out, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
for rel, data in c.game_files.items():
    p = os.path.join(root, 'out', addon + '_game', rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
print('\n'.join(['- ' + l for l in c.log] + ['TO CHECK: ' + t for t in c.todo]))
if c.need: print('NEED CS:GO archives:', sorted(c.need))
