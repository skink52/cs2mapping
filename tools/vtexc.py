"""Compiled CS2 texture (vtex_c) -> RGB image, for stock textures read out of CS2's VPKs (radartex.py paints radar floors with them).

  python3 vtexc.py <pak01_dir.vpk> <texture path, e.g. materials/de_ancient/hr_ancient_ground_grass_01_color_tga_696ef19.vtex> <out.png> [max px]

Layout (resource header v12, DATA block of the texture, mips smallest first after the DATA block, optionally LZ4 per mip) as read by
Source 2 Viewer / SourceIO. Decodes DXT1/DXT5/BC4/BC5/BC7 with Pillow's 'bcn' decoder and RGBA8888/BGRA8888 directly; YCoCg DXT5 is converted.
Other formats (BC6H HDR, ETC2, float) return None. Only the mip nearest above `max_px` is decoded, so a 2048 px texture costs a 256 px read.
"""
import struct, sys, os
import numpy as np
from PIL import Image

BCN = {1: (1, 8), 2: (3, 16), 20: (7, 16), 27: (4, 8), 21: (5, 16)}    # vtex format -> (Pillow bcn n, bytes per 4x4 block)
RAW = {4: 'RGBA', 28: 'BGRA'}

def _lz4(src, usz):
    try:
        import lz4.block
        return lz4.block.decompress(src, uncompressed_size=usz)
    except ImportError:
        import vmatc
        return vmatc.lz4_block(src, usz)

def _mip_bytes(fmt, w, h):
    if fmt in BCN: return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * BCN[fmt][1]
    return w * h * 4

def decode(raw, max_px=256):
    """RGB uint8 array (h, w, 3) of the smallest mip at least max_px wide (or the biggest there is), or None."""
    fs, hv, rv, bo, bc = struct.unpack_from('<IHHII', raw, 0)
    if hv != 12: return None
    blocks = {}; p = 8 + bo
    for _ in range(bc):
        off, sz = struct.unpack_from('<II', raw, p + 4); blocks[raw[p:p + 4]] = (p + 4 + off, sz); p += 12
    if b'DATA' not in blocks: return None
    d, dsz = blocks[b'DATA']
    ver, flags = struct.unpack_from('<HH', raw, d)
    if ver != 1: return None
    w, h, depth = struct.unpack_from('<HHH', raw, d + 20)
    fmt, mips = raw[d + 26], raw[d + 27]
    if fmt not in BCN and fmt not in RAW: return None
    if flags & 4: return None                                       # cube map
    eo = d + 32; eoff, ecnt = struct.unpack_from('<II', raw, eo); ep = eo + eoff
    comp = None
    for i in range(ecnt):
        q = ep + i * 12; typ, o, s = struct.unpack_from('<III', raw, q); dp = q + 4 + o
        if typ == 3:                                                # COMPRESSED_MIP_SIZE: compressed flag, ?, count, then per-mip sizes
            c1, _, n = struct.unpack_from('<III', raw, dp)
            comp = (c1 == 1, list(struct.unpack_from('<%dI' % n, raw, dp + 12)))
    level = 0
    while level + 1 < mips and (w >> (level + 1)) >= max_px: level += 1
    mw, mh = max(1, w >> level), max(1, h >> level)
    pos = d + dsz
    if comp and comp[0]:
        sizes = comp[1]
        pos += sum(sizes[level + 1:])
        data = raw[pos:pos + sizes[level]]
        want = _mip_bytes(fmt, mw, mh)
        if len(data) != want: data = _lz4(data, want)
    else:
        pos += sum(_mip_bytes(fmt, max(1, w >> k), max(1, h >> k)) for k in range(level + 1, mips))
        data = raw[pos:pos + _mip_bytes(fmt, mw, mh)]
    if fmt in RAW:
        im = Image.frombytes('RGBA', (mw, mh), data, 'raw', RAW[fmt])
    else:
        bw, bh = ((mw + 3) // 4) * 4, ((mh + 3) // 4) * 4
        mode = 'L' if fmt == 27 else 'RGBA'
        im = Image.frombytes(mode, (bw, bh), data, 'bcn', BCN[fmt][0]).crop((0, 0, mw, mh))
    a = np.asarray(im.convert('RGBA')).copy()
    if fmt == 2 and b'YCoCg Conversion' in raw[:d]:                 # colour stored as YCoCg in a DXT5 (REDI/RED2 special dependency)
        o = a.astype(np.int16); s = (o[..., 2] >> 3) + 1
        co = (o[..., 0] - 128) / s; cg = (o[..., 1] - 128) / s
        a = np.stack([o[..., 3] + co - cg, o[..., 3] + cg, o[..., 3] - co - cg], -1).clip(0, 255).astype(np.uint8)
        return a
    return a[..., :3]

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import vmatc
    a = sys.argv[1:]
    path = a[1] if a[1].endswith('_c') else a[1] + '_c'
    img = decode(vmatc.read_vpk_file(a[0], path), int(a[3]) if len(a) > 3 else 1 << 16)
    if img is None: sys.exit('unsupported texture format')
    Image.fromarray(img).save(a[2]); print('wrote', a[2], img.shape[1], 'x', img.shape[0])
