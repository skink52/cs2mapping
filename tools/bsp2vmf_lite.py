"""Minimal VMF from a CS:GO BSP, for the passes that only need brush sides and decals (texfix overlayfix / facescale),
when the BSPSource-decompiled VMF isn't at hand. Also unpacks the BSP's embedded files (pakfile lump).

python3 bsp2vmf_lite.py <map.bsp> <out.vmf> [embedded_dir]

Writes every brush (world and brush entities) as a `solid` with one `side` per non-bevel brush side: the plane as three points,
the material, and uaxis/vaxis rebuilt from the texinfo (axis = textureVec / |textureVec|, scale = 1 / |textureVec|, shift = offset),
which is exactly what BSPSource writes. Entities: every infodecal from the entity lump and every info_overlay from the overlay lump
(BasisOrigin/U/V/Normal, uv0..uv3, StartU/EndU/StartV/EndV). Nothing else (no point entities, no displacements).
"""
import struct, sys, os, re, io, zipfile, lzma

def lump(d, i):
    off, ln, ver, fourcc = struct.unpack_from('<iiii', d, 8 + 16 * i)
    raw = d[off:off + ln]
    if raw[:4] == b'LZMA':                      # CS:GO lump compression: 'LZMA' actualSize lzmaSize props[5] data
        size, = struct.unpack_from('<I', raw, 4)
        props = raw[12:17]
        dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': struct.unpack('<I', props[1:5])[0],
                                                                'lc': props[0] % 9, 'lp': (props[0] // 9) % 5, 'pb': props[0] // 45}])
        raw = dec.decompress(raw[17:], size)
    return raw

def brush_centre(pls):
    """centre of the brush's vertices (intersections of three side planes that lie inside every side), or None"""
    import itertools, numpy as np
    N = np.array([p[0] for p in pls], float); D = np.array([p[1] for p in pls], float); pts = []
    for i, j, k in itertools.combinations(range(len(pls)), 3):
        A = N[[i, j, k]]
        if abs(np.linalg.det(A)) < 1e-6: continue
        x = np.linalg.solve(A, D[[i, j, k]])
        if np.all(N @ x <= D + 0.05): pts.append(x)
    return np.mean(pts, 0).tolist() if pts else None

def plane_points(n, dist, near=None):
    n = [float(x) for x in n]
    p0 = [n[k] * dist for k in range(3)]
    if near is not None:                     # put the points on the plane next to the brush (readers take the centroid of all side points)
        t = sum(n[k] * near[k] for k in range(3)) - dist
        p0 = [near[k] - n[k] * t for k in range(3)]
    a = [0, 0, 1] if abs(n[2]) < 0.9 else [1, 0, 0]
    u = [a[1] * n[2] - a[2] * n[1], a[2] * n[0] - a[0] * n[2], a[0] * n[1] - a[1] * n[0]]
    l = sum(x * x for x in u) ** 0.5; u = [x / l * 64 for x in u]
    v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]]
    # VMF winding: (p0, p1, p2) with normal = (p2 - p0) x (p1 - p0)... texfix/vmf readers use cross(p1-p0, p2-p0) and then orient outward
    return [p0, [p0[k] + v[k] for k in range(3)], [p0[k] + u[k] for k in range(3)]]

def main(src, out, emb=None):
    d = open(src, 'rb').read()
    assert d[:4] == b'VBSP', 'not a BSP'
    planes = lump(d, 1); texdata = lump(d, 2); texinfo = lump(d, 6); brushes = lump(d, 18); sides = lump(d, 19)
    sdata = lump(d, 43); stab = lump(d, 44); ents = lump(d, 0).decode('latin-1', 'replace'); ovl = lump(d, 45)
    names = []
    for i in range(len(stab) // 4):
        o, = struct.unpack_from('<i', stab, 4 * i); e = sdata.index(b'\0', o); names.append(sdata[o:e].decode('latin-1'))
    tdname = [names[struct.unpack_from('<i', texdata, 32 * i + 12)[0]] for i in range(len(texdata) // 32)]
    def ti(i):
        v = struct.unpack_from('<8f', texinfo, 72 * i); flags, td = struct.unpack_from('<ii', texinfo, 72 * i + 64)
        return v[:4], v[4:8], (tdname[td] if 0 <= td < len(tdname) else 'TOOLS/TOOLSNODRAW')
    def axis(vec):
        l = (vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) ** 0.5 or 1.0
        return '[%g %g %g %g] %g' % (vec[0] / l, vec[1] / l, vec[2] / l, vec[3], 1.0 / l)
    o = ['world\n{\n"classname" "worldspawn"\n']
    nb = ns = 0
    for b in range(len(brushes) // 12):
        first, num, contents = struct.unpack_from('<iii', brushes, 12 * b)
        sl = []; allp = []
        for s in range(first, first + num):
            pn, tix, disp, bevel, thin = struct.unpack_from('<HhhBB', sides, 8 * s)
            allp.append((struct.unpack_from('<3f', planes, 20 * pn), struct.unpack_from('<f', planes, 20 * pn + 12)[0]))
        cen = brush_centre(allp)
        if cen is None: continue
        for s in range(first, first + num):
            pn, tix, disp, bevel, thin = struct.unpack_from('<HhhBB', sides, 8 * s)
            if bevel or tix < 0: continue
            nx, ny, nz, dist = struct.unpack_from('<4f', planes, 20 * pn)
            u, v, mat = ti(tix)
            pts = plane_points((nx, ny, nz), dist, cen)
            sl.append('side\n{\n"plane" "%s"\n"material" "%s"\n"uaxis" "%s"\n"vaxis" "%s"\n}\n'
                      % (' '.join('(%g %g %g)' % tuple(p) for p in pts), mat, axis(u), axis(v)))
        if len(sl) >= 4:
            o.append('solid\n{\n' + ''.join(sl) + '}\n'); nb += 1; ns += len(sl)
    o.append('}\n')
    nd = 0
    for blk in re.findall(r'\{([^{}]*)\}', ents):
        kv = dict(re.findall(r'"([^"]*)"\s+"([^"]*)"', blk))
        if kv.get('classname', '').lower() == 'infodecal':
            o.append('entity\n{\n' + ''.join('"%s" "%s"\n' % (k, v) for k, v in kv.items()) + '}\n'); nd += 1
    no = 0
    SZ = 352
    for i in range(len(ovl) // SZ):
        base = SZ * i
        oid, tix, fc = struct.unpack_from('<ihH', ovl, base)
        U = struct.unpack_from('<2f', ovl, base + 264); Vv = struct.unpack_from('<2f', ovl, base + 272)
        uv = [struct.unpack_from('<3f', ovl, base + 280 + 12 * k) for k in range(4)]
        org = struct.unpack_from('<3f', ovl, base + 328); nrm = struct.unpack_from('<3f', ovl, base + 340)
        u, v, mat = ti(tix)
        # BasisU / BasisV aren't stored: rebuild like vbsp (U from the normal's dominant axes, V = N x U)
        a = [0, 0, 1] if abs(nrm[2]) < 0.9 else [0, 1, 0]
        bu = [a[1] * nrm[2] - a[2] * nrm[1], a[2] * nrm[0] - a[0] * nrm[2], a[0] * nrm[1] - a[1] * nrm[0]]
        l = sum(x * x for x in bu) ** 0.5 or 1; bu = [x / l for x in bu]
        bv = [nrm[1] * bu[2] - nrm[2] * bu[1], nrm[2] * bu[0] - nrm[0] * bu[2], nrm[0] * bu[1] - nrm[1] * bu[0]]
        kv = {'classname': 'info_overlay', 'material': mat, 'origin': '%g %g %g' % org, 'BasisOrigin': '%g %g %g' % org,
              'BasisNormal': '%g %g %g' % nrm, 'BasisU': '%g %g %g' % tuple(bu), 'BasisV': '%g %g %g' % tuple(bv),
              'StartU': '%g' % U[0], 'EndU': '%g' % U[1], 'StartV': '%g' % Vv[0], 'EndV': '%g' % Vv[1]}
        for k in range(4): kv['uv%d' % k] = '%g %g %g' % uv[k]
        o.append('entity\n{\n' + ''.join('"%s" "%s"\n' % (k, v) for k, v in kv.items()) + '}\n'); no += 1
    open(out, 'w', encoding='utf-8').write(''.join(o))
    print('%s: %d brushes, %d sides, %d infodecals, %d info_overlays' % (out, nb, ns, nd, no))
    if emb:
        pak = lump(d, 40)
        with zipfile.ZipFile(io.BytesIO(pak)) as z:
            n = 0
            for zi in z.infolist():
                p = os.path.normpath(os.path.join(emb, zi.filename.lower()))
                if not p.startswith(os.path.normpath(emb)): continue
                os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(z.read(zi)); n += 1
        print('%d embedded files -> %s' % (n, emb))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
