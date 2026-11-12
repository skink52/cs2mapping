"""read a CS2 .nav (v36) far enough for area polygons: corners, then per polygon u8 n, n x u32 corner index, i32 (-1).
Header layout found empirically on mg_trenchwarfare (12 Nov 2026): corner count u32 at 0x91. Reads only."""
import struct, sys, json
import numpy as np

def read(path):
    d = open(path, 'rb').read()
    assert struct.unpack_from('<I', d, 0)[0] == 0xFEEDFACE
    ver = struct.unpack_from('<I', d, 4)[0]
    # find the corner table: a u32 count followed by count*12 bytes of floats then a u32 polygon count; search the header
    for off in range(0x40, 0x200):
        n = struct.unpack_from('<I', d, off)[0]
        if not 3 <= n < 2_000_000 or off + 4 + n * 12 + 4 > len(d): continue
        p = off + 4 + n * 12
        npoly = struct.unpack_from('<I', d, p)[0]
        if not 1 <= npoly <= n * 4: continue
        V = np.frombuffer(d[off + 4:p], dtype='<f4').reshape(-1, 3)
        if not np.all(np.isfinite(V)) or np.abs(V).max() > 65536: continue
        q = p + 4; polys = []; ok = True
        for i in range(npoly):
            k = d[q]; q += 1
            if not 3 <= k <= 64: ok = False; break
            idx = struct.unpack_from('<%dI' % k, d, q); q += 4 * k
            if max(idx) >= n: ok = False; break
            q += 4
            polys.append(idx)
        if ok: return ver, V, polys
    raise SystemExit('corner table not found')

def areas(path):
    ver, V, polys = read(path)
    out = []
    for idx in polys:
        P = V[list(idx)]
        x, y = P[:, 0], P[:, 1]
        a = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        out.append((float(P[:, 0].mean()), float(P[:, 1].mean()), float(P[:, 2].mean()), float(a)))
    return ver, np.array(out)

if __name__ == '__main__':
    ver, A = areas(sys.argv[1])
    print('version', ver, 'areas', len(A), 'total m2 %.0f' % (A[:, 3].sum() * 0.0254 ** 2))
