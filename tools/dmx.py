"""Binary DMX (encoding version 9: Hammer .vmap, ModelDoc 'model 22' meshes) reader/writer, three APIs over one format.

DMX.load(path) / .save(path): lossless object API (Element objects, str strings, resolved references); load() + save()
  reproduces the original bytes. Elements keep their attribute order, the string table keeps its order (new strings are appended).
load(path) / loads(data) -> Doc, dumps(doc), get / geta / set_ / delete: dict elements with bytes strings, int element
  references (index into doc.elements, -1 = null, ('guid', bytes) external); T_ELEM, T_STR, T_V3, ..., ARR names.
read(path) -> (header, [ModelElement]), write(path, root, fmt='model 22'), dump(e): ModelDoc mesh API, attrs as
  {name: (type, value)}, arrays as Attr (numeric arrays are numpy); AOFF, T_UINT8 names. numpy is only imported here.
"""
import struct, uuid

T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_BINARY, T_TIME, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_QUAT, T_MATRIX, T_UINT64, T_BYTE = range(1, 17)
ARRAY = 32
FIXED = {T_INT: '<i', T_FLOAT: '<f', T_BOOL: '<B', T_TIME: '<i', T_COLOR: '<4B', T_VEC2: '<2f', T_VEC3: '<3f',
         T_VEC4: '<4f', T_QANGLE: '<3f', T_QUAT: '<4f', T_MATRIX: '<16f', T_UINT64: '<Q', T_BYTE: '<B'}


class Element:
    __slots__ = ('type', 'name', 'guid', 'attrs', 'index')
    def __init__(self, type_, name, guid=None):
        self.type = type_; self.name = name
        self.guid = guid or uuid.uuid4().bytes
        self.attrs = []   # list of [name, type, value]
        self.index = -1
    def get(self, name, default=None):
        for a in self.attrs:
            if a[0] == name: return a[2]
        return default
    def attr(self, name):
        for a in self.attrs:
            if a[0] == name: return a
        return None
    def set(self, name, type_, value):
        a = self.attr(name)
        if a: a[1] = type_; a[2] = value
        else: self.attrs.append([name, type_, value])
    def __repr__(self): return '<%s %s>' % (self.type, self.name)


class Reader:
    def __init__(self, data):
        self.d = data; self.i = 0
    def i32(self):
        v = struct.unpack_from('<i', self.d, self.i)[0]; self.i += 4; return v
    def cstr(self):
        j = self.d.index(b'\0', self.i); s = self.d[self.i:j]; self.i = j + 1; return s.decode('utf-8', 'surrogateescape')
    def raw(self, n):
        v = self.d[self.i:self.i + n]; self.i += n; return v


class DMX:
    def __init__(self):
        self.header = ''
        self.prefix = []      # list of attribute lists (inline strings)
        self.strings = []
        self.elements = []

    # ------------------------------------------------------------ load
    @classmethod
    def load(cls, path):
        data = open(path, 'rb').read()
        self = cls()
        r = Reader(data)
        nl = data.index(b'\n')
        self.header = data[:nl + 1].decode()
        r.i = nl + 1
        assert data[r.i] == 0; r.i += 1
        npre = r.i32()
        for _ in range(npre):
            attrs = []
            for _ in range(r.i32()):
                name = r.cstr(); t = r.raw(1)[0]
                attrs.append([name, t, self._value(r, t, inline=True)])
            self.prefix.append(attrs)
        self.strings = [r.cstr() for _ in range(r.i32())]
        n = r.i32()
        for _ in range(n):
            t = self.strings[r.i32()]; name = self.strings[r.i32()]; guid = r.raw(16)
            e = Element(t, name, guid); e.index = len(self.elements); self.elements.append(e)
        for e in self.elements:
            for _ in range(r.i32()):
                name = self.strings[r.i32()]; t = r.raw(1)[0]
                e.attrs.append([name, t, self._value(r, t)])
        assert r.i == len(data), (r.i, len(data))
        # resolve element references
        for e in self.elements:
            for a in e.attrs:
                if a[1] == T_ELEMENT: a[2] = self._ref(a[2])
                elif a[1] == T_ELEMENT + ARRAY: a[2] = [self._ref(x) for x in a[2]]
        self.root = self.elements[0]
        return self

    def _ref(self, idx):
        if idx == -1: return None
        if idx == -2: raise ValueError('external element reference')
        return self.elements[idx]

    def _value(self, r, t, inline=False):
        if t & ARRAY:
            bt = t - ARRAY
            n = r.i32()
            return [self._scalar(r, bt, inline=True) for _ in range(n)]
        return self._scalar(r, t, inline)

    def _scalar(self, r, t, inline=False):
        if t == T_ELEMENT:
            return r.i32()
        if t == T_STRING:
            return r.cstr() if inline else self.strings[r.i32()]
        if t == T_BINARY:
            return r.raw(r.i32())
        fmt = FIXED[t]
        v = struct.unpack_from(fmt, r.d, r.i); r.i += struct.calcsize(fmt)
        return v[0] if len(v) == 1 else v

    # ------------------------------------------------------------ save
    def save(self, path):
        # gather every element reachable from the root, keeping existing order first
        order = []; seen = set()
        def visit(e):
            if e is None or id(e) in seen: return
            seen.add(id(e)); order.append(e)
        for e in self.elements: visit(e)
        stack = list(self.elements)
        while stack:
            e = stack.pop()
            for a in e.attrs:
                vals = a[2] if a[1] == T_ELEMENT + ARRAY else ([a[2]] if a[1] == T_ELEMENT else [])
                for x in vals:
                    if x is not None and id(x) not in seen:
                        visit(x); stack.append(x)
        self.elements = order
        for k, e in enumerate(order): e.index = k
        sidx = {s: k for k, s in enumerate(self.strings)}
        def S(s):
            if s not in sidx: sidx[s] = len(self.strings); self.strings.append(s)
            return sidx[s]
        # strings used by element headers and attribute names / string values
        for e in order:
            S(e.type); S(e.name)
            for a in e.attrs:
                S(a[0])
                if a[1] == T_STRING: S(a[2])
        out = bytearray()
        out += self.header.encode() + b'\0'
        out += struct.pack('<i', len(self.prefix))
        for attrs in self.prefix:
            out += struct.pack('<i', len(attrs))
            for name, t, v in attrs:
                out += name.encode('utf-8', 'surrogateescape') + b'\0' + bytes([t])
                out += self._enc(t, v, None, inline=True)
        out += struct.pack('<i', len(self.strings))
        for s in self.strings: out += s.encode('utf-8', 'surrogateescape') + b'\0'
        out += struct.pack('<i', len(order))
        for e in order:
            out += struct.pack('<ii', sidx[e.type], sidx[e.name]) + e.guid
        for e in order:
            out += struct.pack('<i', len(e.attrs))
            for name, t, v in e.attrs:
                out += struct.pack('<i', sidx[name]) + bytes([t])
                out += self._enc(t, v, sidx)
        open(path, 'wb').write(bytes(out))

    def _enc(self, t, v, sidx, inline=False):
        if t & ARRAY:
            bt = t - ARRAY
            return struct.pack('<i', len(v)) + b''.join(self._enc_scalar(bt, x, sidx, True) for x in v)
        return self._enc_scalar(t, v, sidx, inline)

    def _enc_scalar(self, t, v, sidx, inline):
        if t == T_ELEMENT:
            return struct.pack('<i', -1 if v is None else (v.index if isinstance(v, Element) else v))
        if t == T_STRING:
            return (v.encode('utf-8', 'surrogateescape') + b'\0') if inline else struct.pack('<i', sidx[v])
        if t == T_BINARY:
            return struct.pack('<i', len(v)) + v
        fmt = FIXED[t]
        return struct.pack(fmt, *(v if isinstance(v, (tuple, list)) else (v,)))


# ------------------------------------------------------------ dict / bytes API (Doc)
T_ELEM, T_INT, T_FLOAT, T_BOOL, T_STR, T_BIN, T_TIME, T_COLOR, T_V2, T_V3, T_V4, T_QANG, T_QUAT, T_MAT, T_U64, T_U8 = range(1, 17)
ARR = 32
_fix = {T_INT: ('<i', 4), T_FLOAT: ('<f', 4), T_BOOL: ('<?', 1), T_TIME: ('<i', 4), T_COLOR: ('<4B', 4), T_V2: ('<2f', 8),
        T_V3: ('<3f', 12), T_V4: ('<4f', 16), T_QANG: ('<3f', 12), T_QUAT: ('<4f', 16), T_MAT: ('<16f', 64), T_U64: ('<Q', 8), T_U8: ('<B', 1)}

class R:
    def __init__(s, d, p=0): s.d = d; s.p = p
    def i(s): v = struct.unpack_from('<i', s.d, s.p)[0]; s.p += 4; return v
    def b(s): v = s.d[s.p]; s.p += 1; return v
    def cstr(s): e = s.d.index(b'\0', s.p); v = s.d[s.p:e]; s.p = e + 1; return v
    def raw(s, n): v = s.d[s.p:s.p + n]; s.p += n; return v
    def fmt(s, f, n):
        v = struct.unpack_from(f, s.d, s.p); s.p += n
        return v[0] if len(v) == 1 else list(v)

class Doc:
    def __init__(s): s.header = b''; s.prefix = []; s.elements = []

def _read_val(r, t, strtab, inline_str):
    if t == T_ELEM:
        v = r.i()
        if v == -2: return ('guid', r.cstr())
        return v
    if t == T_STR: return r.cstr() if inline_str else strtab[r.i()]
    if t == T_BIN: n = r.i(); return r.raw(n)
    f, n = _fix[t]; return r.fmt(f, n)

def _read_attr(r, strtab, inline_str):
    t = r.b()
    if t > ARR:
        n = r.i(); bt = t - ARR
        if bt == T_STR:  # string arrays are always inline
            return t, [r.cstr() for _ in range(n)]
        return t, [_read_val(r, bt, strtab, inline_str) for _ in range(n)]
    return t, _read_val(r, t, strtab, inline_str)

def loads(d):
    doc = Doc(); e = d.index(b'\n\x00'); doc.header = d[:e + 1]
    r = R(d, e + 2)
    for _ in range(r.i()):
        attrs = []
        for _ in range(r.i()):
            name = r.cstr(); t, v = _read_attr(r, None, True); attrs.append([name, t, v])
        doc.prefix.append(attrs)
    strtab = [r.cstr() for _ in range(r.i())]
    n = r.i()
    for _ in range(n):
        doc.elements.append({'type': strtab[r.i()], 'name': strtab[r.i()], 'guid': r.raw(16), 'attrs': []})
    for el in doc.elements:
        for _ in range(r.i()):
            name = strtab[r.i()]; t, v = _read_attr(r, strtab, False); el['attrs'].append([name, t, v])
    if r.p != len(d): raise ValueError('trailing data %d/%d' % (r.p, len(d)))
    return doc

def load(path): return loads(open(path, 'rb').read())

def _w_val(out, t, v, sidx, inline):
    if t == T_ELEM:
        if isinstance(v, tuple): out += struct.pack('<i', -2) + v[1] + b'\0'
        else: out += struct.pack('<i', v)
    elif t == T_STR: out += (v + b'\0') if inline else struct.pack('<i', sidx[v])
    elif t == T_BIN: out += struct.pack('<i', len(v)) + v
    else:
        f, n = _fix[t]; out += struct.pack(f, *(v if isinstance(v, (list, tuple)) else [v]))

def _w_attr(out, t, v, sidx, inline):
    out.append(t)
    if t > ARR:
        out += struct.pack('<i', len(v)); bt = t - ARR
        for x in v:
            if bt == T_STR: out += x + b'\0'
            else: _w_val(out, bt, x, sidx, inline)
    else: _w_val(out, t, v, sidx, inline)

def dumps(doc):
    strs = []; sidx = {}
    def add(s):
        if s not in sidx: sidx[s] = len(strs); strs.append(s)
    for el in doc.elements:
        add(el['type']); add(el['name'])
        for name, t, v in el['attrs']:
            add(name)
            if t == T_STR: add(v)
    out = bytearray(doc.header + b'\0')
    out += struct.pack('<i', len(doc.prefix))
    for attrs in doc.prefix:
        out += struct.pack('<i', len(attrs))
        for name, t, v in attrs: out += name + b'\0'; _w_attr(out, t, v, None, True)
    out += struct.pack('<i', len(strs))
    for s in strs: out += s + b'\0'
    out += struct.pack('<i', len(doc.elements))
    for el in doc.elements: out += struct.pack('<ii', sidx[el['type']], sidx[el['name']]) + el['guid']
    for el in doc.elements:
        out += struct.pack('<i', len(el['attrs']))
        for name, t, v in el['attrs']: out += struct.pack('<i', sidx[name]); _w_attr(out, t, v, sidx, False)
    return bytes(out)

# ---- helpers ----
def get(el, name, default=None):
    for a in el['attrs']:
        if a[0] == name: return a[2]
    return default
def geta(el, name):
    for a in el['attrs']:
        if a[0] == name: return a
    return None
def set_(el, name, t, v):
    a = geta(el, name)
    if a: a[1] = t; a[2] = v
    else: el['attrs'].append([name, t, v])
def delete(el, name): el['attrs'] = [a for a in el['attrs'] if a[0] != name]


# ------------------------------------------------------------ ModelDoc mesh API (ModelElement)
# attribute type ids (binary 9)
T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_BINARY, T_TIME, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_QUAT, T_MATRIX, T_UINT64, T_UINT8 = range(1, 17)
NSINGLE = 16
AOFF = 32  # array type id = AOFF + element type id
FMT = {T_INT:'<i', T_FLOAT:'<f', T_BOOL:'<B', T_TIME:'<i', T_COLOR:'<4B', T_VEC2:'<2f', T_VEC3:'<3f', T_VEC4:'<4f', T_QANGLE:'<3f', T_QUAT:'<4f', T_MATRIX:'<16f', T_UINT64:'<Q', T_UINT8:'<B'}

class ModelElement:
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
    import numpy as np
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
        elems.append(ModelElement(t, n, eid))
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
    import numpy as np
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
    import numpy as np
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
