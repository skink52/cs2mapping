"""Source 1 studio models (MDL v44-49 + VVD + VTX, as Garry's Mod / HL2 / CS:S ship them): reference-pose skeleton and
LOD0 skinned mesh, read with numpy only.

    m = SrcModel('models/player/foo.mdl')
    m.bones      [{'name', 'parent', 'world' (3x4 reference-pose bone->model matrix)}]
    m.textures   texture names; m.cdtextures search folders; m.skins [[texture index per skinref], ...]
    m.parts      [{'name', 'models': [{'name', 'meshes': [{'material' (skinref), 'tris' (k,3) global vertex ids,
                   'eyeball' (index or -1)}]}]}]
    m.V, m.N, m.UV   LOD0 vertex positions / normals / uvs (model space, v from the top)
    m.W, m.B         (n,3) bone weights and bone indices
    m.eyeballs   [{'bone', 'org', 'radius', 'up', 'forward', 'iris_scale', 'texture'}]

python3 -I srcmdl.py <model.mdl> prints a summary (bones, parts, materials, height).
"""
import os, struct, sys
import numpy as np

VVD_VERTEX = np.dtype([('w', '<f4', 3), ('b', 'u1', 3), ('nb', 'u1'), ('p', '<f4', 3), ('n', '<f4', 3), ('uv', '<f4', 2)])


def _str(data, off):
    e = data.index(b'\0', off)
    return data[off:e].decode('latin-1')


class SrcModel:
    def __init__(self, path):
        self.path = path
        d = self.data = open(path, 'rb').read()
        if d[:4] != b'IDST': raise ValueError('%s: not a Source MDL' % path)
        self.version, self.checksum = struct.unpack_from('<ii', d, 4)
        if not 44 <= self.version <= 49: raise ValueError('%s: MDL version %d not supported (44-49)' % (path, self.version))
        self.name = d[12:76].split(b'\0')[0].decode('latin-1')
        (self.flags, nb, bi) = struct.unpack_from('<i ii', d, 152)
        ntex, ti, ncd, cdi, nskinref, nfam, si, nbp, bpi = struct.unpack_from('<ii ii iii ii', d, 204)
        # bones
        self.bones = []
        for k in range(nb):
            o = bi + k * 216
            name = _str(d, o + struct.unpack_from('<i', d, o)[0])
            parent, = struct.unpack_from('<i', d, o + 4)
            p2b = np.array(struct.unpack_from('<12f', d, o + 96)).reshape(3, 4)
            R = p2b[:, :3].T; t = -R @ p2b[:, 3]                 # inverse of poseToBone = bone -> model
            self.bones.append({'name': name, 'parent': parent, 'world': np.hstack([R, t[:, None]])})
        self.textures = []
        for k in range(ntex):
            o = ti + k * 64
            self.textures.append(_str(d, o + struct.unpack_from('<i', d, o)[0]).replace('\\', '/'))
        self.cdtextures = [_str(d, struct.unpack_from('<i', d, cdi + 4 * k)[0]).replace('\\', '/') for k in range(ncd)]
        self.skins = [list(struct.unpack_from('<%dh' % nskinref, d, si + 2 * nskinref * f)) for f in range(nfam)]
        # body parts -> models -> meshes (the VVD/VTX supply the vertices and triangles)
        self.parts = []
        self.eyeballs = []
        for k in range(nbp):
            o = bpi + k * 16
            ni, nm, base, mi = struct.unpack_from('<iiii', d, o)
            part = {'name': _str(d, o + ni), 'models': []}
            for j in range(nm):
                mo = o + mi + j * 148
                mname = d[mo:mo + 64].split(b'\0')[0].decode('latin-1')
                nmesh, meshi, nverts, vidx = struct.unpack_from('<iiii', d, mo + 72)
                neye, eyei = struct.unpack_from('<ii', d, mo + 100)
                eye_base = len(self.eyeballs)
                for e in range(neye):
                    eo = mo + eyei + e * 172
                    bone, = struct.unpack_from('<i', d, eo + 4)
                    org = np.array(struct.unpack_from('<3f', d, eo + 8)); zoff, rad = struct.unpack_from('<2f', d, eo + 20)
                    up = np.array(struct.unpack_from('<3f', d, eo + 28)); fwd = np.array(struct.unpack_from('<3f', d, eo + 40))
                    tex, _, iris = struct.unpack_from('<iif', d, eo + 52)
                    self.eyeballs.append({'bone': bone, 'org': org, 'radius': rad, 'up': up, 'forward': fwd, 'iris_scale': iris, 'texture': tex})
                meshes = []
                for q in range(nmesh):
                    me = mo + meshi + q * 116
                    mat, _, mnv, voff = struct.unpack_from('<iiii', d, me)
                    mtype, mparam = struct.unpack_from('<ii', d, me + 24)
                    meshes.append({'material': mat, 'nverts': mnv, 'voff': voff, 'eyeball': eye_base + mparam if mtype == 1 else -1})
                part['models'].append({'name': mname, 'vstart': vidx // 48, 'nverts': nverts, 'meshes': meshes})
            self.parts.append(part)
        self._read_vvd()
        self._read_vtx()

    # ------------------------------------------------------------ files next to the .mdl
    def _sibling(self, *exts):
        base = self.path[:-4]
        for e in exts:
            for cand in (base + e, base + e.upper()):
                if os.path.exists(cand): return cand
        raise FileNotFoundError('%s: no %s next to it' % (self.path, ' / '.join(exts)))

    def _read_vvd(self):
        d = open(self._sibling('.vvd'), 'rb').read()
        if d[:4] != b'IDSV': raise ValueError('bad VVD')
        ver, chk, nlod = struct.unpack_from('<iii', d, 4)
        nlodv = struct.unpack_from('<8i', d, 16)
        nfix, fixi, vdi, tdi = struct.unpack_from('<iiii', d, 48)
        allv = np.frombuffer(d, VVD_VERTEX, nlodv[0] if nfix == 0 else (tdi - vdi) // 48, vdi)
        if nfix:
            idx = []
            for k in range(nfix):
                lod, src, num = struct.unpack_from('<iii', d, fixi + 12 * k)
                if lod >= 0: idx.extend(range(src, src + num))
            allv = allv[np.array(idx, int)]
        self.V = allv['p'].astype(float); self.N = allv['n'].astype(float); self.UV = allv['uv'].astype(float)
        self.W = allv['w'].astype(float); self.B = allv['b'].astype(int); nbw = allv['nb'].astype(int)
        for k in range(3): self.W[nbw <= k, k] = 0.0
        s = self.W.sum(1, keepdims=True); s[s == 0] = 1; self.W /= s

    def _read_vtx(self):
        path = self._sibling('.dx90.vtx', '.dx80.vtx', '.sw.vtx', '.vtx')
        d = open(path, 'rb').read()
        ver, = struct.unpack_from('<i', d, 0)
        nbp, bpo = struct.unpack_from('<ii', d, 28)
        # strip group / strip headers grew in later compilers (topology fields): detect by checking index sanity
        for sg_size, st_size in ((25, 27), (33, 35)):
            try:
                self._vtx_parse(d, nbp, bpo, sg_size, st_size); return
            except (ValueError, struct.error, IndexError):
                continue
        raise ValueError('%s: could not read the VTX' % path)

    def _vtx_parse(self, d, nbp, bpo, SG, ST):
        nV = len(self.V)
        result = []
        for k in range(nbp):
            o = bpo + 8 * k
            nm, mo = struct.unpack_from('<ii', d, o)
            part = self.parts[k]
            if nm != len(part['models']): raise ValueError('model count')
            out_models = []
            for j in range(nm):
                m = o + mo + 8 * j
                nlod, lo = struct.unpack_from('<ii', d, m)
                l = m + lo                                   # LOD 0
                nmesh, mesho, _ = struct.unpack_from('<iif', d, l)
                mdl_model = part['models'][j]
                if nmesh != len(mdl_model['meshes']): raise ValueError('mesh count')
                tris_per_mesh = []
                for q in range(nmesh):
                    me = l + mesho + 9 * q
                    nsg, sgo = struct.unpack_from('<ii', d, me)
                    mesh = mdl_model['meshes'][q]
                    tris = []
                    for g in range(nsg):
                        so = me + sgo + SG * g
                        nv, vo, ni, io_, nst, sto = struct.unpack_from('<6i', d, so)
                        verts = np.frombuffer(d, np.dtype([('bw', 'u1', 3), ('nb', 'u1'), ('orig', '<u2'), ('bid', 'i1', 3)]), nv, so + vo)
                        idx = np.frombuffer(d, '<u2', ni, so + io_).astype(int)
                        if ni and idx.max() >= nv: raise ValueError('index range')
                        gv = mdl_model['vstart'] + mesh['voff'] + verts['orig'].astype(int)
                        if nv and gv.max() >= nV: raise ValueError('vertex range')
                        for s in range(nst):
                            sh = so + sto + ST * s
                            sni, sio, snv, svo = struct.unpack_from('<4i', d, sh)
                            flags = d[sh + 18]
                            sidx = idx[sio:sio + sni]
                            if flags & 2:        # triangle strip
                                t = [(sidx[i], sidx[i + 1], sidx[i + 2]) if i % 2 == 0 else (sidx[i + 1], sidx[i], sidx[i + 2]) for i in range(len(sidx) - 2)]
                                t = np.array([x for x in t if len(set(x)) == 3], int).reshape(-1, 3)
                            else:
                                t = sidx[:len(sidx) // 3 * 3].reshape(-1, 3)
                            if len(t): tris.append(gv[t])
                    tris_per_mesh.append(np.vstack(tris) if tris else np.zeros((0, 3), int))
                out_models.append(tris_per_mesh)
            result.append(out_models)
        for k, part in enumerate(self.parts):
            for j, mdl_model in enumerate(part['models']):
                for q, mesh in enumerate(mdl_model['meshes']):
                    # Source winds triangles clockwise seen from the front: flip to counter-clockwise
                    mesh['tris'] = result[k][j][q][:, [0, 2, 1]]

    # ------------------------------------------------------------ helpers
    def bone_index(self, name):
        for i, b in enumerate(self.bones):
            if b['name'].lower() == name.lower(): return i
        return -1

    def default_meshes(self, choices=None):
        """meshes of each body part's chosen model (default: model 0, as in the game: a blank model 0 means the part is off -
        hats, party props and shields in later slots stay off unless chosen)"""
        out = []
        for k, part in enumerate(self.parts):
            ms = part['models']
            j = (choices or {}).get(part['name'], 0)
            if not 0 <= j < len(ms) or ms[j]['nverts'] == 0: continue
            out += ms[j]['meshes']
        return out


if __name__ == '__main__':
    m = SrcModel(sys.argv[1])
    print('%s  v%d  %d bones, %d vertices, %d skins' % (m.name, m.version, len(m.bones), len(m.V), len(m.skins)))
    print('textures:', m.textures, 'cd:', m.cdtextures)
    for p in m.parts:
        print('part %-20s' % p['name'], [(mo['name'], mo['nverts'], sum(len(x['tris']) for x in mo['meshes'])) for mo in p['models']])
    z = m.V[:, 2]; print('height %.1f (z %.1f..%.1f)' % (z.max() - z.min(), z.min(), z.max()))
    print('bones:', ' '.join(b['name'] for b in m.bones))
