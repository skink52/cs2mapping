"""Patch onto the mapper's map: a master post_processing_volume (vis group ifr_pp) and hangar grime overlay quads (ifr_grime).
Re-runnable: both groups are replaced, nothing else is touched. Run tools/grime.py first (textures + vmats).
usage: python -I tools/patch_post_grime.py <the map as last saved in Hammer> <out .vmap>
Close Hammer, back up the map, run, check_mesh, copy the output over the map.

Hangar geometry (read from the mapper's meshes, z -12983 floor, two halls):
  hall A x -6083..-3133, y -4959..-416;  hall B x -6083..-3133, y 288..4831; wall tops about z -12142; bay pads top z -12952.
"""
import os, sys, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create'))); sys.path.insert(0, HERE)
import numpy as np
import vmapgen as G, vmaplib, vmesh

FLOOR = -12983.0; PADTOP = -12952.0; WALLTOP = -12150.0
HX = (-6083.0, -3133.0)
HALLS = {'A': dict(y=(-4959.0, -416.0), padx=[(-5420, -4918), (-4780, -4278), (-4119, -3617)], rows=[(-4410, -3909, 'y1'), (-2970, -2469, 'y0')]),
         'B': dict(y=(288.0, 4831.0), padx=[(-5599, -5097), (-4938, -4436), (-4298, -3796)], rows=[(2341, 2842, 'y1'), (3781, 4282, 'y0')])}
M = lambda n: 'materials/ifr/grime/ifr_grime_%s.vmat' % n
GROUP = 'ifr_grime'
rng = random.Random(5252)


def quad(c, right, up, w, h, mat):
    c = np.array(c, float); r = np.array(right, float) * w / 2; u = np.array(up, float) * h / 2
    v = [c - r - u, c + r - u, c + r + u, c - r + u]
    vmesh.TEX_SIZE[mat] = (1024, 1024)
    m = vmesh.polymesh_open(v, [[0, 1, 2, 3]], [mat], scale=1.0)
    uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]
    ev = m.get('edgeVertexIndices'); ef = m.get('edgeFaceIndices')
    for st in m.get('faceVertexData').get('streams'):
        if st.get('semanticName') == 'texcoord':
            data = st.attr('data')[2]
            for i in range(len(data)):
                if ef[i] >= 0: data[i] = (float(uvs[ev[i]][0]), float(uvs[ev[i]][1]))
    vmesh.mesh_node(m, GROUP, bake=True, shadows=False, visexclude=True, physics='none')


class Surface:
    """a plane region: placed rects (circles for floor) so nothing overlaps"""
    def __init__(self): self.placed = []
    def free(self, x, y, rad, pad=10):
        return all(math.hypot(x - px, y - py) > rad + pr + pad for px, py, pr in self.placed)
    def add(self, x, y, rad): self.placed.append((x, y, rad))


def in_rect(x, y, r, m):
    return r[0] - m < x < r[1] + m and r[2] - m < y < r[3] + m


def floor_decal(name, x, y, size, yaw, z=FLOOR + 0.5):
    a = math.radians(yaw); rt = (math.cos(a), math.sin(a), 0); up = (-math.sin(a), math.cos(a), 0)
    quad((x, y, z), rt, up, size, size, M(name))


def build():
    n = dict(floor=0, pad=0, wall=0)
    for hn, H in HALLS.items():
        y0, y1 = H['y']; fs = Surface()
        pads = []
        for (ya, yb, side) in H['rows']:
            for (xa, xb) in H['padx']: pads.append((xa, xb, ya, yb, side))
        # keep-out for floor placement: pads (+margin), taken by earlier items
        for (xa, xb, ya, yb, side) in pads:
            cx = (xa + xb) / 2
            # worn hazard stripe along the pad edge facing the aisle (axis aligned)
            ey = yb + 85 if side == 'y1' else ya - 85
            floor_decal('hazard', cx, ey, 520, 0); fs.add(cx, ey, 150); n['floor'] += 1
            # jet scorch on the pad top
            floor_decal('scorch', cx + rng.uniform(-40, 40), (ya + yb) / 2 + rng.uniform(-40, 40), rng.uniform(330, 430), rng.uniform(0, 360), z=PADTOP + 0.5); n['pad'] += 1
        def place(name, count, lo, hi, margin, region=None, tries=200):
            k = 0
            for _ in range(tries):
                if k >= count: break
                s = rng.uniform(lo, hi); rad = s * 0.38
                x = rng.uniform(HX[0] + rad + 40, HX[1] - rad - 40)
                yr = region or (y0, y1)
                y = rng.uniform(yr[0] + rad + 40, yr[1] - rad - 40) if yr[1] - yr[0] > 2 * rad + 80 else (yr[0] + yr[1]) / 2
                if any(in_rect(x, y, (p[0], p[1], p[2], p[3]), margin + rad * 0.3) for p in pads): continue
                if not fs.free(x, y, rad): continue
                fs.add(x, y, rad); floor_decal(name, x, y, s, rng.uniform(0, 360)); k += 1; n['floor'] += 1
        # oil stains hugging the pads: pick a pad, put the stain just outside its edge
        got = 0
        for _ in range(400):
            if got >= 12: break
            p = rng.choice(pads); s = rng.uniform(300, 440); rad = s * 0.38
            x = rng.uniform(p[0] - 260, p[1] + 260); y = rng.uniform(p[2] - 260, p[3] + 260)
            if in_rect(x, y, (p[0], p[1], p[2], p[3]), rad * 0.2) or any(in_rect(x, y, (q[0], q[1], q[2], q[3]), rad * 0.2) for q in pads): continue
            if not (HX[0] + rad < x < HX[1] - rad and y0 + rad < y < y1 - rad) or not fs.free(x, y, rad): continue
            fs.add(x, y, rad); floor_decal('oil_a' if got % 2 else 'oil_b', x, y, s, rng.uniform(0, 360)); got += 1; n['floor'] += 1
        place('skid', 3, 700, 950, 40)
        place('oil_b', 3, 280, 420, 40)
        place('spatter', 4, 260, 380, 40)
        place('sand', 3, 520, 760, 0, region=(y0, y0 + 520))
        place('sand', 2, 520, 760, 0, region=(y1 - 520, y1))
        # walls
        walls = [(HX[0], (1, 0, 0), 'y', (y0, y1)), (HX[1], (-1, 0, 0), 'y', (y0, y1)),
                 (y0, (0, 1, 0), 'x', HX), (y1, (0, -1, 0), 'x', HX)]
        for pos, nrm, axis, (a0, a1) in walls:
            nv = np.array(nrm, float); rt = np.cross((0, 0, 1), nv); rects = []
            long_wall = a1 - a0 > 3000
            plan = ['water'] * (5 if long_wall else 2) + ['rust'] * (3 if long_wall else 1) + ['scorch', 'spatter'] * (1 if long_wall else 0) + ['scorch'] * (0 if long_wall else 1)
            for kind in plan:
                for _ in range(60):
                    if kind == 'water': w, h = rng.uniform(220, 380), rng.uniform(520, 760); zt = WALLTOP - rng.uniform(0, 60); zc = zt - h / 2; ang = 0
                    elif kind == 'rust': w, h = rng.uniform(260, 360), rng.uniform(500, 700); zt = WALLTOP - rng.uniform(60, 280); zc = zt - h / 2; ang = 0
                    else: w = h = rng.uniform(280, 420); zc = FLOOR + rng.uniform(150, 300); ang = rng.uniform(0, 360)
                    s = rng.uniform(a0 + w / 2 + 120, a1 - w / 2 - 120)
                    rect = (s - w / 2, s + w / 2, zc - h / 2, zc + h / 2)
                    if any(not (rect[1] + 20 < q[0] or q[1] + 20 < rect[0] or rect[3] + 20 < q[2] or q[3] + 20 < rect[2]) for q in rects): continue
                    rects.append(rect)
                    c = np.array([pos + nv[0] * 0.5, s, zc]) if axis == 'y' else np.array([s, pos + nv[1] * 0.5, zc])
                    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                    rr = rt * ca + np.array((0, 0, 1)) * sa; uu = -rt * sa + np.array((0, 0, 1)) * ca
                    quad(c, rr, uu, w, h, M(kind)); n['wall'] += 1
                    break
    return n


def main(src, out):
    d = G.open_map(src, '')
    world = G.world_of(d); kids = world.attr('children')
    old = [c for c in kids[2] if c.get('customVisGroup', '') in ('ifr_pp', GROUP)]
    kids[2] = [c for c in kids[2] if c not in old]
    n = build()
    G.ent('post_processing_volume', (0, 0, 2500), group='ifr_pp', targetname='ifr_pp_master', postprocessing='postprocess/mg_ironframe_dunes.vpost',
          master='1', minexposure='0.6', maxexposure='1.8', enableexposure='1', fadetime='1.0', spawnflags='4097')
    G.finish(d, out, group=None, first_run_cleanup=False)
    print('replaced %d old nodes; added 1 post_processing_volume + grime floor %(floor)d, pad tops %(pad)d, walls %(wall)d' % (len(old), ) % n if False else
          'replaced %d old nodes; added 1 post_processing_volume + grime floor %d, pad tops %d, walls %d' % (len(old), n['floor'], n['pad'], n['wall']))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
