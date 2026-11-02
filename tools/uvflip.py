"""Upside-down textures on vertical faces: flips V where it runs upward, for faces whose material matches.

  python uvflip.py <vmap in> <vmap out> <material substring> [...]

Source draws a texture top-down (V grows downward on a wall). mg_minecraft_adventure's torches had 101 sides whose V ran upward, so the torch
showed upside down. Each such face gets V negated in both its texture coordinates and its Hammer texture axis (textureaxisv, all four values),
so the two stay consistent and Hammer shows the same thing it builds. Floors and ceilings are left alone. Rerun-safe: a flipped face reads upright.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V
from texfix import stream

def run(m, words):
    n = 0
    for node, _ in m.walk():
        if m.type(node) != b'CMapMesh': continue
        md = m.g(node, b'meshData')
        if md is None or md < 0: continue
        mats = [x.decode().lower() for x in m.g(md, b'materials') or []]
        if not any(w in x for x in mats for w in words): continue
        fd = m.g(md, b'faceData')
        vs, mis = stream(m, fd, b'textureaxisv'), stream(m, fd, b'materialindex')
        pos = stream(m, m.g(md, b'vertexData'), b'position'); tc = stream(m, m.g(md, b'faceVertexData'), b'texcoord')
        fei, evi, nxt, vdi, fdi, evd = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices', b'faceDataIndices', b'edgeVertexDataIndices'))
        if None in (vs, mis, pos, tc, fei, evi, nxt, vdi, fdi, evd): continue
        # decide every face first, then flip each shared texcoord once: neighbouring faces share entries, and flipping as we go
        # half-flipped the next face (54 of mg_minecraft_adventure's 101 torch sides on the first try)
        pick, entries = [], set()
        for f, he in enumerate(fei):
            fi = fdi[f]
            if not any(w in mats[mis[fi]] for w in words): continue
            hs, h = [], he
            for _ in range(64):
                hs.append(h); h = nxt[h]
                if h == he: break
            zs = [pos[vdi[evi[x]]][2] for x in hs]
            if max(zs) - min(zs) < 1: continue
            top = max(hs, key=lambda x: pos[vdi[evi[x]]][2]); bot = min(hs, key=lambda x: pos[vdi[evi[x]]][2])
            if tc[evd[top]][1] - tc[evd[bot]][1] <= 0: continue          # already top-down
            pick.append(fi); entries |= {evd[x] for x in hs}
        for x in entries:
            u, v = tc[x][0], tc[x][1]; tc[x] = type(tc[x])([u, -v])
        for fi in set(pick): vs[fi] = type(vs[fi])([-c for c in vs[fi]])
        n += len(pick)
    return n

if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    mp = V.Map(sys.argv[1]); n = run(mp, [w.lower() for w in sys.argv[3:]]); mp.save(sys.argv[2])
    print('summary\tflipped=%d' % n)
