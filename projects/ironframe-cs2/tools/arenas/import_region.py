"""Copy everything inside a box from one .vmap into another: the Dunes hangar (skink52's 12 garage bays, built in Hammer) into a
generated arena map that has none.

usage: python -I tools/arenas/import_region.py <source.vmap> <target.vmap> x0 y0 z0 x1 y1 z1 [--into ifr_hangar] [--dry-run]

Takes every top-level node of the source whose bounds lie wholly inside the box (meshes) or whose origin is inside it (entities), plus
light probe / cubemap volumes whose box overlaps it, and deep-copies them into the target at the same place (vmapedit.import_subtree,
fresh node and reference ids). --into puts the copies in a vis group of that name (customVisGroup), so a re-run first removes
the previous import: running it again after the source changed refreshes the target. Nothing in the target outside that group is
touched; the box must be empty in the target apart from an earlier import. The source is only read (Hammer may have it open).
Default box: the Dunes hangar (x -7500 .. -2400, y -6500 .. 6500, z -14500 .. -11000), below every arena copy and clear of the
booth (0, 0, -12000) and the cache room (3072, 0, -12000).
"""
import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'tools'), os.path.join(REPO, 'create')]
import dmx
import vmapedit as V
from dmx import T_STR

VOLUMES = {'env_combined_light_probe_volume', 'env_light_probe_volume', 'env_cubemap_box', 'env_cubemap'}


def _vec(s):
    try: return [float(v) for v in str(s).split()]
    except ValueError: return None


def select(m, box):
    lo, hi = box[:3], box[3:]
    inside = lambda p: all(lo[i] <= p[i] <= hi[i] for i in range(3))
    out = []
    for n in m.children(m.world):
        t = m.type(n)
        if t == b'CMapEntity':
            o = m.origin(n)
            if inside(o): out.append(n); continue
            if m.cls(n) in VOLUMES:
                a, b = _vec(m.P(n, 'box_mins', '')), _vec(m.P(n, 'box_maxs', ''))
                if a and b and all(o[i] + a[i] <= hi[i] and o[i] + b[i] >= lo[i] for i in range(3)): out.append(n)
        else:
            b = m.bounds(n)
            if b and inside(b[0]) and inside(b[1]): out.append(n)
    return out


def set_group(m, n, name):
    for at in m.E[n]['attrs']:
        if at[0] == b'customVisGroup': at[2] = name.encode(); return
    m.E[n]['attrs'].append([b'customVisGroup', T_STR, name.encode()])


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 8: sys.exit(__doc__)
    src, dst = args[0], args[1]; box = [float(v) for v in args[2:8]]
    group = argv[argv.index('--into') + 1] if '--into' in argv else 'ifr_hangar'
    s, t = V.Map(src), V.Map(dst)
    old = [n for n in t.children(t.world) if (t.g(n, b'customVisGroup') or b'') == group.encode()]
    for n in old: t.remove_node(n)
    clash = select(t, box)
    if clash: sys.exit('the box is not empty in %s (%d nodes outside group %s): refusing to overlap them' % (dst, len(clash), group))
    nodes = select(s, box)
    memo, nid = {}, [t.next_node_id()]
    kids = dmx.geta(t.E[t.world], b'children')[2]
    for n in nodes:
        j = t.import_subtree(s, n, memo, nid); set_group(t, j, group); kids.append(j)
    for j in memo.values():
        for at in t.E[j]['attrs']:
            if at[0] == b'referenceID': at[2] = random.getrandbits(63)
    kinds = {}
    for n in nodes:
        k = s.cls(n) if s.type(n) == b'CMapEntity' else s.type(n).decode()
        kinds[k] = kinds.get(k, 0) + 1
    print('import_region: %d nodes from %s (%s); %d earlier ones replaced' % (len(nodes), os.path.basename(src),
          ', '.join('%s %d' % kv for kv in sorted(kinds.items(), key=lambda kv: -kv[1])), len(old)))
    if '--dry-run' not in argv: t.save(dst)


if __name__ == '__main__':
    main(sys.argv[1:])
