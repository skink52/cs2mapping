"""GoldSrc studio model (.mdl version 10) reader: bones, textures, meshes in the reference pose.

Vertices are stored relative to their bone; the reference pose is the bones' default values. Each vertex follows one bone.
"""
import struct
import numpy as np


def quat_from_angles(a):
    """GoldSrc AngleQuaternion: a = (roll about X, pitch about Y, yaw about Z), radians"""
    sy, cy = np.sin(a[2] * 0.5), np.cos(a[2] * 0.5)
    sp, cp = np.sin(a[1] * 0.5), np.cos(a[1] * 0.5)
    sr, cr = np.sin(a[0] * 0.5), np.cos(a[0] * 0.5)
    return np.array([sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy])


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class MDL:
    def __init__(self, path):
        d = self.d = open(path, 'rb').read()
        ident, ver = struct.unpack_from('<4si', d, 0)
        assert ident == b'IDST' and ver == 10, (path, ident, ver)
        self.name = d[8:72].split(b'\0')[0].decode('latin-1')
        o = 72 + 4 + 12 * 5 + 4
        (nbones, boneidx, nbc, bcidx, nhb, hbidx, nseq, seqidx, nsg, sgidx, ntex, texidx, texdata,
         nskinref, nskinfam, skinidx, nbp, bpidx, natt, attidx) = struct.unpack_from('<20i', d, o)
        # bones
        self.bones = []
        for i in range(nbones):
            b = boneidx + i * 112
            name = d[b:b + 32].split(b'\0')[0].decode('latin-1')
            parent, flags = struct.unpack_from('<ii', d, b + 32)
            value = struct.unpack_from('<6f', d, b + 64)
            self.bones.append({'name': name, 'parent': parent, 'pos': np.array(value[:3]), 'rot': np.array(value[3:])})
        # reference pose: bone -> world (rotation, translation)
        self.R, self.T = [], []
        for b in self.bones:
            r = quat_mat(quat_from_angles(b['rot']))
            if b['parent'] < 0: self.R.append(r); self.T.append(b['pos'].copy())
            else:
                pr, pt = self.R[b['parent']], self.T[b['parent']]
                self.R.append(pr @ r); self.T.append(pr @ b['pos'] + pt)
        # textures (8-bit with a 256-colour palette after the pixels)
        self.textures = []
        for i in range(ntex):
            t = texidx + i * 80
            name = d[t:t + 64].split(b'\0')[0].decode('latin-1')
            flags, w, h, index = struct.unpack_from('<4i', d, t + 64)
            pix = np.frombuffer(d, np.uint8, w * h, index).reshape(h, w)
            pal = np.frombuffer(d, np.uint8, 768, index + w * h).reshape(256, 3)
            self.textures.append({'name': name, 'flags': flags, 'w': w, 'h': h, 'pix': pix, 'pal': pal})
        self.skinref = list(struct.unpack_from('<%dh' % nskinref, d, skinidx)) if nskinref else []
        # body parts -> models -> meshes (triangle strips and fans)
        self.bodyparts = []
        for i in range(nbp):
            p = bpidx + i * 76
            bpname = d[p:p + 64].split(b'\0')[0].decode('latin-1')
            nmodels, base, modelidx = struct.unpack_from('<3i', d, p + 64)
            models = []
            for m in range(nmodels):
                mo = modelidx + m * 112
                mname = d[mo:mo + 64].split(b'\0')[0].decode('latin-1')
                (mtype, rad, nmesh, meshidx, nverts, vinfo, vidx, nnorms, ninfo, nidx, ngroups, gidx) = struct.unpack_from('<ifiiiiiiiiii', d, mo + 64)
                vbone = np.frombuffer(d, np.uint8, nverts, vinfo)
                verts = np.frombuffer(d, np.float32, nverts * 3, vidx).reshape(-1, 3).astype(np.float64)
                nbone = np.frombuffer(d, np.uint8, nnorms, ninfo)
                norms = np.frombuffer(d, np.float32, nnorms * 3, nidx).reshape(-1, 3).astype(np.float64)
                meshes = []
                for k in range(nmesh):
                    numtris, triidx, skin, _, _ = struct.unpack_from('<5i', d, meshidx + k * 20)
                    tris = []          # (vertex, normal, s, t) x 3
                    q = triidx
                    while True:
                        cnt = struct.unpack_from('<h', d, q)[0]; q += 2
                        if cnt == 0: break
                        fan = cnt < 0; cnt = abs(cnt)
                        pts = [struct.unpack_from('<4h', d, q + j * 8) for j in range(cnt)]
                        q += cnt * 8
                        for j in range(2, cnt):
                            if fan: tri = (pts[0], pts[j - 1], pts[j])
                            elif j % 2: tri = (pts[j - 1], pts[j - 2], pts[j])
                            else: tri = (pts[j - 2], pts[j - 1], pts[j])
                            tris.append(tri)
                    meshes.append({'skin': skin, 'tris': tris})
                models.append({'name': mname, 'vbone': vbone, 'verts': verts, 'nbone': nbone, 'norms': norms, 'meshes': meshes})
            self.bodyparts.append({'name': bpname, 'models': models})

    def world(self, model):
        """reference-pose positions and normals of a model's vertices"""
        R, T = self.R, self.T
        V = np.array([R[b] @ v + T[b] for b, v in zip(model['vbone'], model['verts'])])
        N = np.array([R[b] @ n for b, n in zip(model['nbone'], model['norms'])])
        return V, N

    def texture_rgba(self, i):
        t = self.textures[i]
        rgb = t['pal'][t['pix']]
        a = np.full(t['pix'].shape, 255, np.uint8)
        if t['flags'] & 0x40: a[t['pix'] == 255] = 0          # masked: the last palette colour is see-through
        return np.dstack([rgb, a])
