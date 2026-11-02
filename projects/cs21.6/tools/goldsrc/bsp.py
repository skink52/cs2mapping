"""GoldSrc (Half-Life / CS 1.6) BSP v30 and WAD3 readers."""
import struct, re
import numpy as np

LUMPS = ['entities', 'planes', 'textures', 'vertices', 'visibility', 'nodes', 'texinfo', 'faces',
         'lighting', 'clipnodes', 'leaves', 'marksurfaces', 'edges', 'surfedges', 'models']

CONTENTS_EMPTY, CONTENTS_SOLID, CONTENTS_WATER, CONTENTS_SLIME, CONTENTS_LAVA, CONTENTS_SKY = -1, -2, -3, -4, -5, -6

# hull sizes (mins, maxs) for hulls 0..3
HULLS = [((0, 0, 0), (0, 0, 0)), ((-16, -16, -36), (16, 16, 36)), ((-32, -32, -32), (32, 32, 32)), ((-16, -16, -18), (16, 16, 18))]


def parse_entities(text):
    ents = []
    for block in re.findall(r'\{(.*?)\}', text, re.S):
        e = {}
        for k, v in re.findall(r'"([^"]*)"\s*"([^"]*)"', block):
            if k in e:
                # keep repeated keys (outputs in some maps) as a list under k + '#n'
                n = 1
                while f'{k}#{n}' in e: n += 1
                e[f'{k}#{n}'] = v
            else:
                e[k] = v
        ents.append(e)
    return ents


def decode_miptex(data, off=0, palette_override=None):
    """Returns (name, width, height, rgba ndarray) for a miptex at data[off:]. None if the texture isn't embedded."""
    name = data[off:off + 16].split(b'\0')[0].decode('ascii', 'replace')
    w, h = struct.unpack_from('<II', data, off + 16)
    offs = struct.unpack_from('<4I', data, off + 24)
    if offs[0] == 0:
        return name, w, h, None
    n0 = w * h
    idx = np.frombuffer(data, np.uint8, n0, off + offs[0]).reshape(h, w)
    # palette follows mip 3 and a 2-byte count
    pal_off = off + offs[3] + (w // 8) * (h // 8)
    count = struct.unpack_from('<H', data, pal_off)[0]
    pal = np.frombuffer(data, np.uint8, count * 3, pal_off + 2).reshape(count, 3)
    if count < 256:
        pal = np.vstack([pal, np.zeros((256 - count, 3), np.uint8)])
    rgb = pal[idx]
    a = np.full((h, w, 1), 255, np.uint8)
    if name.startswith('{'):
        a[idx == 255] = 0
    return name, w, h, np.concatenate([rgb, a], axis=2)


class Wad:
    def __init__(self, path):
        d = open(path, 'rb').read()
        magic, n, off = struct.unpack_from('<4sII', d, 0)
        assert magic in (b'WAD3', b'WAD2'), path
        self.data = d
        self.entries = {}
        for i in range(n):
            filepos, disksize, size, typ, comp, _p1, _p2, name = struct.unpack_from('<IIIBBBB16s', d, off + 32 * i)
            name = name.split(b'\0')[0].decode('ascii', 'replace').lower()
            self.entries[name] = (filepos, disksize, typ)

    def get(self, name):
        e = self.entries.get(name.lower())
        if not e:
            return None
        filepos, size, typ = e
        if typ == 0x43:     # miptex
            return decode_miptex(self.data, filepos)
        return None


class BSP:
    def __init__(self, path):
        d = open(path, 'rb').read()
        self.data = d
        ver = struct.unpack_from('<i', d, 0)[0]
        assert ver == 30, f'{path}: BSP version {ver}'
        self.lumps = {}
        for i, nm in enumerate(LUMPS):
            o, l = struct.unpack_from('<ii', d, 4 + 8 * i)
            self.lumps[nm] = d[o:o + l]
        L = self.lumps
        self.entities = parse_entities(L['entities'].split(b'\0')[0].decode('latin-1'))
        pl = np.frombuffer(L['planes'], np.dtype([('n', '<f4', 3), ('d', '<f4'), ('type', '<i4')]))
        self.planes = pl
        self.vertices = np.frombuffer(L['vertices'], '<f4').reshape(-1, 3).astype(np.float64)
        self.edges = np.frombuffer(L['edges'], '<u2').reshape(-1, 2)
        self.surfedges = np.frombuffer(L['surfedges'], '<i4')
        self.faces = np.frombuffer(L['faces'], np.dtype([('plane', '<u2'), ('side', '<u2'), ('firstedge', '<i4'), ('numedges', '<u2'),
                                                         ('texinfo', '<u2'), ('styles', 'u1', 4), ('lightofs', '<i4')]))
        self.texinfo = np.frombuffer(L['texinfo'], np.dtype([('s', '<f4', 4), ('t', '<f4', 4), ('miptex', '<i4'), ('flags', '<i4')]))
        self.nodes = np.frombuffer(L['nodes'], np.dtype([('plane', '<u4'), ('children', '<i2', 2), ('mins', '<i2', 3), ('maxs', '<i2', 3),
                                                         ('firstface', '<u2'), ('numfaces', '<u2')]))
        self.clipnodes = np.frombuffer(L['clipnodes'], np.dtype([('plane', '<i4'), ('children', '<i2', 2)]))
        self.leaves = np.frombuffer(L['leaves'], np.dtype([('contents', '<i4'), ('visofs', '<i4'), ('mins', '<i2', 3), ('maxs', '<i2', 3),
                                                           ('firstmark', '<u2'), ('nummark', '<u2'), ('ambient', 'u1', 4)]))
        self.marksurfaces = np.frombuffer(L['marksurfaces'], '<u2')
        self.models = np.frombuffer(L['models'], np.dtype([('mins', '<f4', 3), ('maxs', '<f4', 3), ('origin', '<f4', 3), ('headnode', '<i4', 4),
                                                           ('visleafs', '<i4'), ('firstface', '<i4'), ('numfaces', '<i4')]))
        self.lighting = L['lighting']
        # textures
        T = L['textures']
        n = struct.unpack_from('<i', T, 0)[0]
        offs = struct.unpack_from(f'<{n}i', T, 4)
        self.textures = []
        for o in offs:
            if o < 0:
                self.textures.append(('', 0, 0, None)); continue
            self.textures.append(decode_miptex(T, o))

    @property
    def worldspawn(self):
        return self.entities[0]

    def face_verts(self, fi):
        f = self.faces[fi]
        out = []
        for k in range(f['numedges']):
            se = self.surfedges[f['firstedge'] + k]
            v = self.edges[se][0] if se >= 0 else self.edges[-se][1]
            out.append(self.vertices[v])
        return np.array(out)

    def face_normal(self, fi):
        f = self.faces[fi]
        n = self.planes[f['plane']]['n'].astype(np.float64)
        return -n if f['side'] else n

    # ---------------------------------------------------------------- hull queries
    def point_contents(self, p, hull=0, model=0):
        """Contents at point p (array (...,3)) in the given hull of a model. Vectorised over points."""
        p = np.asarray(p, np.float64)
        shp = p.shape[:-1]
        P = p.reshape(-1, 3)
        node = np.full(len(P), self.models[model]['headnode'][hull], np.int64)
        if hull == 0:
            nodes, planes = self.nodes, self.planes
            active = node >= 0
            while active.any():
                idx = np.where(active)[0]
                nd = nodes[node[idx]]
                pl = planes[nd['plane']]
                dist = np.einsum('ij,ij->i', P[idx], pl['n'].astype(np.float64)) - pl['d']
                child = np.where(dist >= 0, nd['children'][:, 0], nd['children'][:, 1]).astype(np.int64)
                node[idx] = child
                active = node >= 0
            res = self.leaves['contents'][-node - 1]
        else:
            cn, planes = self.clipnodes, self.planes
            active = node >= 0
            while active.any():
                idx = np.where(active)[0]
                nd = cn[node[idx]]
                pl = planes[nd['plane']]
                dist = np.einsum('ij,ij->i', P[idx], pl['n'].astype(np.float64)) - pl['d']
                child = np.where(dist >= 0, nd['children'][:, 0], nd['children'][:, 1]).astype(np.int64)
                node[idx] = child
                active = node >= 0
            res = node      # clipnode leaves store contents directly (negative)
        return np.asarray(res).reshape(shp)

    def light_samples(self, fi):
        """Lightmap for face fi as (h, w, 3) uint8 for style 0 plus the texture-space mins (in 16-unit texels). None if unlit."""
        f = self.faces[fi]
        if f['lightofs'] < 0 or f['styles'][0] == 255:
            return None
        ti = self.texinfo[f['texinfo']]
        V = self.face_verts(fi)
        s = V @ ti['s'][:3].astype(np.float64) + ti['s'][3]
        t = V @ ti['t'][:3].astype(np.float64) + ti['t'][3]
        smin, smax = np.floor(s.min() / 16), np.ceil(s.max() / 16)
        tmin, tmax = np.floor(t.min() / 16), np.ceil(t.max() / 16)
        w, h = int(smax - smin) + 1, int(tmax - tmin) + 1
        o = f['lightofs']
        arr = np.frombuffer(self.lighting, np.uint8, w * h * 3, o).reshape(h, w, 3)
        return arr, (smin, tmin)
