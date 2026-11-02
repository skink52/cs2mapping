"""Bare-skin first-person hands: the stock agent's full-finger glove hand mesh (shape, weights, weapon fit) from the template arms DMX,
re-skinned with a generated skin texture laid out on the glove's own UVs. Shading comes from 3D (proximity occlusion between the
fingers, fingertip/knuckle flush, fine mottling), so UV seams don't show. The template's bare forearm piece is dropped (our sleeves cover it).
usage: python3 tools/bare_hands.py <template arms dmx (arms_stock/arms.dmx)> <addon out> [preview.png]
writes models/tw/players/hands_bare/arms.dmx + materials/models/tw/players/hands_bare/"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy.spatial import cKDTree
import dmx9
from noise import fbm

MODEL_DIR = 'models/tw/players'; MAT_DIR = 'materials/models/tw/players'; NAME = 'hands_bare'
TEX = 1024
SKIN = np.array([196, 146, 118], float)          # sRGB base tone
FLUSH = np.array([206, 128, 112], float)         # fingertips / knuckles


def tris(fs):
    out, cur = [], []
    for i in fs['faces']:
        if i < 0:
            out += [(cur[0], cur[k], cur[k + 1]) for k in range(1, len(cur) - 1)]; cur = []
        else: cur.append(i)
    return out


def main(src, out, preview=None):
    dm = dmx9.DMX.load(src)
    model = dm.root['model']
    glove = None
    for c in list(model['children']):
        sh = c.get('shape') if c.type == 'DmeDag' else None
        if sh is None: continue
        if any('glove' in fs['material']['mtlName'] for fs in sh['faceSets']): glove = sh
        else:
            model['children'].remove(c)
            jl = model['jointList']
            if any(j is c for j in jl): jl[:] = [j for j in jl if j is not c]    # mesh dags sit after the bones: indices unchanged
    assert glove is not None, 'no glove mesh in ' + src
    vd = glove['currentState']
    P = np.array(vd['position$0']); pi = np.array(vd['position$0Indices'])
    N = np.array(vd['normal$0']); ni = np.array(vd['normal$0Indices'])
    UV = np.array(vd['texcoord$0']); ui = np.array(vd['texcoord$0Indices'])
    if vd['flipVCoordinates']: UV = UV * [1, -1] + [0, 1]

    # per-position shading in 3D
    pn = np.zeros_like(P); np.add.at(pn, pi, N[ni]); pn /= np.linalg.norm(pn, axis=1, keepdims=True) + 1e-9
    tree = cKDTree(P)
    occ = np.zeros(len(P))
    for i, nb in enumerate(tree.query_ball_point(P, 1.4)):
        d = P[nb] - P[i]; l = np.linalg.norm(d, axis=1); k = l > 0.15
        if k.any(): occ[i] = np.clip((d[k] / l[k, None]) @ pn[i], 0, None).mean()
    occ = np.clip(occ / max(np.percentile(occ, 97), 1e-6), 0, 1)
    flush = np.zeros(len(P))
    for s in (1, -1):                              # per hand: distance from the wrist end (highest z) towards the fingertips
        h = (P[:, 1] * s) > 0
        if not h.any(): continue
        z = P[h, 2]; t = (z.max() - z) / max(np.ptp(z), 1e-6)
        flush[h] = np.clip((t - 0.55) / 0.45, 0, 1) ** 1.5
    mott = fbm(P[:, 0] / 0.9 + P[:, 2] / 2.1, P[:, 1] / 0.9 + P[:, 2] / 1.7, 1.0, 3, seed=31)
    col = SKIN[None] * (1 - 0.35 * flush[:, None]) + FLUSH[None] * 0.35 * flush[:, None]
    col = col * (1.0 - 0.42 * occ[:, None]) * (0.96 + 0.08 * mott[:, None])

    # rasterise per face corner into the glove's UV layout
    img = np.zeros((TEX, TEX, 3)); cov = np.zeros((TEX, TEX))
    T = [t for fs in glove['faceSets'] for t in tris(fs)]
    for a, b, c in T:
        uv = UV[ui[[a, b, c]]] * TEX; cc = col[pi[[a, b, c]]]
        x0, y0 = np.floor(uv.min(0)).astype(int); x1, y1 = np.ceil(uv.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, TEX - 1), min(y1, TEX - 1)
        if x1 < x0 or y1 < y0: continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = uv
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9: continue
        w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; w2 = 1 - w0 - w1
        m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not m.any(): continue
        v = w0[..., None] * cc[0] + w1[..., None] * cc[1] + w2[..., None] * cc[2]
        sl = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        img[sl][m] = v[m]; cov[sl][m] = 1
    for _ in range(12):                            # pad islands so mips don't bleed the background in
        k = cov > 0
        acc = np.zeros_like(img); n = np.zeros_like(cov)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            acc += np.roll(np.roll(img * k[..., None], dx, 1), dy, 0); n += np.roll(np.roll(k, dx, 1), dy, 0)
        fill = (~k) & (n > 0); img[fill] = acc[fill] / n[fill, None]; cov[fill] = 1
    img[cov == 0] = SKIN * 0.9
    grain = fbm(*np.meshgrid(np.arange(TEX) / 9.0, np.arange(TEX) / 9.0), 1.0, 2, seed=5)[..., None]
    img = np.clip(img * (0.985 + 0.03 * grain), 0, 255).astype(np.uint8)

    md = os.path.join(out, MAT_DIR, NAME); os.makedirs(md, exist_ok=True)
    Image.fromarray(img).save(os.path.join(md, NAME + '_color.png'))
    rough = np.clip(150 + 40 * occ.mean() + 25 * (grain[..., 0] - 0.5), 0, 255).astype(np.uint8)
    Image.fromarray(rough).filter(ImageFilter.GaussianBlur(1)).save(os.path.join(md, NAME + '_rough.png'))
    rel = '%s/%s/' % (MAT_DIR, NAME)
    open(os.path.join(md, NAME + '.vmat'), 'w', newline='\n').write(
        '// bare first-person hands (generated, tools/bare_hands.py)\nLayer0\n{\n\tshader "csgo_complex.vfx"\n\tF_SPECULAR 1\n'
        '\tTextureColor "%s%s_color.png"\n\tTextureRoughness "%s%s_rough.png"\n}\n' % (rel, NAME, rel, NAME))
    for fs in glove['faceSets']: fs['material']['mtlName'] = rel + NAME + '.vmat'
    glove.name = NAME
    d = os.path.join(out, MODEL_DIR, NAME); os.makedirs(d, exist_ok=True)
    dm.save(os.path.join(d, 'arms.dmx'))
    if preview:
        vc = np.zeros((len(P), 3)); vc[pi] = col[pi]
        from glbskin import splat
        lit = np.clip(0.55 + 0.45 * (pn @ np.array([0.3, -0.4, 0.86])), 0.3, 1)[:, None]
        ims = [splat(P, np.clip(vc * lit, 0, 255).astype(np.uint8), (ax, ay, az), 600, 400)
               for ax, ay, az in ((np.array([0, 1, 0.]), np.array([0, 0, 1.]), np.array([1, 0, 0.])),
                                  (np.array([0, 1, 0.]), np.array([1, 0, 0.]), np.array([0, 0, 1.])))]
        sheet = Image.new('RGB', (1200, 400)); sheet.paste(ims[0], (0, 0)); sheet.paste(ims[1], (600, 0))
        sheet.save(preview)
    print('bare hands: %d positions, %d tris, occlusion mean %.2f' % (len(P), len(T), occ.mean()))


if __name__ == '__main__':
    main(*sys.argv[1:4])
