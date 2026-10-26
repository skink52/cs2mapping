"""Minimal CS2 resource reader: pull files out of pak01 VPKs, list a vmat_c's texture references, decode vtex_c mip 0 to PNG.
Reference: ValveResourceFormat (Texture.cs). Only LZ4/uncompressed mips and DXT1/DXT5/BC4/BC5/BC7/RGBA8888 formats."""
import struct, io, re, os, pickle
import numpy as np
from PIL import Image

VPK_DIR = os.environ.get('CS2_VPK_DIR', '')   # folder holding CS2's pak01_dir.vpk and the pak01_NNN.vpk chunks you need
_idx = None


def index():
    global _idx
    if _idx is None:
        import vpkdir
        _idx = vpkdir.read_dir(os.path.join(VPK_DIR, 'pak01_dir.vpk'))
    return _idx


def vpk_read(path):
    arc, off, ln, pre, inline = index()[path]
    if arc == 0x7fff:
        d = open(os.path.join(VPK_DIR, 'pak01_dir.vpk'), 'rb'); d.seek(inline + off); return pre + d.read(ln)
    f = open(os.path.join(VPK_DIR, 'pak01_%03d.vpk' % arc), 'rb'); f.seek(off)
    return pre + f.read(ln)


def archive_of(path):
    return index()[path][0]


def refs(data):
    return sorted(set(m.decode() for m in re.findall(rb'(?:materials|models)/[\w/\.\-]+\.vtex', data)))


def lz4_block(src, out_size):
    dst = bytearray(); i = 0; n = len(src)
    while i < n:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255: break
        dst += src[i:i + lit]; i += lit
        if i >= n: break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4
        start = len(dst) - off
        if off >= ml: dst += dst[start:start + ml]
        else:
            for k in range(ml): dst.append(dst[start + k])
    return bytes(dst[:out_size])


BLOCK = {1: 8, 2: 16, 20: 16, 21: 16, 27: 8}


def mip_size(fmt, w, h):
    if fmt in BLOCK: return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * BLOCK[fmt]
    if fmt in (4, 28): return w * h * 4
    raise ValueError('format %d' % fmt)


def dds(fmt, w, h, data):
    # DDS with DX10 header where needed, decoded by Pillow
    fourcc = {1: b'DXT1', 2: b'DXT5'}.get(fmt, b'DX10')
    hdr = struct.pack('<4sI6I44x', b'DDS ', 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, len(data), 0, 1)
    pf = struct.pack('<II4s5I', 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    caps = struct.pack('<5I', 0x1000, 0, 0, 0, 0)
    out = hdr + pf + caps
    if fourcc == b'DX10':
        dxgi = {20: 98, 21: 83, 27: 80}[fmt]
        out += struct.pack('<5I', dxgi, 3, 0, 1, 0)
    return Image.open(io.BytesIO(out + data))


def decode_vtex(data, mip=0):
    b = io.BytesIO(data)
    size, hv, ver, boff, bcount = struct.unpack('<IHHII', data[:16])
    blocks = {}
    for k in range(bcount):
        p = 8 + boff + k * 12
        t, o, s = struct.unpack_from('<4sII', data, p)
        blocks[t] = (p + 4 + o, s)
    off, sz = blocks[b'DATA']
    ver, flags = struct.unpack_from('<HH', data, off)
    w, h, depth, fmt, nmip = struct.unpack_from('<HHHBB', data, off + 20)
    eoff, ecount = struct.unpack_from('<II', data, off + 32)
    comp = None; method = 0
    p = off + 32 + eoff
    for k in range(ecount):
        t, o, s = struct.unpack_from('<III', data, p + k * 12)
        if t == 4:
            q = p + k * 12 + 4 + o
            method, moff, mips = struct.unpack_from('<III', data, q)
            comp = struct.unpack_from('<%di' % mips, data, q + 4 + moff)
    if method == 2: raise ValueError('zstd mips')
    pos = off + sz
    want = min(mip, nmip - 1)
    for j in range(nmip - 1, want, -1):
        ms = mip_size(fmt, max(1, w >> j), max(1, h >> j)) * max(1, depth)
        if comp is not None: ms = min(ms, comp[j])
        pos += ms
    mw, mh = max(1, w >> want), max(1, h >> want)
    full = mip_size(fmt, mw, mh)
    if comp is not None and comp[want] < full: raw = lz4_block(data[pos:pos + comp[want]], full)
    else: raw = data[pos:pos + full]
    if fmt in (4, 28):
        a = np.frombuffer(raw, np.uint8).reshape(mh, mw, 4)
        if fmt == 28: a = a[..., [2, 1, 0, 3]]
        return Image.fromarray(a.copy(), 'RGBA')
    return dds(fmt, mw, mh, raw)
