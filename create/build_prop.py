"""Bakes and writes one prop: LOD meshes (same chart layout), atlas textures, vmat, vmdl, physics hulls, preview."""
import os, sys, time
import numpy as np
from PIL import Image
import bake, modelio, render, stock

OUT = os.environ.get('CS2_ADDON_OUT', os.path.join(os.path.dirname(__file__), '..', 'out', 'addon'))
PREV = os.environ.get('CS2_PREVIEW_DIR', os.path.join(os.path.dirname(os.path.abspath(OUT)), 'preview'))
ROOT = os.environ.get('CS2_MODEL_PREFIX', 'props')


def build(name, spec, preview=True, cam=None):
    t0 = time.time()
    lods = spec['lods']
    m0 = lods[0]
    groups = dict(spec.get('atlases') or {'main': dict(size=spec.get('size', 1024))})
    shaders = dict(spec['shaders'])
    if any(c['mat'] == 'decal' for c in m0.charts):
        groups['decal'] = dict(size=spec.get('decal_size', 512), alpha=lambda b: b['metal'], metal=False, fill=0.92)
        shaders['decal'] = decal_shader(spec['decal_imgs'])
    # split charts by atlas key; charts on stock materials skip the bake (a list value = variants picked per part)
    smap = spec.get('stock', stock.assign(name))
    chart_atlas = [('~' + _skey(smap[c['mat']], 0)) if c['mat'] in smap else c.get('atlas', 'main') for c in m0.charts]
    rel_dir = 'models/%s/%s' % (ROOT, name)
    mat_rel = 'materials/models/%s/%s' % (ROOT, name)
    os.makedirs(os.path.join(OUT, rel_dir), exist_ok=True)
    uvs = [np.zeros((len(m.V), 2)) for m in lods]
    vmats = {}
    previews = []
    for key, g in groups.items():
        ids = [i for i, a in enumerate(chart_atlas) if a == key]
        if not ids: continue
        sub = submesh(m0, ids)
        baked = bake.bake(sub, shaders, size=g['size'], res=spec.get('res'), ground=spec.get('ground'),
                          fill=g.get('fill', 0.8), normal_strength=spec.get('normal_strength', 1.0))
        # recompute the atlas uv for every LOD with the same packing
        d, rects = bake.pack([m0.charts[i] for i in ids], g['size'], g.get('fill', 0.8))
        for li, m in enumerate(lods):
            idmap = {c: k for k, c in enumerate(ids)}
            vchart = np.full(len(m.V), -1); vchart[m.F.ravel()] = np.repeat(m.FC, 3)
            for c, k in idmap.items():
                sel = vchart == c
                if not sel.any(): continue
                R = rects[k]
                uvs[li][sel, 0] = (R[0] + m.T[sel, 0] * R[2]) / g['size']
                uvs[li][sel, 1] = (R[1] + m.T[sel, 1] * R[3]) / g['size']
        tname = name if key == 'main' else '%s_%s' % (name, key)
        tex = modelio.write_textures(OUT, mat_rel, tname, baked, metal=g.get('metal', spec.get('metal', False)))
        if g.get('alpha') is not None:
            a = g['alpha'](baked)
            Image.fromarray(modelio.to8(a)).save(os.path.join(OUT, mat_rel, tname + '_trans.png'))
            alpha = '%s/%s_trans.png' % (mat_rel, tname)
        else:
            alpha = None
        vm = '%s/%s.vmat' % (mat_rel, tname)
        modelio.write_vmat(OUT, vm, tex, comment='mg_trenchwarfare %s (procedural, AI-generated)' % tname, alpha=alpha,
                           backfaces=g.get('backfaces', False))
        vmats[key] = vm
        if g.get('alpha') is not None:
            baked = dict(baked, alpha=g['alpha'](baked), metal=np.zeros_like(baked['metal']))
        previews.append((sub, bake.atlas_uv(sub, rects, g['size']), baked))
    # SMDs: one material name per atlas, one per stock material (tiling uv per face corner)
    meshes = []
    skeys = sorted({k for c in m0.charts if c['mat'] in smap for k in (smap[c['mat']] if isinstance(smap[c['mat']], (list, tuple)) else [smap[c['mat']]])})
    for li, m in enumerate(lods):
        fuv = uvs[li][m.F]
        groups_ = []
        fmat = np.array([_skey(smap.get(m.charts[c]['mat'], ''), p) for c, p in zip(m.FC, m.FP)], object) if len(m.FC) else np.zeros(0, object)
        for key in vmats:
            ids = [i for i, a in enumerate(chart_atlas) if a == key]
            groups_.append(('%s_%s' % (name, key), np.isin(m.FC, ids) & (fmat == '')))
        for sk in skeys:
            fsel = fmat == sk
            if fsel.any(): fuv[fsel] = stock.uv_for(m, fsel, sk)
            groups_.append(('stock_%s' % sk, fsel))
            if li == 0: previews.append(stock_preview(m, fsel, fuv[fsel], sk))
        mn = '%s_lod%d' % (name, li)
        write_multi_smd(os.path.join(OUT, rel_dir, mn + '.smd'), m, fuv, groups_)
        meshes.append(mn)
    for sk in skeys:
        vmats['~' + sk] = stock.STOCK[sk]['vmat']
    hull_names = []
    for k, pts in enumerate(spec.get('hulls', [])):
        hn = '%s_hull%d' % (name, k)
        modelio.write_hull_smd(os.path.join(OUT, rel_dir, hn + '.smd'), [pts])
        hull_names.append(hn)
    remaps = [(('stock_%s.vmat' % k[1:]) if k.startswith('~') else ('%s_%s.vmat' % (name, k)), v) for k, v in vmats.items()]
    txt = modelio.vmdl_text(name, rel_dir, meshes, remaps, hull_names, surface=spec.get('surface', 'default'),
                            lod_thresholds=spec.get('lod_thresholds'), entity='')
    open(os.path.join(OUT, rel_dir, name + '.vmdl'), 'w', newline='\n').write(txt)
    lo, hi = m0.bounds()
    info = dict(model='%s/%s.vmdl' % (rel_dir, name), tris=[int(m.tri_count()) for m in lods], mins=lo.round(1).tolist(), maxs=hi.round(1).tolist())
    print('%s: %s tris %s  bounds %s..%s  %.1fs' % (name, info['model'], info['tris'], info['mins'], info['maxs'], time.time() - t0))
    if preview:
        os.makedirs(PREV, exist_ok=True)
        c = (lo + hi) / 2
        rad = float(np.linalg.norm(hi - lo)) * 1.3
        if cam: c, rad = cam.get('c', c), cam.get('r', rad)
        render.turntable(previews, c, rad, os.path.join(PREV, name + '.png'), n=4, elev=cam.get('elev', 22) if cam else 22)
    return info


def _skey(v, part):
    if isinstance(v, (list, tuple)):
        return v[(int(part) * 2654435761 >> 7) % len(v)]
    return v


def decal_shader(imgs):
    """decal charts: colour from the image projected over the quad, alpha (worn by noise) returned in the metal channel"""
    from noise import fbm
    def sh(ctx):
        col = np.zeros((ctx.n, 3), np.float32); a = np.zeros(ctx.n, np.float32)
        for p in np.unique(ctx.part):
            sel = ctx.part == p
            part = ctx.parts[p]; img = imgs[ctx.chart_info[ctx.chart[sel][0]]['decal']]
            d = ctx.P[sel] - part['decal_o']
            u = d @ part['decal_u'] / part['decal_s'][0]; v = d @ part['decal_v'] / part['decal_s'][1]
            H, W = img.shape[:2]
            px = np.clip((u * (W - 1)).astype(int), 0, W - 1); py = np.clip(((1 - v) * (H - 1)).astype(int), 0, H - 1)
            rgba = img[py, px]
            n = fbm(ctx.P[sel, 0] * 0.45, ctx.P[sel, 1] * 0.45, ctx.P[sel, 2] * 0.45, 3, seed=91)
            n2 = fbm(ctx.P[sel, 0] * 2.2, ctx.P[sel, 1] * 2.2, ctx.P[sel, 2] * 2.2, 2, seed=92)
            wear = np.clip((n + 0.8) / 0.3, 0, 1) * np.clip(0.85 + 0.6 * n2, 0, 1)
            a[sel] = rgba[:, 3] * wear
            col[sel] = rgba[:, :3] * (0.82 + 0.18 * np.clip(0.5 + n2, 0, 1))[:, None]
        return dict(color=col, rough=np.full(ctx.n, 0.72, np.float32), metal=a)
    return sh


def submesh(m, chart_ids):
    import geo
    sel = np.isin(m.FC, chart_ids)
    s = geo.Mesh()
    used = np.unique(m.F[sel].ravel())
    remap = -np.ones(len(m.V), np.int64); remap[used] = np.arange(len(used))
    s.V, s.N, s.T = m.V[used], m.N[used], m.T[used]
    s.F = remap[m.F[sel]]
    cmap = {c: k for k, c in enumerate(chart_ids)}
    s.FC = np.array([cmap[c] for c in m.FC[sel]], np.int64)
    s.charts = [m.charts[c] for c in chart_ids]
    s.parts = m.parts; s.FP = m.FP[sel]
    return s


_STOCK_PREV = {}


def stock_preview(m, fsel, fuv, key):
    """(mesh, uv, textures) for the turntable: stock faces unshared so each corner keeps its own uv"""
    import geo
    if key not in _STOCK_PREV:
        p = os.path.join(os.environ.get('STOCK_PREVIEW_DIR', os.path.join(__import__('tempfile').gettempdir(), 'stockprev')), key + '.png')
        try:
            if not os.path.exists(p):
                import vtexread as V
                os.makedirs(os.path.dirname(p), exist_ok=True)
                vm = stock.STOCK[key]['vmat']
                if not vm.endswith('.vmat') or os.path.exists(os.path.join(OUT, vm)):
                    import re
                    txt = open(os.path.join(OUT, vm)).read()
                    tc = re.search(r'TextureColor "([^"]+)"', txt).group(1)
                    tn = re.search(r'g_vColorTint "\[([\d. ]+)\]"', txt)
                    im = np.asarray(Image.open(os.path.join(OUT, tc)).convert('RGB').resize((512, 512)), np.float32)
                    if tn: im = im * np.array([float(v) for v in tn.group(1).split()[:3]])
                    Image.fromarray(im.clip(0, 255).astype(np.uint8)).save(p)
                else:
                    r = [x for x in V.refs(V.vpk_read(vm + '_c')) if '_color' in x][0]
                    V.decode_vtex(V.vpk_read(r + '_c'), 1).convert('RGB').save(p)
            col = np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0
        except Exception:
            col = np.full((4, 4, 3), 0.5)
        h, w = col.shape[:2]
        _STOCK_PREV[key] = dict(color=col, normal=np.tile([0, 0, 1.0], (h, w, 1)), rough=np.full((h, w), 0.8), ao=np.ones((h, w)), metal=np.zeros((h, w)))
    F = m.F[fsel]
    s = geo.Mesh(); s.V = m.V[F].reshape(-1, 3); s.N = m.N[F].reshape(-1, 3); s.T = np.zeros((len(s.V), 2))
    s.F = np.arange(len(s.V)).reshape(-1, 3)
    return s, fuv.reshape(-1, 2), _STOCK_PREV[key]


def write_multi_smd(path, mesh, uv, groups):
    """uv: per vertex (nv,2) or per face corner (nf,3,2)"""
    V, N = mesh.V, mesh.N
    if uv.ndim == 2: uv = uv[mesh.F]
    lines = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f"
    for matname, fsel in groups:
        for f, fu in zip(mesh.F[fsel], uv[fsel]):
            lines.append(matname)
            for i, t in zip(f, fu):
                x, y, z = V[i]; nx, ny, nz = N[i]
                lines.append(fmt % (y, -x, z, ny, -nx, nz, t[0], 1 - t[1]))
    lines.append("end")
    open(path, 'w', newline='\n').write("\n".join(lines) + "\n")
