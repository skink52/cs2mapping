"""Source 1 textures and materials: VTF (7.0-7.5) mip 0 -> RGBA numpy array, and a VMT reader.

    rgba = load_vtf(path)                       # (h, w, 4) uint8
    shader, params = load_vmt(path, roots)      # params: lower-case keys ('$basetexture', ...) -> str; 'patch' resolved

python3 -I vtf.py <file.vtf> <out.png> converts one texture.
DXT1/3/5 go through a DDS header that Pillow decodes; the 8-bit-per-channel and 565/4444/5551 formats are unpacked here.
"""
import io, os, re, struct, sys
import numpy as np
from PIL import Image

# format id -> bytes per pixel (block formats: bytes per 4x4 block, negative)
FMT = {0: 4, 1: 4, 2: 3, 3: 3, 4: 2, 5: 1, 6: 2, 8: 1, 9: 3, 10: 3, 11: 4, 12: 4, 13: -8, 14: -16, 15: -16, 16: 4, 17: 2,
       18: 2, 19: 2, 20: -8, 21: 2, 22: 2, 23: 4}


def _size(fmt, w, h):
    b = FMT[fmt]
    if b < 0: return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * -b
    return w * h * b


def _dds(fourcc, w, h, data):
    hdr = struct.pack('<4sI6I44x', b'DDS ', 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(data), 0, 1)
    pf = struct.pack('<II4s5I', 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    caps = struct.pack('<5I', 0x1000, 0, 0, 0, 0)
    return np.array(Image.open(io.BytesIO(hdr + pf + caps + data)).convert('RGBA'))


def _unpack(fmt, w, h, b):
    a = np.frombuffer(b, np.uint8)
    if fmt in (13, 20): return _dds(b'DXT1', w, h, b)
    if fmt == 14: return _dds(b'DXT3', w, h, b)
    if fmt == 15: return _dds(b'DXT5', w, h, b)
    full = lambda x: np.dstack([x, np.full(x.shape[:2], 255, np.uint8)])
    if fmt in (0, 23): return a.reshape(h, w, 4).copy()                       # RGBA8888 (UVWQ treated alike)
    if fmt == 1: return a.reshape(h, w, 4)[..., ::-1].copy()                  # ABGR
    if fmt in (2, 9): return full(a.reshape(h, w, 3))                        # RGB888
    if fmt in (3, 10): return full(a.reshape(h, w, 3)[..., ::-1])             # BGR888
    if fmt == 11: return a.reshape(h, w, 4)[..., [1, 2, 3, 0]].copy()         # ARGB
    if fmt == 12: return a.reshape(h, w, 4)[..., [2, 1, 0, 3]].copy()         # BGRA
    if fmt == 16: return full(a.reshape(h, w, 4)[..., [2, 1, 0]])             # BGRX
    if fmt == 5: return full(np.repeat(a.reshape(h, w, 1), 3, 2))            # I8
    if fmt == 6: x = a.reshape(h, w, 2); return np.dstack([x[..., 0]] * 3 + [x[..., 1]])
    if fmt == 8: x = a.reshape(h, w); return np.dstack([np.full((h, w), 255, np.uint8)] * 3 + [x])
    if fmt == 22: x = a.reshape(h, w, 2); return np.dstack([x[..., 0], x[..., 1], np.full((h, w), 255, np.uint8), np.full((h, w), 255, np.uint8)])
    v = np.frombuffer(b, '<u2').reshape(h, w).astype(np.uint32)
    if fmt in (4, 17):                                                        # RGB565 / BGR565
        r, g, bb = (v >> 11) & 31, (v >> 5) & 63, v & 31
        if fmt == 4: r, bb = bb, r
        return full(np.dstack([r * 255 // 31, g * 255 // 63, bb * 255 // 31]).astype(np.uint8))
    if fmt == 19:                                                             # BGRA4444
        return np.dstack([((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17, ((v >> 12) & 15) * 17]).astype(np.uint8)
    if fmt in (18, 21):                                                       # BGRX5551 / BGRA5551
        r, g, bb, al = (v >> 10) & 31, (v >> 5) & 31, v & 31, v >> 15
        return np.dstack([r * 255 // 31, g * 255 // 31, bb * 255 // 31, (al * 255 if fmt == 21 else np.full_like(al, 255))]).astype(np.uint8)
    raise ValueError('VTF format %d not supported' % fmt)


def load_vtf(path):
    d = open(path, 'rb').read()
    if d[:4] != b'VTF\0': raise ValueError('%s: not a VTF' % path)
    vmaj, vmin, hsize = struct.unpack_from('<III', d, 4)
    w, h, flags, frames = struct.unpack_from('<HHIH', d, 16)
    hifmt, = struct.unpack_from('<i', d, 52); mips = d[56]
    lofmt, = struct.unpack_from('<i', d, 57); low, loh = d[61], d[62]
    depth = struct.unpack_from('<H', d, 63)[0] if vmin >= 2 else 1
    depth = max(1, depth)
    faces = 6 if flags & 0x4000 else 1
    if vmin >= 3:
        nres, = struct.unpack_from('<I', d, 68)
        start = None
        for k in range(nres):
            tag, off = d[80 + 8 * k:83 + 8 * k], struct.unpack_from('<I', d, 84 + 8 * k)[0]
            if tag == b'\x30\0\0': start = off
        if start is None: raise ValueError('%s: no image data' % path)
    else:
        start = hsize + (_size(lofmt, low, loh) if lofmt >= 0 and low else 0)
    # mips run smallest to largest; frame 0 of mip 0 starts after all smaller mips
    off = start
    for m in range(mips - 1, 0, -1):
        off += _size(hifmt, max(1, w >> m), max(1, h >> m)) * frames * faces * max(1, depth >> m)
    n = _size(hifmt, w, h)
    return _unpack(hifmt, w, h, d[off:off + n])


# ---------------------------------------------------------------- VMT
def _kv(text):
    """tiny KeyValues parser -> nested [(key, value or list)]"""
    toks = re.findall(r'"([^"]*)"|(\{|\})|([^\s{}"]+)', re.sub(r'//[^\n]*', '', text))
    toks = [a if a or (not b and not c) else (b or c) for a, b, c in toks]
    pos = 0
    def block():
        nonlocal pos
        out = []
        while pos < len(toks):
            t = toks[pos]; pos += 1
            if t == '}': return out
            if pos < len(toks) and toks[pos] == '{':
                pos += 1; out.append((t, block()))
            elif pos < len(toks):
                out.append((t, toks[pos])); pos += 1
        return out
    return block()


def find_file(rel, roots):
    rel = rel.replace('\\', '/').lower().lstrip('/')
    for r in roots:
        p = os.path.join(r, *rel.split('/'))
        if os.path.exists(p): return p
    return None


def load_vmt(path, roots, depth=0):
    root = _kv(open(path, 'r', encoding='latin-1').read())
    if not root: raise ValueError('%s: empty VMT' % path)
    shader, body = root[0]
    params = {}
    if isinstance(body, list):
        for k, v in body:
            if isinstance(v, str): params[k.lower()] = v
            elif k.lower() == 'replace' or k.lower() == 'insert':
                for k2, v2 in v:
                    if isinstance(v2, str): params[k2.lower()] = v2
    if shader.lower() == 'patch' and depth < 4:
        inc = params.get('include')
        p = find_file(inc, roots) if inc else None
        if p:
            s2, base = load_vmt(p, roots, depth + 1)
            base.update({k: v for k, v in params.items() if k != 'include'})
            return s2, base
    return shader.lower(), params


if __name__ == '__main__':
    Image.fromarray(load_vtf(sys.argv[1])).save(sys.argv[2])
