"""Short front (step 5, piece 3; docs/SHORT_FRONT_DESIGN.md): move the user's own objects with their area before the map is regenerated
at 5 bays. Reads a map (the user's save), writes a copy and a report; never writes the input.

usage: python tools/move_user_objects.py <in.vmap> <out.vmap> [--report R]
  default report: <out>.moves.json

Every top-level world node that is NOT generated (vis group tw_gen) is placed in one zone by its origin (entities) or the centre of its
bounds (meshes), in the 15-bay map's coordinates, and handled by the zone's rule:
  north      y > 2700 (the woods: ladders, ladder volumes, woodsopen blockers, skirmish wire, the user's trees)   y + WOOD_DY (-1920)
  south      y < -2700 (sap mouths and galleries: the user's tl_bench bridges, undergroundopen blockers)          y + TUN_DY (+1920)
  shelter    a niche revetment beside an old dressing station (|x| 2180..2420, within 160 of its y): follows its station
             (-1056 -> -576, 576 -> 576; 2304 has no station any more: dropped)
  nml        |x| < 1350 (no man's land: the random explosions and their logic, the user's pools)          y x KY (1/3: inside the shorter strip)
  keep       |y| <= 1100 (the centre third)                                                                  unchanged
  cut        everything else (the outer two thirds of the trench band and its mortar pits)                      dropped (listed)
  outside    |x| >= 3600 or z < -1500 (aerodromes, the briefing room under the map)                                                     unchanged
Nodes without a position (nav data) are kept. The prefix's per-class entity counts follow the dropped entities.
Level: "simulated" (reads back; the generated map is checked by the gate). AI-generated (Claude) for skink52.
"""
import argparse, json, os, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
sys.path.append(HERE)
import layout as LY       # noqa: E402  (the short layout: FRONT_Y, WOOD_DY, TUN_DY)

KY = LY.FRONT_Y / 2880.0
SHELTER_MAP = {-1056.0: -576.0, 576.0: 576.0, 2304.0: None}     # old station y -> new (None: gone)


def s_(v): return v.decode('utf-8', 'replace') if isinstance(v, bytes) else (v or '')


def mesh_kids(m, i): return [c for c in m.children(i) if m.type(c) == b'CMapMesh']


def where(m, i):
    t = s_(m.type(i))
    if t == 'CMapMesh' or (t == 'CMapEntity' and mesh_kids(m, i)):     # a brush entity (nav seed, clip): where its meshes are
        b = m.bounds(i)
        if b: return (b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2, (b[0][2] + b[1][2]) / 2
    o = m.g(i, b'origin')
    return (o[0], o[1], o[2]) if o is not None else None


def zone(x, y, z):
    ax = abs(x)
    if ax >= 3600 or z < -1500: return 'outside', 0.0              # aerodromes; the briefing room under the map (z -2900)
    if 2180 <= ax <= 2420:
        for oy, ny in SHELTER_MAP.items():
            if abs(y - oy) < 160: return ('shelter', ny - oy) if ny is not None else ('cut', None)
    if y > 2700: return 'north', LY.WOOD_DY
    if y < -2700: return 'south', LY.TUN_DY
    if ax < 1350: return 'nml', y * KY - y
    if abs(y) <= 1100: return 'keep', 0.0
    return 'cut', None


def main(argv=None):
    ap = argparse.ArgumentParser(description='move user objects for the short front')
    ap.add_argument('pos', nargs='*', help='<in> <out> (or --in / --out, as deploy_tw.py --chain passes them)')
    ap.add_argument('--in', dest='inp_'); ap.add_argument('--out', dest='out_'); ap.add_argument('--report')
    a = ap.parse_args(argv)
    a.inp = a.inp_ or a.pos[0]; a.out = a.out_ or a.pos[1]
    if os.path.normcase(os.path.abspath(a.inp)) == os.path.normcase(os.path.abspath(a.out)): sys.exit('move_user_objects: out must not be the input')
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw)
    V.random.seed('move_user_objects:%08x' % (zlib.crc32(raw) & 0xffffffff))
    rep = dict(input=os.path.abspath(a.inp), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), moved=[], dropped=[], kept=0, counts={})
    drop = []
    for i in list(m.children(m.world)):
        if s_(m.g(i, b'customVisGroup')) == 'tw_gen': continue
        p = where(m, i)
        if p is None: rep['kept'] += 1; continue
        z, dy = zone(*p)
        rep['counts'][z] = rep['counts'].get(z, 0) + 1
        t = s_(m.type(i)); cls = s_(m.cls(i)) if t == 'CMapEntity' else t
        row = dict(node=i, cls=cls, name=s_(m.name(i)) if t == 'CMapEntity' else '', vg=s_(m.g(i, b'customVisGroup')), at=[round(p[0]), round(p[1])], zone=z)
        if dy is None: drop.append(i); rep['dropped'].append(row); continue
        if dy:
            for j in (mesh_kids(m, i) if t == 'CMapEntity' and mesh_kids(m, i) else [i]):   # a brush entity: its meshes move (as patch_world_1)
                o = list(m.g(j, b'origin') or [0.0, 0.0, 0.0])
                o[1] += dy
                dmx.set_(m.E[j], b'origin', dmx.T_V3, [float(v) for v in o])
            row['dy'] = round(dy, 1); rep['moved'].append(row)
        else: rep['kept'] += 1
    for i in drop: m.remove_node(i)
    counts = {}
    for e in m.entities(): counts[s_(m.cls(e))] = counts.get(s_(m.cls(e)), 0) + 1
    for attrs in m.doc.prefix:
        pre = {x[0]: x for x in attrs}
        if b'map_subasset_reference_names' in pre:
            names = sorted(counts)
            pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
            pre[b'map_subasset_reference_names'][2] = [nm.encode() for nm in names]
            pre[b'map_subasset_reference_counts'][2] = [counts[nm] for nm in names]
    m.prune()
    n = m.save(a.out)
    rp = a.report or os.path.splitext(a.out)[0] + '.moves.json'
    json.dump(rep, open(rp, 'w'), indent=1)
    print('move_user_objects: %s (%s bytes); zones %s; %d moved, %d dropped, %d unchanged -> %s'
          % (a.out, n, json.dumps(rep['counts']), len(rep['moved']), len(rep['dropped']), rep['kept'], rp))


if __name__ == '__main__':
    main()
