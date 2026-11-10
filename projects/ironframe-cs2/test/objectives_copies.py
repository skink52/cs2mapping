"""tools/arenas/objectives.py map_points: copy 0 is the generated arena (nearest ifr_arena_1), whatever the stacking order.
usage: python -I test/objectives_copies.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from arenas import objectives as O

class G:
    def __init__(s, ents): s.e = ents
    def entities(s, d): return s.e
    def props_of(s, c): return c['p']

def ent(tn, o): return {'p': {'classname': 'info_target', 'targetname': tn}, 'origin': o}

fails = 0
ids = [k for k in 'ABC' if k in O.FONT]
for stack, a1, want in (([0, -8664, 8664], 0, {0: 0, 1: 8664, 2: -8664}),    # Sprawl: one copy above the generated arena
                        ([0, -8664], 0, {0: 0, 1: -8664}),                    # Dunes
                        ([0, -8664], None, {0: 0, 1: -8664})):                # no ifr_arena_1: topmost is copy 0
    E = [ent('ifr_point_' + k, (i * 100.0, 0.0, z + 40.0)) for z in stack for i, k in enumerate(ids)]
    if a1 is not None: E.append(ent('ifr_arena_1', (0.0, 0.0, float(a1))))
    out, offs = O.map_points(None, G(E))
    got = {c: round(offs[c][2]) for c in offs}
    ok = got == want and all(abs(out[0][i][3] - 32) < 1 for i in range(len(ids)))
    print(('ok  ' if ok else 'FAIL'), stack, 'ifr_arena_1 z', a1, '->', got)
    fails += not ok
sys.exit(1 if fails else 0)
