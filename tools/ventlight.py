"""Stage D pass `ventlight`: crawl-space vents capped by func_breakable grates get their own stationary light.

In CS:GO the grates (func_breakable) didn't block baked light, so some light reached the ducts behind them. In CS2 the ducts
bake pitch black, and players / weapons inside get no direct light (skink52, ttt_cg_skyscraper_2017, 29 Oct 2026).

A cover is a func_breakable that is thin on one axis (< 8 u), at most 160 u across and not glass. On each side of it the empty space is
measured (8-unit voxels of the world geometry near the covers): a side is a duct when the opening there is no wider than the cover
(+24 u) and runs at least 48 u deep. Each duct gets a light_omni2 (directlight 3 = Stationary, no shadows, warm white, dim, range =
duct depth, 128-384) up to 96 u in from the cover; lights closer than 160 u to one already placed are skipped (a duct capped at
both ends gets one per end only when it is long). The covers get "disableshadows" 1 so they don't cast shadows over the duct.
"""
import numpy as np
from lighting import mesh_polys, TOOL_PASS
import vmapedit as V

VS = 8.0


def covers(m):
    out = []
    for e in m.by_class('func_breakable'):
        b = m.bounds(e)
        if not b: continue
        size = [b[1][k] - b[0][k] for k in range(3)]
        thin = int(np.argmin(size))
        if size[thin] >= 8 or max(size) > 160: continue
        mats = [x.decode().lower() for ch in m.children(e) if m.type(ch) == b'CMapMesh' for x in m.g(m.g(ch, b'meshData'), b'materials') or []]
        if any('glass' in x or 'wndw' in x or 'window' in x for x in mats): continue      # windows, not vents
        out.append((e, np.array(b[0]), np.array(b[1]), thin))
    return out


def world_polys_near(m, lo, hi):
    polys = []
    def walk(n):
        for c in m.children(n):
            t = m.type(c)
            if t == b'CMapMesh':
                for mat, loop in mesh_polys(m, c):
                    if mat.startswith(TOOL_PASS): continue
                    P = np.array(loop)
                    if (P.max(0) >= lo).all() and (P.min(0) <= hi).all(): polys.append(P)
            elif t == b'CMapGroup': walk(c)
    walk(m.world)
    return polys


def voxelise(polys, lo, shape):
    solid = np.zeros(shape, bool)
    for P in polys:
        for i in range(1, len(P) - 1):
            a, b, c = P[0], P[i], P[i + 1]
            n = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / (VS * 0.4)) + 2
            u, w = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
            k = (u + w) <= 1
            q = a + np.outer(u[k], b - a) + np.outer(w[k], c - a)
            idx = np.floor((q - lo) / VS).astype(int)
            ok = ((idx >= 0) & (idx < np.array(shape))).all(1)
            idx = idx[ok]
            solid[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    return solid


def run(m, c):
    cv = covers(m)
    if not cv: return 0
    lo = np.min([x[1] for x in cv], 0) - 600; hi = np.max([x[2] for x in cv], 0) + 600
    shape = tuple(int(x) for x in np.ceil((hi - lo) / VS))
    solid = voxelise(world_polys_near(m, lo, hi), lo, shape)

    def free(p, d, limit):
        """free distance from p along unit axis vector d"""
        for s in range(1, int(limit / VS) + 1):
            q = p + d * s * VS
            i = tuple(np.floor((q - lo) / VS).astype(int))
            if any(x < 0 or x >= shape[k] for k, x in enumerate(i)) or solid[i]: return (s - 1) * VS
        return limit

    tmpl = next(iter(m.by_class('light_omni2')), None)
    base = {a[0].decode(): a[2].decode() for a in m.props(tmpl)['attrs'] if a[0] not in (b'classname', b'targetname')} if tmpl else {}
    placed = []; nduct = 0
    for e, b0, b1, ax in cv:
        ctr = (b0 + b1) / 2; size = b1 - b0
        u, v = [k for k in range(3) if k != ax]
        duct = False
        for s in (1, -1):
            n = np.zeros(3); n[ax] = s
            p = ctr + n * (size[ax] / 2 + 12)
            ex = lambda k, sg: free(p, np.eye(3)[k] * sg, 256)
            wu = ex(u, 1) + ex(u, -1); wv = ex(v, 1) + ex(v, -1)
            depth = free(p, n, 1024)
            if wu > size[u] + 24 or wv > size[v] + 24 or depth < 48: continue
            duct = True
            pos = p + n * min(depth / 2, 96)
            if any(np.linalg.norm(pos - q) < 160 for q in placed): continue
            props = dict(base)
            props.update({'directlight': '3', 'castshadows': '0', 'enabled': '1', 'color': '255 236 210', 'colormode': '0',
                          'brightness': '-1.5', 'brightness_legacy': '0.35', 'brightness_units': '1', 'brightness_lumens': '350',
                          'brightness_candelas': '28', 'brightness_nits': '3436', 'range': '%.0f' % min(max(depth, 128), 384),
                          'targetname': 'port_ventlight_%d' % (len(placed) + 1)})
            m.new_entity('light_omni2', [float(x) for x in pos], props)
            placed.append(pos)
        if duct: m.setp(e, 'disableshadows', '1'); nduct += 1
    c.log.append('ventlight: %d of %d thin func_breakables are vent covers, %d stationary lights placed in the ducts behind them (no shadows, dim); covers set to Disable Shadows'
                 % (nduct, len(cv), len(placed)))
    return len(placed)
