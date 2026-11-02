"""Top-down check images of the converted maps: floors coloured by texture and height, spawns (T red, CT blue),
bomb sites, buy zones. Reads the written vmap back, like preview/scene.py.

usage: python3 tools/overview.py <map.vmap> <addon dir> <maps.json> <out prefix>
"""
import os, sys, json, re
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx9

vmap, addon, mj, prefix = sys.argv[1:5]
dm = dmx9.DMX.load(vmap)
maps = json.load(open(mj))['maps']
avg = {}


def colour(mat):
    if mat in avg: return avg[mat]
    c = (120, 120, 120)
    f = os.path.join(addon, mat)
    if os.path.exists(f):
        m = re.search(r'TextureColor "([^"]+)"', open(f).read())
        if m and os.path.exists(os.path.join(addon, m.group(1))):
            c = tuple(int(x) for x in np.asarray(Image.open(os.path.join(addon, m.group(1))).convert('RGB')).reshape(-1, 3).mean(0))
    avg[mat] = c
    return c


def walk(e, out):
    for c in e.get('children', []) or []:
        out.append(c); walk(c, out)
    return out


polys = []
for node in walk(dm.root['world'], []):
    if node.type != 'CMapMesh': continue
    md = node['meshData']; o = np.array(node['origin'])
    pos = np.array(md['vertexData']['streams'][0]['data'])
    mats = md['materials']; mi = {s.name: s['data'] for s in md['faceData']['streams']}['materialindex:0']
    ev, en, vdi = md['edgeVertexIndices'], md['edgeNextIndices'], md['vertexDataIndices']
    for f, h0 in enumerate(md['faceEdgeIndices']):
        mat = mats[mi[md['faceDataIndices'][f]]]
        if mat.startswith('materials/tools/') or 'moondome' in mat: continue
        L = []; h = h0
        while True:
            L.append(pos[vdi[ev[h]]] + o); h = en[h]
            if h == h0: break
        P = np.array(L)
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) == 0 or n[2] / np.linalg.norm(n) < 0.5: continue
        polys.append((P[:, 2].mean(), P, mat))
polys.sort(key=lambda t: t[0])
for M in maps:
    lo, hi = np.array(M['bounds'][0]), np.array(M['bounds'][1])
    s = 0.2
    W, H = int((hi[0] - lo[0]) * s) + 1, int((hi[1] - lo[1]) * s) + 1
    im = Image.new('RGB', (W, H), (0, 0, 0)); dr = ImageDraw.Draw(im)
    X = lambda x: (x - lo[0]) * s
    Y = lambda y: (hi[1] - y) * s
    for z, P, mat in polys:
        if not (lo[0] - 1 <= P[:, 0].min() and P[:, 0].max() <= hi[0] + 1 and lo[1] - 1 <= P[:, 1].min() and P[:, 1].max() <= hi[1] + 1): continue
        k = 0.45 + 0.55 * (z - lo[2]) / max(1, hi[2] - lo[2])
        c = tuple(int(v * k) for v in colour(mat))
        dr.polygon([(X(p[0]), Y(p[1])) for p in P], fill=c)
    for z in M['buyzones']:
        dr.rectangle([X(z['mins'][0]), Y(z['maxs'][1]), X(z['maxs'][0]), Y(z['mins'][1])], outline=(255, 80, 80) if z['team'] == 2 else (80, 140, 255))
    for bs in M['buyspots']:
        for p in bs['points']:
            r = bs['radius'] * s
            dr.ellipse([X(p[0]) - r, Y(p[1]) - r, X(p[0]) + r, Y(p[1]) + r], outline=(255, 80, 80) if bs['team'] == 2 else (80, 140, 255))
    for site in M['sites']:
        dr.rectangle([X(site['mins'][0]), Y(site['maxs'][1]), X(site['maxs'][0]), Y(site['mins'][1])], outline=(255, 255, 0), width=2)
        dr.text((X(site['mins'][0]) + 3, Y(site['maxs'][1]) + 3), site['letter'], fill=(255, 255, 0))
    for team, col in (('T', (255, 40, 40)), ('CT', (40, 120, 255))):
        for i, p in enumerate(M['spawns'][team]):
            dr.ellipse([X(p[0]) - 3, Y(p[1]) - 3, X(p[0]) + 3, Y(p[1]) + 3], fill=col)
    im.save('%s_%s.png' % (prefix, M['key']))
    print(M['key'], W, H)
