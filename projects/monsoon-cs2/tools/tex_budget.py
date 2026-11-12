"""Texel density and texture memory of the procedural props (mg_monsoon playtest 1, finding 16).

usage: python tex_budget.py [--addon ../out/addon] [--game <game addon>] [--json out.json] [names...]

Per prop (props.json): every LOD0 SMD material group -> its vmat (vmdl remaps) -> colour texture size, then the area-weighted texel
density sqrt(sum(uv area * tex px^2) / sum(world area)) in px per unit and px per metre (40 u = 1 m). Tiling materials count their
UVs as they are (several tiles per face is fine). Memory: the compiled vtex_c files in the game addon (header w, h, format, mips),
in MiB of VRAM, summed over the unique textures the props reference (shared tile/stock textures counted once).
"""
import os, sys, re, json, struct
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
U_PER_M = 40.0
BPP = {1: 0.5, 2: 1.0, 20: 1.0, 21: 1.0, 27: 0.5, 4: 4.0, 28: 4.0, 26: 0.5, 25: 1.0}   # DXT1, DXT5, BC4?, BC5, BC7..., RGBA8888


def vtex_info(path):
    """(w, h, fmt, mips, bytes of VRAM incl. mips) from a compiled vtex_c header"""
    data = open(path, 'rb').read(4096)
    size, hv, ver, boff, bcount = struct.unpack('<IHHII', data[:16])
    blocks = {}
    for k in range(bcount):
        p = 8 + boff + k * 12
        t, o, s = struct.unpack_from('<4sII', data, p)
        blocks[t] = (p + 4 + o, s)
    off, sz = blocks[b'DATA']
    w, h, depth, fmt, nmip = struct.unpack_from('<HHHBB', data, off + 20)
    tot = 0
    for j in range(nmip):
        mw, mh = max(1, w >> j), max(1, h >> j)
        if fmt in (1, 2, 20, 21, 27, 26, 25):
            blk = {1: 8, 27: 8, 26: 8}.get(fmt, 16)
            tot += max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * blk
        else:
            tot += mw * mh * BPP.get(fmt, 4.0)
    return w, h, fmt, nmip, tot * max(1, depth)


def read_smd(path):
    mats = {}
    lines = open(path).read().split('\n')
    i = lines.index('triangles') + 1
    while i + 3 < len(lines) and lines[i] != 'end':
        m = lines[i]
        v = [lines[i + k].split() for k in (1, 2, 3)]
        mats.setdefault(m, []).append([[float(x) for x in vv[1:4]] + [float(vv[7]), float(vv[8])] for vv in v])
        i += 4
    return {k: np.array(v) for k, v in mats.items()}


def vmdl_remaps(path):
    txt = open(path).read()
    return dict(re.findall(r'from = "([^"]+)"\s*to = "([^"]+)"', txt))


def vmat_textures(addon, vmat):
    p = os.path.join(addon, vmat)
    if not os.path.isfile(p): return {}
    return dict(re.findall(r'\t(Texture\w+) "([^"\[]+)"', open(p).read()))


def png_size(addon, rel):
    from PIL import Image
    p = os.path.join(addon, rel)
    if os.path.isfile(p):
        return Image.open(p).size
    return None


def density(tris, tex):
    """area-weighted MEDIAN texel density (px/unit) of the triangles, and their world area. The median, not the mean: with
    index-spaced UVs (before 13 Nov 2026) the thin edge bands of every box held most texels and the mean hid that the faces
    themselves got a third of the linear density."""
    P = tris[..., :3]; T = tris[..., 3:5]
    wa = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) / 2
    ua = np.abs((T[:, 1, 0] - T[:, 0, 0]) * (T[:, 2, 1] - T[:, 0, 1]) - (T[:, 2, 0] - T[:, 0, 0]) * (T[:, 1, 1] - T[:, 0, 1])) / 2
    ok = wa > 1e-6
    if not ok.any(): return 0.0, 0.0
    d = np.sqrt(ua[ok] * tex[0] * tex[1] / wa[ok])
    o = np.argsort(d); c = np.cumsum(wa[ok][o]); c /= c[-1]
    return float(d[o][min(len(o) - 1, np.searchsorted(c, 0.5))]), float(wa[ok].sum())


def main(argv):
    addon = os.path.join(HERE, '..', 'out', 'addon')
    game = r'C:\source1\links\game_addons\mg_monsoon'
    out = None
    names = []
    it = iter(argv)
    for a in it:
        if a == '--addon': addon = next(it)
        elif a == '--game': game = next(it)
        elif a == '--json': out = next(it)
        else: names.append(a)
    props = json.load(open(os.path.join(addon, '..', 'props.json')))
    rep = {}
    seen_tex = {}
    for n in (names or sorted(props)):
        info = props[n]
        mdir = os.path.join(addon, os.path.dirname(info['model']))
        smd = os.path.join(mdir, n + '_lod0.smd')
        vmdl = os.path.join(addon, info['model'])
        if not os.path.isfile(smd) or not os.path.isfile(vmdl): continue
        rem = vmdl_remaps(vmdl)
        groups = read_smd(smd)
        rows = {}
        for mname, tris in groups.items():
            vm = rem.get(mname + '.vmat') or rem.get(mname)
            if vm is None: continue
            tx = vmat_textures(addon, vm)
            col = tx.get('TextureColor')
            sz = png_size(addon, col) if col else None
            if sz is None: sz = (1024, 1024)      # a game material read from the VPK: assume 1024
            d, area = density(tris, sz)
            rows[mname] = dict(vmat=vm, tex=list(sz), px_per_u=round(d, 2), px_per_m=round(d * U_PER_M), area_m2=round(area / U_PER_M ** 2, 2))
            # the compiler packs roughness into the normal map, metalness and translucency into the colour map's alpha
            # (no vtex_c of their own): count colour (BC7 with alpha/metal, else DXT1), normal (BC7), AO (BC4)
            packed = any(k in tx for k in ('TextureMetalness', 'TextureTranslucency'))
            for k, t in tx.items():
                if k in ('TextureColor', 'TextureNormal', 'TextureAmbientOcclusion'):
                    seen_tex.setdefault(t, dict(props=set(), bpp={'TextureColor': 1.0 if packed else 0.5, 'TextureNormal': 1.0}.get(k, 0.5)))['props'].add(n)
        tot = sum(r['area_m2'] for r in rows.values())
        avg = sum(r['px_per_m'] * r['area_m2'] for r in rows.values()) / max(tot, 1e-6) if rows else 0   # area-weighted over groups
        rep[n] = dict(groups=rows, area_m2=round(tot, 2), px_per_m=round(float(avg)))
    # VRAM from compiled textures
    vram = {}
    for t in seen_tex:
        base = os.path.splitext(t)[0]
        d = os.path.join(game, os.path.dirname(t))
        stem = os.path.basename(base) + '_png_'
        hit = [f for f in os.listdir(d) if f.startswith(stem) and f.endswith('.vtex_c')] if os.path.isdir(d) else []
        if hit:
            w, h, fmt, nm, b = vtex_info(os.path.join(d, hit[0]))
            vram[t] = dict(w=w, h=h, fmt=fmt, mips=nm, mib=round(b / 2 ** 20, 3), compiled=True)
        else:
            sz = png_size(addon, t)
            if sz:   # not compiled yet: estimate from the format the compiler picks (bytes per pixel above) with mips
                vram[t] = dict(w=sz[0], h=sz[1], fmt=None, mips=None, mib=round(sz[0] * sz[1] * seen_tex[t]['bpp'] * 4 / 3 / 2 ** 20, 3), compiled=False)
        # a compiled file older than its png is stale: estimate instead
        if vram.get(t, {}).get('compiled') and os.path.isfile(os.path.join(addon, t)) and \
                os.path.getmtime(os.path.join(d, hit[0])) < os.path.getmtime(os.path.join(addon, t)):
            sz = png_size(addon, t)
            vram[t] = dict(w=sz[0], h=sz[1], fmt=None, mips=None, mib=round(sz[0] * sz[1] * seen_tex[t]['bpp'] * 4 / 3 / 2 ** 20, 3), compiled=False)
    total = sum(v['mib'] for v in vram.values())
    res = dict(props=rep, textures=vram, total_mib=round(total, 1), n_textures=len(vram))
    print('%-22s %8s %8s  groups (px/m @ area m2)' % ('prop', 'm2', 'px/m'))
    for n, r in rep.items():
        g = ', '.join('%s %d@%.1f' % (k.replace(n + '_', ''), v['px_per_m'], v['area_m2']) for k, v in r['groups'].items())
        print('%-22s %8.1f %8d  %s' % (n, r['area_m2'], r['px_per_m'], g))
    print('textures %d, VRAM %.1f MiB (compiled where found, else estimated 1 B/px + mips)' % (len(vram), total))
    if out: json.dump(res, open(out, 'w'), indent=1)
    return res


if __name__ == '__main__':
    main(sys.argv[1:])
