"""Binary FBX node-tree reader (used by fbxmesh.py).  python3 fbxparse.py <file.fbx> dumps the top of the node tree."""
import struct, zlib, sys, json
import numpy as np

class Node:
    __slots__ = ('name', 'props', 'children')
    def __init__(self, name, props):
        self.name = name; self.props = props; self.children = []
    def find(self, name):
        return [c for c in self.children if c.name == name]
    def first(self, name):
        for c in self.children:
            if c.name == name: return c
        return None
    def prop70(self, pname):
        p70 = self.first('Properties70')
        if not p70: return None
        for p in p70.find('P'):
            if p.props[0] == pname: return p.props[4:]
        return None

def read_fbx(path):
    d = open(path, 'rb').read()
    assert d[:21] == b'Kaydara FBX Binary  \x00', 'not a binary FBX'
    ver = struct.unpack_from('<I', d, 23)[0]
    big = ver >= 7500
    off = 27
    def rd_node(off):
        if big:
            end, nprops, plen = struct.unpack_from('<QQQ', d, off); off += 24
        else:
            end, nprops, plen = struct.unpack_from('<III', d, off); off += 12
        nlen = d[off]; off += 1
        if end == 0: return None, off
        name = d[off:off+nlen].decode('latin1'); off += nlen
        props = []
        for _ in range(nprops):
            t = chr(d[off]); off += 1
            if t in 'YCIFDL':
                fmt = {'Y':'<h','C':'<?','I':'<i','F':'<f','D':'<d','L':'<q'}[t]
                props.append(struct.unpack_from(fmt, d, off)[0]); off += struct.calcsize(fmt)
            elif t in 'fdlib':
                n, enc, clen = struct.unpack_from('<III', d, off); off += 12
                dt = {'f':'<f4','d':'<f8','l':'<i8','i':'<i4','b':'<u1'}[t]
                if enc == 0:
                    sz = n*np.dtype(dt).itemsize; raw = d[off:off+sz]; off += sz
                else:
                    raw = zlib.decompress(d[off:off+clen]); off += clen
                props.append(np.frombuffer(raw, dtype=dt).copy())
            elif t in 'SR':
                n = struct.unpack_from('<I', d, off)[0]; off += 4
                raw = d[off:off+n]; off += n
                props.append(raw.decode('latin1') if t == 'S' else raw)
            else:
                raise ValueError('unknown prop type %r at %d' % (t, off))
        node = Node(name, props)
        while off < end:
            c, off = rd_node(off)
            if c is None: break
            node.children.append(c)
        return node, end
    root = Node('ROOT', [])
    while off < len(d):
        n, off = rd_node(off)
        if n is None: break
        root.children.append(n)
        if off + 13 > len(d) or d[off:off+13] == b'\x00'*13 and root.children and root.children[-1].name == 'Takes':
            pass
    return root, ver

def dump(n, depth=0, maxd=3, out=None):
    out = out if out is not None else []
    if depth > maxd: return out
    ps = []
    for p in n.props:
        if isinstance(p, np.ndarray): ps.append('<%s[%d]>' % (p.dtype, len(p)))
        elif isinstance(p, (bytes, bytearray)): ps.append('<raw %d>' % len(p))
        else: ps.append(repr(p)[:60])
    out.append('  '*depth + n.name + ' ' + ', '.join(ps))
    for c in n.children: dump(c, depth+1, maxd, out)
    return out

if __name__ == '__main__':
    root, ver = read_fbx(sys.argv[1])
    print('version', ver)
    for c in root.children:
        print(c.name, len(c.children))
    gs = root.first('GlobalSettings')
    if gs:
        for p in gs.first('Properties70').find('P'):
            print('  GS', p.props[0], p.props[4:])
    objs = root.first('Objects')
    for o in objs.children:
        print(o.name, [repr(p)[:50] if not isinstance(p, np.ndarray) else '<%s[%d]>' % (p.dtype, len(p)) for p in o.props])
        if o.name == 'Model':
            for pn in ['Lcl Translation','Lcl Rotation','Lcl Scaling','PreRotation','PostRotation','RotationOffset','RotationPivot','ScalingOffset','ScalingPivot','GeometricTranslation','GeometricRotation','GeometricScaling','RotationOrder','InheritType']:
                v = o.prop70(pn)
                if v is not None: print('    ', pn, v)
        if o.name == 'Geometry':
            for c in o.children:
                print('    ', '\n     '.join(dump(c, 0, 1)))
        if o.name in ('Material', 'Texture', 'Video'):
            print('\n'.join('    ' + l for l in dump(o, 0, 2)[1:]))
    con = root.first('Connections')
    for c in con.children:
        print('CONN', c.props)
