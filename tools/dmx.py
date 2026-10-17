"""Read/write Source 2 binary DMX (encoding binary 9) - the .vmap format.

doc = dmx.load(path) -> Doc with .header, .prefix (list of attr lists), .elements
Element = dict(type=bytes, name=bytes, guid=bytes(16), attrs=list[[name, type, value]])
Element references are ints (index into doc.elements), -1 = null.
"""
import struct

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
