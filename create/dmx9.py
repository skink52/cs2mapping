"""Lossless reader/writer for Source 2 binary DMX v9 (Hammer .vmap files).

Elements are kept in file order, string-table order is preserved, and every attribute keeps
its exact type id, so load() -> save() reproduces the original bytes. New elements and
attributes can be added; their strings are appended to the table on save.
"""
import struct, uuid

T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_BINARY, T_TIME, T_COLOR = 1, 2, 3, 4, 5, 6, 7, 8
T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_QUAT, T_MATRIX, T_UINT64, T_UINT8 = 9, 10, 11, 12, 13, 14, 15, 16
ARRAY = 32


class Element:
    __slots__ = ("type", "name", "id", "attrs")

    def __init__(self, type_, name="", id_=None):
        self.type = type_
        self.name = name
        self.id = id_ or uuid.uuid4()
        self.attrs = {}          # name -> [type_id, value]

    def __getitem__(self, k): return self.attrs[k][1]
    def get(self, k, d=None): return self.attrs[k][1] if k in self.attrs else d
    def __contains__(self, k): return k in self.attrs
    def set(self, k, t, v): self.attrs[k] = [t, v]; return self

    def __setitem__(self, k, v):
        if k in self.attrs: self.attrs[k][1] = v
        else: raise KeyError(f"new attribute {k} needs a type: use set()")

    def __repr__(self): return f"<{self.type} '{self.name}'>"


class Missing:
    """Reference to an element stored outside this file (-2 + guid string)."""
    def __init__(self, guid): self.guid = guid


class Reader:
    def __init__(self, data):
        self.d = data; self.p = 0

    def take(self, n):
        b = self.d[self.p:self.p + n]; self.p += n; return b

    def i32(self): return struct.unpack_from("<i", self.d, self.take(4) and self.p - 4)[0]
    def u8(self): v = self.d[self.p]; self.p += 1; return v

    def cstr(self):
        e = self.d.index(b"\0", self.p); s = self.d[self.p:e].decode("utf-8"); self.p = e + 1; return s


class DMX:
    def __init__(self):
        self._orphans = set()
        self.header = ""
        self.prefix = []       # list of attr dicts (inline strings)
        self.strings = []
        self.elements = []

    @property
    def root(self): return self.elements[0]

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, path):
        data = open(path, "rb").read()
        dm = cls()
        end = data.index(b"\0")
        dm.header = data[:end].decode("ascii")
        r = Reader(data); r.p = end + 1
        assert "binary 9" in dm.header, dm.header

        def value(t, inline, elems):
            if t == T_ELEMENT:
                i = r.i32()
                if i == -1: return None
                if i == -2: return Missing(r.cstr())
                return elems[i] if elems is not None else i
            if t == T_INT: return r.i32()
            if t == T_FLOAT: return struct.unpack("<f", r.take(4))[0]
            if t == T_BOOL: return r.u8()
            if t == T_STRING: return r.cstr() if inline else dm.strings[r.i32()]
            if t == T_BINARY: n = r.i32(); return r.take(n)
            if t == T_TIME: return r.i32()
            if t == T_COLOR: return tuple(r.take(4))
            if t == T_VEC2: return struct.unpack("<2f", r.take(8))
            if t in (T_VEC3, T_QANGLE): return struct.unpack("<3f", r.take(12))
            if t in (T_VEC4, T_QUAT): return struct.unpack("<4f", r.take(16))
            if t == T_MATRIX: return struct.unpack("<16f", r.take(64))
            if t == T_UINT64: return struct.unpack("<Q", r.take(8))[0]
            if t == T_UINT8: return r.u8()
            raise ValueError(f"type {t} at {r.p}")

        def attrs(inline_names, elems):
            out = {}
            for _ in range(r.i32()):
                name = r.cstr() if inline_names else dm.strings[r.i32()]
                t = r.u8()
                if t >= ARRAY:
                    n = r.i32()
                    out[name] = [t, [value(t - ARRAY, True, elems) for _ in range(n)]]
                else:
                    out[name] = [t, value(t, inline_names, elems)]
            return out

        for _ in range(r.i32()):
            dm.prefix.append(attrs(True, None))
        dm.strings = [r.cstr() for _ in range(r.i32())]
        n = r.i32()
        for _ in range(n):
            t = dm.strings[r.i32()]; nm = dm.strings[r.i32()]
            dm.elements.append(Element(t, nm, uuid.UUID(bytes_le=r.take(16))))
        for e in dm.elements:
            e.attrs = attrs(False, dm.elements)
        assert r.p == len(data), f"trailing bytes {len(data) - r.p}"
        dm._orphans = set(id(e) for e in dm.elements) - dm._reachable()
        dm._keep = [e for e in dm.elements if id(e) in dm._orphans]   # hold references so ids stay valid
        return dm

    def _reachable(self):
        reach, stack = set(), [self.elements[0]]
        while stack:
            e = stack.pop()
            if id(e) in reach: continue
            reach.add(id(e))
            for t, v in e.attrs.values():
                if (t & ~ARRAY) == T_ELEMENT:
                    for x in (v if t >= ARRAY else [v]):
                        if isinstance(x, Element) and id(x) not in reach: stack.append(x)
        return reach

    # ------------------------------------------------------------------ save
    def save(self, path):
        # drop unreachable elements? no: keep file order, but append newly referenced ones
        # keep only elements reachable from the root (file order first, then new ones)
        reach = set()
        stack = [self.elements[0]]
        newcomers = []
        known = set(id(e) for e in self.elements)
        while stack:
            e = stack.pop()
            if id(e) in reach: continue
            reach.add(id(e))
            if id(e) not in known: newcomers.append(e)
            for t, v in e.attrs.values():
                if (t & ~ARRAY) == T_ELEMENT:
                    for x in (v if t >= ARRAY else [v]):
                        if isinstance(x, Element) and id(x) not in reach: stack.append(x)
        # newcomers in a stable depth-first order
        orphans = getattr(self, "_orphans", set())   # elements that were already unreferenced in the file
        order = [e for e in self.elements if id(e) in reach or id(e) in orphans]
        seen = set(id(e) for e in order)
        def walk(e):
            for t, v in e.attrs.values():
                if (t & ~ARRAY) == T_ELEMENT:
                    for x in (v if t >= ARRAY else [v]):
                        if isinstance(x, Element) and id(x) not in seen:
                            seen.add(id(x)); order.append(x); walk(x)
        for e in list(order): walk(e)
        self.elements = order
        index = {id(e): i for i, e in enumerate(order)}
        strings = list(self.strings); sidx = {s: i for i, s in enumerate(strings)}

        def S(s):
            if s not in sidx: sidx[s] = len(strings); strings.append(s)
            return sidx[s]
        for e in order:
            S(e.type); S(e.name)
            for k, (t, v) in e.attrs.items():
                S(k)
                if t == T_STRING: S(v)

        out = bytearray()
        w = out.extend
        i32 = lambda v: w(struct.pack("<i", v))
        cstr = lambda s: w(s.encode("utf-8") + b"\0")

        def value(t, v, inline):
            if t == T_ELEMENT:
                if v is None: i32(-1)
                elif isinstance(v, Missing): i32(-2); cstr(v.guid)
                else: i32(index[id(v)])
            elif t == T_INT: i32(int(v))
            elif t == T_FLOAT: w(struct.pack("<f", v))
            elif t == T_BOOL: w(bytes([1 if v else 0]))
            elif t == T_STRING:
                if inline: cstr(v)
                else: i32(sidx[v])
            elif t == T_BINARY: i32(len(v)); w(v)
            elif t == T_TIME: i32(int(v))
            elif t == T_COLOR: w(bytes(v))
            elif t == T_VEC2: w(struct.pack("<2f", *v))
            elif t in (T_VEC3, T_QANGLE): w(struct.pack("<3f", *v))
            elif t in (T_VEC4, T_QUAT): w(struct.pack("<4f", *v))
            elif t == T_MATRIX: w(struct.pack("<16f", *v))
            elif t == T_UINT64: w(struct.pack("<Q", v))
            elif t == T_UINT8: w(bytes([v]))
            else: raise ValueError(t)

        def attrs(a, inline_names):
            i32(len(a))
            for k, (t, v) in a.items():
                if inline_names: cstr(k)
                else: i32(sidx[k])
                w(bytes([t]))
                if t >= ARRAY:
                    i32(len(v))
                    for x in v: value(t - ARRAY, x, True)
                else:
                    value(t, v, inline_names)

        w(self.header.encode("ascii") + b"\0")
        i32(len(self.prefix))
        for a in self.prefix: attrs(a, True)
        i32(len(strings))
        for s in strings: cstr(s)
        i32(len(order))
        for e in order:
            i32(sidx[e.type]); i32(sidx[e.name]); w(e.id.bytes_le)
        for e in order: attrs(e.attrs, False)
        open(path, "wb").write(bytes(out))
        self.strings = strings


def dump(e, depth=0, maxdepth=3, seen=None, out=None):
    """Readable outline of an element tree (for exploring)."""
    seen = seen if seen is not None else set()
    out = out if out is not None else []
    pad = "  " * depth
    out.append(f"{pad}{e.type} '{e.name}'")
    if id(e) in seen: out[-1] += " (seen)"; return out
    seen.add(id(e))
    for k, (t, v) in e.attrs.items():
        base = t & ~ARRAY
        if base == T_ELEMENT:
            vals = v if t >= ARRAY else [v]
            out.append(f"{pad}  .{k}: [{len(vals)} el]" if t >= ARRAY else f"{pad}  .{k}:")
            if depth < maxdepth:
                for x in vals[:12]:
                    if isinstance(x, Element): dump(x, depth + 2, maxdepth, seen, out)
        else:
            s = repr(v)
            out.append(f"{pad}  .{k} ({t}) = {s[:100]}")
    return out
