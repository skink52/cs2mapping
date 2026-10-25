"""Minimal binary DMX (encoding 9) reader/writer, enough for Source 2 ModelDoc 'model 22' files."""
import struct, uuid
import numpy as np

# attribute type ids (binary 9)
T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_BINARY, T_TIME, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_QUAT, T_MATRIX, T_UINT64, T_UINT8 = range(1, 17)
NSINGLE = 16
AOFF = 32  # array type id = AOFF + element type id
FMT = {T_INT:'<i', T_FLOAT:'<f', T_BOOL:'<B', T_TIME:'<i', T_COLOR:'<4B', T_VEC2:'<2f', T_VEC3:'<3f', T_VEC4:'<4f', T_QANGLE:'<3f', T_QUAT:'<4f', T_MATRIX:'<16f', T_UINT64:'<Q', T_UINT8:'<B'}

class Element:
    def __init__(self, type, name, id=None):
        self.type = type; self.name = name; self.id = id or uuid.uuid4().bytes
        self.attrs = {}   # name -> (typeid, value)
    def __getitem__(self, k): return self.attrs[k][1]
    def get(self, k, d=None): return self.attrs[k][1] if k in self.attrs else d
    def set(self, k, t, v): self.attrs[k] = (t, v)
    def __repr__(self): return f'<{self.type} {self.name!r}>'

class Attr:  # array wrapper
    __slots__ = ('elem_type', 'items')
    def __init__(self, elem_type, items): self.elem_type = elem_type; self.items = items

def read(path):
    d = open(path, 'rb').read()
    h = d.index(b'\0') + 1
    header = d[:h-1].decode()
    pos = [h]
    def u(fmt):
        v = struct.unpack_from(fmt, d, pos[0]); pos[0] += struct.calcsize(fmt); return v if len(v) > 1 else v[0]
    def cstr():
        e = d.index(b'\0', pos[0]); s = d[pos[0]:e].decode('utf-8', 'replace'); pos[0] = e + 1; return s
    nprefix = u('<i'); assert nprefix == 0, nprefix
    nstr = u('<i'); strings = [cstr() for _ in range(nstr)]
    dstr = lambda: strings[u('<i')]
    nel = u('<i'); elems = []
    for _ in range(nel):
        t = dstr(); n = dstr(); eid = d[pos[0]:pos[0]+16]; pos[0] += 16
        elems.append(Element(t, n, eid))
    def rd_single(t):
        if t == T_ELEMENT:
            i = u('<i')
            if i == -1: return None
            if i == -2: return ('guid', cstr())
            return elems[i]
        if t == T_STRING: return dstr()
        if t == T_BINARY:
            n = u('<i'); b = d[pos[0]:pos[0]+n]; pos[0] += n; return b
        v = u(FMT[t]); return v
    def rd_array(t):
        n = u('<i')
        if t == T_STRING: return [cstr() for _ in range(n)]
        if t in FMT and t not in (T_BOOL, T_COLOR, T_UINT8):
            sz = struct.calcsize(FMT[t]); raw = d[pos[0]:pos[0]+n*sz]; pos[0] += n*sz
            dt = {'i':'<i4','f':'<f4','Q':'<u8'}[FMT[t][-1]]; cnt = struct.calcsize(FMT[t]) // np.dtype(dt).itemsize
            a = np.frombuffer(raw, dtype=dt); return a.reshape(n, cnt) if cnt > 1 else a.copy()
        return [rd_single(t) for _ in range(n)]
    for e in elems:
        na = u('<i')
        for _ in range(na):
            name = dstr(); t = u('<B')
            if t > AOFF: e.attrs[name] = (t, Attr(t - AOFF, rd_array(t - AOFF)))
            else: e.attrs[name] = (t, rd_single(t))
    assert pos[0] == len(d), (pos[0], len(d))
    return header, elems

def write(path, root, fmt='model 22'):
    # collect elements depth-first from root
    order = []; seen = set()
    def collect(e):
        if e is None or id(e) in seen: return
        seen.add(id(e)); order.append(e)
        for t, v in e.attrs.values():
            if t == T_ELEMENT: collect(v)
            elif t > AOFF and v.elem_type == T_ELEMENT:
                for x in v.items: collect(x)
    collect(root)
    index = {id(e): i for i, e in enumerate(order)}
    strings = {}; slist = []
    def sid(s):
        if s not in strings: strings[s] = len(slist); slist.append(s)
        return strings[s]
    for e in order:
        sid(e.type); sid(e.name)
        for k, (t, v) in e.attrs.items():
            sid(k)
            if t == T_STRING: sid(v)
    out = bytearray(f'<!-- dmx encoding binary 9 format {fmt} -->\n'.encode() + b'\0')
    out += struct.pack('<i', 0)
    out += struct.pack('<i', len(slist))
    for s in slist: out += s.encode() + b'\0'
    out += struct.pack('<i', len(order))
    for e in order: out += struct.pack('<ii', sid(e.type), sid(e.name)) + e.id
    def w_single(t, v):
        if t == T_ELEMENT: return struct.pack('<i', -1 if v is None else index[id(v)])
        if t == T_STRING: return struct.pack('<i', sid(v))
        if t == T_BINARY: return struct.pack('<i', len(v)) + bytes(v)
        f = FMT[t]
        return struct.pack(f, *v) if struct.calcsize(f) > 4 or f in ('<4B',) else struct.pack(f, v)
    for e in order:
        out += struct.pack('<i', len(e.attrs))
        for k, (t, v) in e.attrs.items():
            out += struct.pack('<iB', sid(k), t)
            if t > AOFF:
                et = v.elem_type; items = v.items
                out += struct.pack('<i', len(items))
                if et == T_STRING:
                    for s in items: out += s.encode() + b'\0'
                elif isinstance(items, np.ndarray):
                    dt = {'i':'<i4','f':'<f4','Q':'<u8'}[FMT[et][-1]]
                    out += np.ascontiguousarray(items, dtype=dt).tobytes()
                else:
                    for x in items: out += w_single(et, x)
            else:
                out += w_single(t, v)
    open(path, 'wb').write(out)

def dump(e, depth=0, seen=None, maxd=6):
    seen = seen if seen is not None else set()
    pad = '  ' * depth
    if e is None: print(pad + 'None'); return
    if id(e) in seen: print(pad + f'-> {e!r}'); return
    seen.add(id(e)); print(pad + repr(e))
    if depth >= maxd: return
    for k, (t, v) in e.attrs.items():
        if t == T_ELEMENT: print(pad + f' .{k}:'); dump(v, depth+1, seen, maxd)
        elif t > AOFF:
            if v.elem_type == T_ELEMENT:
                print(pad + f' .{k}[{len(v.items)}]:')
                for x in v.items: dump(x, depth+1, seen, maxd)
            else:
                a = v.items
                s = (f'array{a.shape}' if isinstance(a, np.ndarray) else f'list[{len(a)}] {a[:4]}')
                print(pad + f' .{k} = {s}')
        else:
            s = repr(v); print(pad + f' .{k} = {s[:80]}')
