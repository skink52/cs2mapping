"""Binary DMX (encoding version 9, as Hammer saves .vmap) reader/writer.

Lossless: load() + save() reproduces the original bytes. Elements keep their attribute order,
the string table keeps its order (new strings are appended).
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
