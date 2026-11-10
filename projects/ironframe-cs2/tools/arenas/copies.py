"""IRONFRAME: lay a generated arena out as 3 identical copies (up to 22 players each, src/cs2/15_arenas.js) on a 2 x 2 grid.

usage: python -I tools/arenas/copies.py <map.vmap> <addon content dir> [--stack 8664 | --spacing 14800] [--copies 3]

--stack Z (what Sprawl uses, like Dunes): copies 2 and 3 at z -Z and +Z above / below copy 1, which stays where it was generated;
each copy keeps its own sky shell (z -1024 .. 6144), so Z must exceed 7168. Without --stack: the 2 x 2 grid below.

A 14 000-u arena (sky shell +-7168) does not fit three times in a row inside the +-16384 world, so copy 1 moves to the
(-S/2, -S/2) quadrant and copies 2 and 3 go to +S along x and along y (S = spacing); the fourth quadrant stays empty.
Every top-level node above z -6000 (the arena: terrain, city, sky shell, lights, probes, particles, gameplay markers) is moved,
then deep-copied for copies 2..N; the pawn booth and cache room (z -12000) stay where they are. Map-wide singletons
(light_environment, env_sky, env_cubemap_fog, the master volumetric fog and post-processing, minimap boundaries) are moved
with copy 1 but never copied. ifr_arena_1..N info_targets mark the copies (the script also pairs the duplicated ifr_drop_* /
ifr_point_* names). _gen/arena.json (copy 1, INTERFACES section 2) is shifted the same way and _gen/entities.json is re-dumped.
Run it last, on a freshly generated map (vmap.py, then sprawl_ops.py): running it twice would move the arena twice.
"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'tools'), os.path.join(REPO, 'create')]
import dmx
import vmapedit as V

SINGLETONS = {'light_environment', 'env_sky', 'env_cubemap_fog', 'env_volumetric_fog_controller', 'post_processing_volume',
              'cs_minimap_boundary', 'info_map_parameters', 'point_script', 'custom_hud_layout'}
ARENA_Z = -6000.0


def offsets(spacing, n, stack=None):
    """stack: z step (Dunes' layout: copies stacked, copy 1 stays put; 0, -step, +step); else the 2 x 2 grid of `spacing`"""
    if stack:
        zs = [0.0, -stack, stack, -2 * stack][:n]
        if n > 3 and 2 * stack + 1024 > 16384: raise SystemExit('a 4th stacked copy does not fit in +-16384')
        return [(0.0, 0.0, z) for z in zs]
    h = spacing / 2
    grid = [(-h, -h), (h, -h), (-h, h), (h, h)]
    if n > 4: raise SystemExit('at most 4 copies fit on the 2 x 2 grid')
    return [(x, y, 0.0) for x, y in grid[:n]]


def shift_node(m, n, d):
    o = m.g(n, b'origin')
    if o is None: return False
    a = dmx.geta(m.E[n], b'origin'); a[2] = [o[0] + d[0], o[1] + d[1], o[2] + d[2]]
    return True


def arena_nodes(m):
    out, single = [], []
    for n in m.children(m.world):
        t = m.type(n)
        if t == b'CMapMesh':
            b = m.bounds(n)
            if b and b[1][2] > ARENA_Z: out.append(n)
        elif t == b'CMapEntity':
            if m.origin(n)[2] <= ARENA_Z: continue
            (single if m.cls(n) in SINGLETONS else out).append(n)
    return out, single


def shift_arena_json(a, d):
    sh = lambda p: [p[0] + d[0], p[1] + d[1], p[2] + d[2]] + list(p[3:])
    a['bounds']['min'] = sh(a['bounds']['min']); a['bounds']['max'] = sh(a['bounds']['max'])
    for t in a.get('drops', {}): a['drops'][t] = [sh(p) for p in a['drops'][t]]
    for p in a.get('points', []): p['pos'] = sh(p['pos'])
    for l in a.get('landmarks', []): l['pos'] = sh(l['pos'])
    if a.get('flags'): a['flags'] = {k: sh(v) for k, v in a['flags'].items()}
    a['nav']['x0'] += d[0]; a['nav']['y0'] += d[1]
    return a


def main(argv):
    if len(argv) < 3: sys.exit(__doc__)
    path, content = argv[1], argv[2]
    spacing = float(argv[argv.index('--spacing') + 1]) if '--spacing' in argv else 14800.0
    n = int(argv[argv.index('--copies') + 1]) if '--copies' in argv else 3
    stack = float(argv[argv.index('--stack') + 1]) if '--stack' in argv else None
    offs = offsets(spacing, n, stack)
    m = V.Map(path)
    if any(m.name(e).startswith('ifr_arena_') for e in m.entities()): sys.exit('this map already has ifr_arena_* copies: regenerate it first')
    nodes, single = arena_nodes(m)
    base = offs[0]
    for nd in nodes + single: shift_node(m, nd, base)
    # copies 2..n: deep copies of every arena node, moved by (copy - copy 1)
    world_children = dmx.geta(m.E[m.world], b'children')[2]
    nid = [m.next_node_id()]
    made = 0
    for k in range(1, n):
        d = tuple(offs[k][i] - base[i] for i in range(3))
        memo = {}
        for nd in nodes:
            j = m.import_subtree(m, nd, memo, nid)
            shift_node(m, j, d); world_children.append(j); made += 1
        for j in memo.values():                                      # entity reference ids must stay unique in Hammer
            for at in m.E[j]['attrs']:
                if at[0] == b'referenceID': at[2] = random.getrandbits(63)
    for k, o in enumerate(offs):
        m.new_entity('info_target', (o[0], o[1], 0.0), {'targetname': 'ifr_arena_%d' % (k + 1), 'spawnflags': '0'})
    m.save(path)
    gen = os.path.join(content, '_gen')
    ap = os.path.join(gen, 'arena.json')
    a = shift_arena_json(json.load(open(ap)), base)
    a['copies'] = [list(o) for o in offs]
    json.dump(a, open(ap, 'w'), indent=1)
    sys.path.insert(0, os.path.join(REPO, 'create'))
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(REPO, 'create', 'dump_entities.py'), path, os.path.join(gen, 'entities.json')], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[-300:])
    print('copies: %d arena nodes + %d singletons moved by (%g, %g, %g); %d nodes copied into %d more copies at %s; arena.json shifted' % (
        len(nodes), len(single), base[0], base[1], base[2], made, n - 1, ', '.join('(%g, %g, %g)' % o for o in offs[1:])))


if __name__ == '__main__':
    main(sys.argv)
