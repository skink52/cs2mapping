"""Textured night preview of the Sprawl map without CS2 (the old tools/vmap_preview.py is flat grey: SPRAWL_NOTES finding 10).
Three steps; the first two write into a work folder (not the repo), the third renders with Cycles in headless Blender.

  python -I tools/arenas/sprawl_preview.py dump <map.vmap> <work dir> [zmin,zmax]
      -> <work>/map.npz (every drawn face of one arena copy: corners, the stored texcoords, material), <work>/props.json
         (prop_static placements), <work>/lights.json (light_omni2), <work>/models.txt (the stock models used)
  node tools/arenas/sprawl_prop_meshes.mjs <work>/models.txt <work>/prop_meshes.json        (LOD 0 of each stock model, from pak01)
  blender -b --python tools/arenas/sprawl_preview_bl.py -- <work dir> <addon content dir> <out prefix> <shot>[,<shot>...] [samples]
      shots: see SHOTS in sprawl_preview_bl.py (square, square_low, avenue, deck, top)

What it is good for: judging composition, scale, density and where the light is. What it is not: the engine. Emissive surfaces light
the scene directly here (in CS2 only the baked light_omni2 do), stock materials are a flat guessed colour, there is no fog or rain.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'tools'), os.path.join(REPO, 'create')]
import numpy as np

SKIP = ('materials/tools/', 'moondome', 'toolsskybox', 'skybox/')


def dump(src, work, zr=(-300.0, 6200.0)):
    import vmapedit as V, radartex
    m = V.Map(src)
    verts, uvs, sizes, matidx, mats = [], [], [], [], {}
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        names = [x.decode().lower() for x in m.g(md, b'materials') or []]
        pos = tc = mi = None
        for st in m.g(m.g(md, b'vertexData'), b'streams') or []:
            if m.E[st]['name'].startswith(b'position'): pos = m.g(st, b'data')
        for st in m.g(m.g(md, b'faceVertexData'), b'streams') or []:
            if m.E[st]['name'].startswith(b'texcoord'): tc = m.g(st, b'data')
        for st in m.g(m.g(md, b'faceData'), b'streams') or []:
            if m.E[st]['name'].startswith(b'materialindex'): mi = m.g(st, b'data')
        fei, evi, nxt, vdi, fdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices', b'faceDataIndices'))
        if pos is None or fei is None: continue
        o = m.g(n, b'origin', [0, 0, 0]); a = m.g(n, b'angles', [0, 0, 0]); sc = m.g(n, b'scales', [1, 1, 1])
        for f, he in enumerate(fei):
            fi = fdi[f] if fdi and f < len(fdi) else f
            mat = names[mi[fi]] if mi is not None and fi < len(mi) and 0 <= mi[fi] < len(names) else ''
            if any(s in mat for s in SKIP): continue
            loop, luv, h = [], [], he
            for _ in range(256):
                p = pos[vdi[evi[h]]]; loop.append(V.xform([p[0] * sc[0], p[1] * sc[1], p[2] * sc[2]], o, a))
                luv.append(tuple(tc[h][:2]) if tc is not None else (0.0, 0.0)); h = nxt[h]
                if h == he: break
            cz = sum(q[2] for q in loop) / len(loop)
            if not (zr[0] <= cz <= zr[1]): continue
            verts += loop; uvs += luv; sizes.append(len(loop)); matidx.append(mats.setdefault(mat, len(mats)))
    names = sorted(mats, key=mats.get)
    guess = [list(radartex.guess_colour(n)) for n in names]
    os.makedirs(work, exist_ok=True)
    np.savez_compressed(os.path.join(work, 'map.npz'), verts=np.array(verts, np.float32), uvs=np.array(uvs, np.float32), sizes=np.array(sizes, np.int32),
                        matidx=np.array(matidx, np.int32))
    json.dump(dict(materials=names, guess=guess), open(os.path.join(work, 'materials.json'), 'w'))
    props, lights = [], []
    for e in m.entities():
        c = m.cls(e); o = m.origin(e)
        if not (zr[0] <= o[2] <= zr[1]): continue
        if c == 'prop_static':
            props.append(dict(model=m.P(e, 'model', ''), origin=o, angles=list(m.g(e, b'angles', [0, 0, 0])), scale=list(m.g(e, b'scales', [1, 1, 1])), tint=m.P(e, 'rendercolor', '255 255 255')))
        elif c == 'light_omni2':
            lights.append(dict(origin=o, color=m.P(e, 'color', '255 255 255'), lumens=float(m.P(e, 'brightness_lumens', '1000') or 1000), range=float(m.P(e, 'range', '512') or 512)))
    json.dump(props, open(os.path.join(work, 'props.json'), 'w')); json.dump(lights, open(os.path.join(work, 'lights.json'), 'w'))
    models = sorted(set(p['model'] for p in props if p['model']))
    open(os.path.join(work, 'models.txt'), 'w').write('\n'.join(models) + '\n')
    print('dump: %d faces, %d materials, %d props (%d models), %d lights -> %s' % (len(sizes), len(names), len(props), len(models), len(lights), work))
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] != 'dump': sys.exit(__doc__)
    zr = tuple(float(x) for x in sys.argv[4].split(',')) if len(sys.argv) > 4 else (-300.0, 6200.0)
    sys.exit(dump(sys.argv[2], sys.argv[3], zr))
