"""Source 1 (CS:GO) model -> LOD0 triangles: .mdl (materials, meshes), .vvd (vertices), .dx90.vtx (indices).

mesh(mdl_bytes, vvd_bytes, vtx_bytes, skin=0) -> list of (material_path, Nx3x3 float array of triangles, model units)
material_path is the cdtexture dir + texture name ("models/props/agarden/roof/roof_a_lod"), without "materials/" or ".vmt".
Used by radar_props.py to draw props on radars. Static props only (bone weights ignored; vertices are in model space)."""
import struct
import numpy as np

def _cstr(b, o):
    e = b.index(b'\0', o); return b[o:e].decode('latin1')

def materials(mdl, skin=0):
    u = lambda o: struct.unpack_from('<i', mdl, o)[0]
    numtex, texidx, numcd, cdidx, numref, numfam, skinidx = (u(204), u(208), u(212), u(216), u(220), u(224), u(228))
    names = [_cstr(mdl, texidx + i * 64 + u(texidx + i * 64)) for i in range(numtex)]
    cds = [_cstr(mdl, u(cdidx + i * 4)).replace('\\', '/').strip('/') for i in range(numcd)]
    fam = min(skin, max(numfam - 1, 0))
    table = [struct.unpack_from('<h', mdl, skinidx + (fam * numref + i) * 2)[0] for i in range(numref)] if numref else list(range(numtex))
    return names, cds, table

def _vertices(vvd):
    ident, ver, chk, nlod = struct.unpack_from('<4siii', vvd, 0)
    nlodv = struct.unpack_from('<8i', vvd, 16)
    nfix, fixstart, vstart, tstart = struct.unpack_from('<4i', vvd, 48)
    n = nlodv[0]
    def block(start, count): return np.frombuffer(vvd, np.float32, count * 12, vstart + start * 48).reshape(count, 12)[:, 4:7]
    if nfix == 0: return block(0, n).copy()
    out = []
    for i in range(nfix):
        lod, src, cnt = struct.unpack_from('<3i', vvd, fixstart + i * 12)
        if lod >= 0: out.append(block(src, cnt))
    return np.concatenate(out) if out else np.zeros((0, 3), np.float32)

def mesh(mdl, vvd, vtx, skin=0):
    u = lambda o: struct.unpack_from('<i', mdl, o)[0]
    names, cds, table = materials(mdl, skin)
    def matpath(idx):
        t = names[table[idx] if idx < len(table) else idx] if names else ''
        for cd in cds or ['']:
            return ((cd + '/') if cd else '') + t.replace('\\', '/')
        return t
    V = _vertices(vvd)
    nbp, bpidx = u(232), u(236)
    v = lambda o: struct.unpack_from('<i', vtx, o)[0]
    vtx_nbp, vtx_bp = v(28), v(32)
    # strip group header size: 25 (old) or 33 (CS:GO adds topology fields); detect on first use
    sg_size = None
    out = []
    for b in range(min(nbp, vtx_nbp)):
        mbp = bpidx + b * 16
        nmodels, modelidx = u(mbp + 4), u(mbp + 12)
        xbp = vtx_bp + b * 8
        x_nmodels, x_modoff = v(xbp), v(xbp + 4)
        if nmodels == 0: continue
        mm = mbp + modelidx                        # first model of the body part (default body group)
        nmeshes, meshidx, vindex = u(mm + 72), u(mm + 76), u(mm + 84)
        base = vindex // 48
        xm = xbp + x_modoff
        nlods, lodoff = v(xm), v(xm + 4)
        xl = xm + lodoff
        xnmesh, xmeshoff = v(xl), v(xl + 4)
        for k in range(min(nmeshes, xnmesh)):
            me = mm + meshidx + k * 116
            mat, vofs = u(me), u(me + 12)
            xmh = xl + xmeshoff + k * 9
            nsg, sgoff = v(xmh), v(xmh + 4)
            tris = []
            for g in range(nsg):
                for size in ([sg_size] if sg_size else [33, 25]):
                    sg = xmh + sgoff + g * size
                    nv, voff, ni, ioff = struct.unpack_from('<4i', vtx, sg)
                    if nv < 0 or ni < 0 or sg + ioff + ni * 2 > len(vtx) or sg + voff + nv * 9 > len(vtx): continue
                    ids = np.frombuffer(vtx, np.uint16, ni, sg + ioff).astype(np.int64)
                    if ni and ids.max() >= nv: continue
                    orig = np.array([struct.unpack_from('<H', vtx, sg + voff + i * 9 + 4)[0] for i in range(nv)], np.int64)
                    gi = base + vofs + orig[ids]
                    if len(gi) and gi.max() >= len(V): continue
                    sg_size = size
                    tris.append(V[gi].reshape(-1, 3, 3))
                    break
            if tris: out.append((matpath(mat), np.concatenate(tris)))
    return out
