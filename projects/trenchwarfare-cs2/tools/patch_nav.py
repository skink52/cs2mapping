"""Nav patch (remaster step 4): NONAV markup over the ground no player can reach from the play areas, as a guarded delta patch.
Reads the input map (never writes it); writes the patched copy, the guard's target list and a report under out/.

usage: python tools/patch_nav.py --in <map.vmap> [--out out/nav_patched.vmap] [--targets out/nav_patch.targets.json]
                                 [--report out/nav_report.json] [--estimate] [--cell 256] [--margin 96] [--stage DIR]
  --in        a COPY of the user's vmap in out/ (cp content\\...\\maps\\mg_trenchwarfare.vmap out/nav_input_user.vmap), or the output of
              tools/patch_world_1.py (it moves the woods seeds inside the fence): this patch is independent of it and runs after it
  --out       must be under out/ and not the input
  --estimate  also rebuild the scene of the output and print the nav estimate before -> after (create/check_play.py's flood, see below)
  then:       python tools/patch_guard.py <in> <out> out/nav_patch.targets.json

What it adds. Everything comes from the input map's own walk graph (the neutral create/check_play.py through the trench adapter
tools/check_play.py: 16-u grid, step 18 u, drops, ladder volumes, the blockers removed = the "open" state):
  in play   every node a play world walks to once the areas are open: both trench systems (posts + dressing stations), the ten mortar
            pits, the briefing room, the woods clearing and the mine galleries. Plus a margin (--margin, xy) around each, every
            WALKABLESEED box and every post / station (check_play's nav_protect points).
  NONAV     func_nav_markup (navProperty_NavGen NONAV, a closed toolsnavattribute box child; the same entity monsoon's
            mv_entities.nav_markup() makes) over every --cell square that has walkable ground but none of it in play: no man's land
            beyond the wire (not walkable for either side: check_play T5), the forest outside the clearing fence, the airfields, the
            terrain to the bounds. A square whose in-play ground lies more than 160 u below its other ground (the briefing room under
            the map, the galleries under no man's land) gets a box that starts 100 u over the in-play ground; a square with in-play
            ground at the same level is left alone. Squares are merged into rectangles (at most 8 x 8) with one z range.
  Copies of the first WALKABLESEED markup of vis group tw_nav (entity + mesh, new node ids), named tw_nav_no_N, vis group tw_nav.
  A re-run replaces the tw_nav_no_N of the input (declared removals).
Nothing else is touched; tools/patch_guard.py checks that.

The estimate (simulated, not a nav build): create/check_play.py check 9 floods the open walk graph from the WALKABLESEED boxes.
Here the nodes inside NONAV boxes are taken out of the graph first (nav generation makes no area there and cannot cross it), and
the flood starts from the seeds and the spawns. Cells -> nav areas uses the one measured pair: the tw34 compile of the user's map
(29 Oct, = the current vmap) reported 44160 nav areas; its flood here is the denominator. Areas are merged rectangles of very
different sizes, so the area count is an estimate within a factor of about 2; the cell count is the solid number.
Ladders: reported (bottom / top walkable nodes, gap to the floor), never changed: the woods ladders are the user's (REVIEW_WORLD_1 M4).
"""
import argparse, json, math, os, sys, time, zlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402
import importlib.util     # noqa: E402
_spec = importlib.util.spec_from_file_location('tw_check_play', os.path.join(HERE, 'check_play.py'))   # the trench adapter (read only here)
TCP = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(TCP)
CP = TCP.CP                                                                                           # create/check_play.py

GROUP = 'tw_nav'
PREFIX = 'tw_nav_no_'
TW34_AREAS = 44160            # nav areas the tw34 compile reported (NOTES tw34, 29 Oct) for the map that is the user's vmap today
CTX_STATE = 'open'


class Mismatch(Exception): pass


# ---------------------------------------------------------------- the walk graph of a map
def scene(path):
    """(ctx, A) for a map: scene, grid and the play worlds' start nodes, as create/check_play.run builds them"""
    A = TCP.Trench()
    A.out_json = None
    CP.setup_grid(A.extent, A.cell)
    sc = CP.load_scene(path, A)
    G = CP.Grid(sc)
    ctx = CP.Ctx(path, A, sc, G, False)
    for w, pts in A.worlds(ctx).items():
        ctx.home[w] = sorted(set(sum((ctx.nodes(p[1], p[2], p[3], state=CTX_STATE) for p in pts), [])))
    return ctx, A


def walkable(ctx):
    G = ctx.G
    return np.isfinite(G.Z).ravel() & ~G.blocked.ravel()


def node_arrays(ctx):
    """x, y, z of every node id (K * NC), NaN where there is no surface"""
    G = ctx.G
    c = np.arange(CP.NC)
    xs = CP.X0 + (c // CP.NY + 0.5) * CP.CELL
    ys = CP.Y0 + (c % CP.NY + 0.5) * CP.CELL
    return np.tile(xs, G.K), np.tile(ys, G.K), G.Z.ravel().astype(float)


def in_play(ctx):
    m = np.zeros(ctx.G.K * CP.NC, bool)
    per = {}
    for w in ctx.home:
        r = ctx.reach_of(w, CTX_STATE)
        per[w] = int(r.sum()); m |= r
    return m, per


def nonav_mask(ctx, X, Y, Z, boxes=None):
    if boxes is None: boxes = [b for (p, n, b) in ctx.sc['navboxes'] if p == 'NONAV']
    out = np.zeros(len(Z), bool)
    for (x0, y0, z0, x1, y1, z1) in boxes:
        out |= (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z >= z0) & (Z <= z1)
    return out


def estimate(ctx):
    """cells the seeds (+ spawns) flood in the open walk graph with the NONAV nodes taken out (check 9's flood when there is no NONAV)"""
    from scipy import sparse
    X, Y, Z = node_arrays(ctx)
    no = nonav_mask(ctx, X, Y, Z)
    g = ctx.graph(CTX_STATE)
    if no.any():
        D = sparse.diags((~no).astype(np.int8)); g = (D @ g @ D).tocsr(); g.eliminate_zeros()
    seeds = []
    for prop, name, b in ctx.sc['navboxes']:
        if prop == 'WALKABLESEED': seeds += [n for n in ctx.G.nodes_near((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2] - 2.0, 30.0, 24.0) if not no[n]]
    for e in ctx.ents:
        if e['cls'] in ('info_player_terrorist', 'info_player_counterterrorist'):
            seeds += [n for n in ctx.G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - 8, 24.0, 24.0) if not no[n]]
    fl = CP.reach(g, sorted(set(seeds))) if seeds else np.zeros(len(Z), bool)
    nseed = sum(1 for p, n, b in ctx.sc['navboxes'] if p == 'WALKABLESEED')
    return dict(flood_cells=int(fl.sum()), nonav_boxes=sum(1 for p, n, b in ctx.sc['navboxes'] if p == 'NONAV'), nonav_nodes=int(no.sum()),
                seeds=nseed, walkable_nodes=int(walkable(ctx).sum()))


def ladders(ctx):
    out = []
    G = ctx.G
    for L_, ids in zip(ctx.sc['ladders'], G.ladder_nodes if hasattr(G, 'ladder_nodes') else [[]] * len(ctx.sc['ladders'])):
        bx = L_['box']; zs = [CP.node_xyz(G, n)[2] for n in ids]
        bot = [z for z in zs if z <= bx[2] + 24]; top = [z for z in zs if z >= bx[5] - 40]
        out.append(dict(box=[round(v) for v in bx], vg=L_['vg'] or 'ungrouped', bottom_nodes=len(bot), top_nodes=len(top),
                        gap_bottom=round(bx[2] - max(bot), 1) if bot else None))
    return out


# ---------------------------------------------------------------- where the NONAV boxes go
def plan_boxes(ctx, cell, margin):
    X, Y, Z = node_arrays(ctx)
    walk = walkable(ctx) & np.isfinite(Z)
    play, per = in_play(ctx)
    A = ctx.A
    keep = [(x, y, z) for (n, x, y, z) in A.nav_protect(ctx)]
    keep += [((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2]) for (p, n, b) in ctx.sc['navboxes'] if p == 'WALKABLESEED']
    x0e, y0e, x1e, y1e = A.extent
    nx, ny = int(math.ceil((x1e - x0e) / cell)), int(math.ceil((y1e - y0e) / cell))
    ci = np.floor((X - x0e) / cell).astype(int); cj = np.floor((Y - y0e) / cell).astype(int)
    ok = walk & (ci >= 0) & (ci < nx) & (cj >= 0) & (cj < ny)
    # in-play z per square, the margin applied in xy: each in-play node marks the squares within `margin` of it
    pz = {}
    ip = np.nonzero(ok & play)[0]
    for dx in (-margin, 0, margin):
        for dy in (-margin, 0, margin):
            a = np.floor((X[ip] + dx - x0e) / cell).astype(int); b = np.floor((Y[ip] + dy - y0e) / cell).astype(int)
            for i, j, z in zip(a, b, Z[ip]):
                if 0 <= i < nx and 0 <= j < ny:
                    k = (i, j); lo, hi = pz.get(k, (1e9, -1e9)); pz[k] = (min(lo, z), max(hi, z))
    for (x, y, z) in keep:
        for dx in (-margin, 0, margin):
            for dy in (-margin, 0, margin):
                i, j = int((x + dx - x0e) // cell), int((y + dy - y0e) // cell)
                if 0 <= i < nx and 0 <= j < ny: lo, hi = pz.get((i, j), (1e9, -1e9)); pz[(i, j)] = (min(lo, z), max(hi, z))
    # out-of-play ground per square
    oz = {}
    op = np.nonzero(ok & ~play)[0]
    order = np.lexsort((Z[op], cj[op], ci[op]))
    for n in op[order]:
        k = (ci[n], cj[n]); lo, hi = oz.get(k, (1e9, -1e9)); oz[k] = (min(lo, Z[n]), max(hi, Z[n]))
    cells = {}
    skipped = 0
    for k, (olo, ohi) in oz.items():
        req = -1e9
        if k in pz:
            plo, phi = pz[k]
            if phi < olo - 160: req = phi + 100.0                  # in-play ground well below (briefing room, galleries): box starts above it
            else: skipped += 1; continue                           # in-play ground at this level: nav stays
        cells[k] = (olo, ohi, req)
    # merge into rectangles: one z range per box, every square's ground inside it, never down to an in-play floor below
    done = set(); boxes = []
    def fits(ks):
        lo = min(cells[k][0] for k in ks); hi = max(cells[k][1] for k in ks); req = max(cells[k][2] for k in ks)
        z0 = max(lo - 48.0, req)
        return (z0 <= min(cells[k][0] for k in ks) - 8.0), z0, hi + 200.0
    for i in range(nx):
        for j in range(ny):
            k = (i, j)
            if k not in cells or k in done: continue
            j1 = j
            while j1 + 1 < ny and (i, j1 + 1) in cells and (i, j1 + 1) not in done and j1 + 1 - j < 8 and fits([(i, q) for q in range(j, j1 + 2)])[0]: j1 += 1
            i1 = i
            while i1 + 1 < nx and i1 + 1 - i < 8:
                col = [(i1 + 1, q) for q in range(j, j1 + 1)]
                if not all(c in cells and c not in done for c in col): break
                if not fits([(a, q) for a in range(i, i1 + 2) for q in range(j, j1 + 1)])[0]: break
                i1 += 1
            ks = [(a, q) for a in range(i, i1 + 1) for q in range(j, j1 + 1)]
            okf, z0, z1 = fits(ks)
            if not okf: z0 = max(cells[k][0] - 48.0, cells[k][2]); ks = [k]; i1, j1 = i, j; z1 = cells[k][1] + 200.0
            done.update(ks)
            boxes.append((x0e + i * cell, y0e + j * cell, round(z0, 1), x0e + (i1 + 1) * cell, y0e + (j1 + 1) * cell, round(z1, 1)))
    info = dict(in_play_nodes=int(play.sum()), worlds=per, squares_with_ground=len(oz), squares_cut=len(cells), squares_kept_level=skipped,
                walkable_nodes=int(walk.sum()))
    # safety: no box over a protected point or a seed (re-checked here, whatever the merge did)
    bad = [(x, y, z) for (x, y, z) in keep for b in boxes if b[0] < x < b[3] and b[1] < y < b[4] and b[2] - 36 < z < b[5]]
    if bad: raise Mismatch('a NONAV box covers a protected point / seed: %s' % bad[:3])
    Xp, Yp, Zp = X[ip], Y[ip], Z[ip]
    cover = nonav_mask(ctx, Xp, Yp, Zp, boxes)
    info['in_play_nodes_covered'] = int(cover.sum())
    if cover.any(): raise Mismatch('%d in-play nodes inside the planned NONAV boxes' % int(cover.sum()))
    return boxes, info


# ---------------------------------------------------------------- the map edit
def template(m):
    """the first WALKABLESEED func_nav_markup of vis group tw_nav with one 8-vertex box mesh at origin 0 (patch_bots.py made them)"""
    for e in m.by_class('func_nav_markup'):
        vg = (m.g(e, b'customVisGroup') or b'').decode()
        if vg != GROUP or m.P(e, 'navProperty_NavGen') != 'WALKABLESEED': continue
        ch = m.children(e)
        if len(ch) != 1 or m.type(ch[0]) != b'CMapMesh' or list(m.g(ch[0], b'origin')) != [0.0, 0.0, 0.0]: continue
        if len(m.mesh_points(ch[0])) != 8: continue
        return e, ch[0]
    raise Mismatch('no WALKABLESEED func_nav_markup of vis group %s with one 8-vertex mesh to copy' % GROUP)


def add_box(m, tmpl, box, name, node_id):
    e0, mesh0 = tmpl
    memo = {}
    e = m.import_subtree(m, e0, memo, node_id)
    mesh = memo[mesh0]
    dmx.set_(m.E[e], b'referenceID', dmx.T_U64, int.from_bytes(os.urandom(8), 'little') >> 1)
    dmx.set_(m.E[mesh], b'referenceID', dmx.T_U64, int.from_bytes(os.urandom(8), 'little') >> 1)
    m.setp(e, 'navProperty_NavGen', 'NONAV'); m.setp(e, 'targetname', name)
    lo, hi = m.bounds(mesh0)
    md = m.g(mesh, b'meshData'); vd = m.g(md, b'vertexData')
    for st in m.g(vd, b'streams'):
        if not m.E[st]['name'].startswith(b'position'): continue
        a = dmx.geta(m.E[st], b'data')
        new = []
        for p in a[2]:
            q = []
            for k in range(3):
                mid = (lo[k] + hi[k]) / 2
                q.append(float(box[k + 3] if p[k] > mid else box[k]))
            new.append(q)
        a[2] = new
    dmx.geta(m.E[m.world], b'children')[2].append(e)
    return e, mesh


def main(argv=None):
    ap = argparse.ArgumentParser(description='nav patch (step 4): NONAV markup')
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--out', default=os.path.join(OUT, 'nav_patched.vmap'))
    ap.add_argument('--targets', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--estimate', action='store_true')
    ap.add_argument('--cell', type=float, default=256.0)
    ap.add_argument('--margin', type=float, default=96.0)
    a = ap.parse_args(argv)
    inp, outp = os.path.abspath(a.inp), os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(inp):
        sys.exit('patch_nav: --out must be under %s and not the input' % OUT)
    if 'csgo_addons' in os.path.normcase(inp).replace('\\', '/'):
        print('patch_nav: reading the map in the addon (read only); a copy in out/ is the rule')
    tp = a.targets or os.path.splitext(outp)[0] + '.targets.json'
    rp = a.report or os.path.splitext(outp)[0] + '.report.json'
    t0 = time.time()
    raw = open(inp, 'rb').read()
    m = V.Map(inp, data=raw)
    T = dict(input=inp, input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=['map_subasset_reference_types', 'map_subasset_reference_names', 'map_subasset_reference_counts'], root=False)
    try:
        tmpl = template(m)
        old = [e for e in m.by_class('func_nav_markup') if m.name(e).startswith(PREFIX)]
        print('patch_nav: building the walk graph of the input (create/check_play.py, ~40 s cold) ...', flush=True)
        ctx, A = scene(inp)
        before = estimate(ctx)
        lad = ladders(ctx) if hasattr(ctx.G, 'ladder_nodes') else []
        boxes, info = plan_boxes(ctx, a.cell, a.margin)
    except Mismatch as ex:
        sys.exit('patch_nav: TARGET MISMATCH, nothing written: %s' % ex)
    # ---- apply: drop the last run's boxes, add the new ones
    for e in old:
        T['remove'][str(m.g(e, b'nodeID'))] = dict(i=e, why='previous patch_nav box ' + m.name(e))
        for c in m.children(e): T['remove'][str(m.g(c, b'nodeID'))] = dict(i=c, why='its mesh')
        m.remove_node(e)
    if old: m.prune(); tmpl = template(m)
    node_id = [m.next_node_id()]
    for k, b in enumerate(boxes):
        nm = PREFIX + str(k + 1)
        add_box(m, tmpl, b, nm, node_id)
        T['add'].append(dict(type='CMapEntity', **{'class': 'func_nav_markup'}, name=nm, why='NONAV %s' % [round(v) for v in b]))
        T['add'].append(dict(type='CMapMesh', why='box of ' + nm))
    counts = {}
    for e in m.entities(): counts[m.cls(e)] = counts.get(m.cls(e), 0) + 1
    for attrs in m.doc.prefix:
        pre = {x[0]: x for x in attrs}
        if b'map_subasset_reference_names' in pre:
            names = sorted(counts)
            pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
            pre[b'map_subasset_reference_names'][2] = [n.encode() for n in names]
            pre[b'map_subasset_reference_counts'][2] = [counts[n] for n in names]
    n = m.save(outp)
    T['output'] = outp
    json.dump(T, open(tp, 'w'), indent=1)
    area = lambda b: (b[3] - b[0]) * (b[4] - b[1])
    print('patch_nav: %d NONAV boxes (%.1f km2 of ground; %d squares cut, %d left for in-play ground at the same level), %d old ones replaced'
          % (len(boxes), sum(area(b) for b in boxes) * 0.0254 ** 2 / 1e6, info['squares_cut'], info['squares_kept_level'], len(old)))
    print('  in play: %d walk nodes (%s)' % (info['in_play_nodes'], ', '.join('%s %d' % kv for kv in sorted(info['worlds'].items()))))
    print('  wrote %s (%d bytes), targets %s' % (outp, n, tp))
    rep = dict(input=inp, output=outp, cell=a.cell, margin=a.margin, boxes=[list(b) for b in boxes], plan=info, before=before, ladders=lad)
    ratio = TW34_AREAS / before['flood_cells'] if before['nonav_boxes'] == 0 and before['flood_cells'] else None
    if a.estimate:
        print('patch_nav: building the walk graph of the output ...', flush=True)
        ctx2, _ = scene(outp)
        after = estimate(ctx2)
        rep['after'] = after
    rep['areas_per_cell_tw34'] = None
    for k in ('before', 'after'):
        if k not in rep: continue
        e = rep[k]
        print('  %-6s seeds %d, NONAV boxes %d, nodes inside NONAV %d, flood %d cells (%.0f m2)' % (k, e['seeds'], e['nonav_boxes'], e['nonav_nodes'], e['flood_cells'],
              e['flood_cells'] * CP.CELL * CP.CELL * 0.0254 ** 2))
    for l in lad:
        print('  ladder volume %s (%s): bottom nodes %d (volume starts %s u above the floor), top nodes %d' % (l['box'], l['vg'], l['bottom_nodes'], l['gap_bottom'], l['top_nodes']))
    json.dump(rep, open(rp, 'w'), indent=1)
    print('  report %s; %.1f s' % (rp, time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
