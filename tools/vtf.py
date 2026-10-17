"""Decode the top mip of a Source 1 .vtf into a PIL RGBA image."""
import struct
import numpy as np
from PIL import Image

BPP = {0: 4, 1: 4, 2: 3, 3: 3, 4: 2, 5: 1, 6: 2, 7: 2, 8: 1, 9: 3, 10: 3, 11: 4, 12: 4, 16: 4, 17: 2, 18: 2, 19: 2, 21: 2, 22: 2, 24: 8, 25: 8}
BLOCK = {13: 8, 14: 16, 15: 16, 20: 8}

def _size(fmt, w, h):
    if fmt in BLOCK: return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * BLOCK[fmt]
    return w * h * BPP[fmt]

def _c565(c):
    r = ((c >> 11) & 31) * 255 // 31; g = ((c >> 5) & 63) * 255 // 63; b = (c & 31) * 255 // 31
    return np.stack([r, g, b], -1).astype(np.int32)

def _dxt_colors(blocks, dxt1):
    c0 = blocks[:, 0].astype(np.uint32) | (blocks[:, 1].astype(np.uint32) << 8)
    c1 = blocks[:, 2].astype(np.uint32) | (blocks[:, 3].astype(np.uint32) << 8)
    p0, p1 = _c565(c0), _c565(c1)
    four = (c0 > c1) | (not dxt1)
    p2 = np.where(four[:, None], (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four[:, None], (p0 + 2 * p1) // 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)                     # n,4,3
    bits = blocks[:, 4:8].astype(np.uint32)
    idx = bits[:, 0] | (bits[:, 1] << 8) | (bits[:, 2] << 16) | (bits[:, 3] << 24)
    sel = np.stack([(idx >> (2 * i)) & 3 for i in range(16)], 1)   # n,16
    rgb = np.take_along_axis(pal, sel[:, :, None].repeat(3, 2).astype(np.int64), 1)
    alpha = np.full(sel.shape, 255, np.int32)
    if dxt1: alpha = np.where((~four[:, None]) & (sel == 3), 0, 255)
    return rgb, alpha

def _decode_dxt(data, w, h, fmt):
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    bs = BLOCK[fmt]
    b = np.frombuffer(data[:bw * bh * bs], np.uint8).reshape(-1, bs)
    if fmt in (13, 20):
        rgb, a = _dxt_colors(b, True)
    else:
        rgb, _ = _dxt_colors(b[:, 8:], False)
        if fmt == 14:
            ab = b[:, :8]
            a = np.stack([((ab[:, i // 2] >> (4 * (i % 2))) & 15) * 17 for i in range(16)], 1).astype(np.int32)
        else:
            a0 = b[:, 0].astype(np.int32); a1 = b[:, 1].astype(np.int32)
            bits = np.zeros(len(b), np.uint64)
            for i in range(6): bits |= b[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
            sel = np.stack([((bits >> np.uint64(3 * i)) & np.uint64(7)).astype(np.int32) for i in range(16)], 1)
            pal = [a0, a1]
            for i in range(1, 7):
                pal.append(np.where(a0 > a1, ((7 - i) * a0 + i * a1) // 7, 0))
            for i in range(1, 5):
                pal[1 + i] = np.where(a0 > a1, pal[1 + i], ((5 - i) * a0 + i * a1) // 5)
            pal[6] = np.where(a0 > a1, pal[6], 0); pal[7] = np.where(a0 > a1, pal[7], 255)
            pal = np.stack(pal, 1)
            a = np.take_along_axis(pal, sel, 1)
    px = np.concatenate([rgb, a[:, :, None]], 2).reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return Image.fromarray(px[:h, :w].clip(0, 255).astype(np.uint8), 'RGBA')

def decode(data):
    assert data[:4] == b'VTF\0', 'not a VTF'
    vmaj, vmin, hsize = struct.unpack_from('<III', data, 4)
    w, h, flags, frames, first = struct.unpack_from('<HHIHH', data, 16)
    fmt, mips, lfmt, lw, lh = struct.unpack_from('<iBiBB', data, 52)
    depth = struct.unpack_from('<H', data, 63)[0] if vmin >= 2 else 1
    depth = max(depth, 1)
    faces = 6 if flags & 0x4000 else 1
    if vmin >= 3:
        nres = struct.unpack_from('<I', data, 68)[0]
        off = None
        for i in range(nres):
            tag, fl, o = struct.unpack_from('<3sBI', data, 80 + 8 * i)
            if tag == b'\x30\x00\x00': off = o
        hi = off
    else:
        hi = hsize + (_size(lfmt, lw, lh) if lfmt >= 0 and lw else 0)
    # mips are stored smallest first; skip to mip 0 of frame 0 / face 0
    p = hi
    for m in range(mips - 1, 0, -1):
        mw, mh = max(1, w >> m), max(1, h >> m)
        p += _size(fmt, mw, mh) * frames * faces * max(1, depth >> m)
    raw = data[p:p + _size(fmt, w, h)]
    if fmt in BLOCK: return _decode_dxt(raw, w, h, fmt)
    a = np.frombuffer(raw, np.uint8)
    if fmt == 0: px = a.reshape(h, w, 4)
    elif fmt == 1: px = a.reshape(h, w, 4)[:, :, ::-1]
    elif fmt == 2: px = np.dstack([a.reshape(h, w, 3), np.full((h, w), 255, np.uint8)])
    elif fmt == 3: px = np.dstack([a.reshape(h, w, 3)[:, :, ::-1], np.full((h, w), 255, np.uint8)])
    elif fmt == 12: px = a.reshape(h, w, 4)[:, :, [2, 1, 0, 3]]
    elif fmt == 16: q = a.reshape(h, w, 4); px = np.dstack([q[:, :, [2, 1, 0]], np.full((h, w), 255, np.uint8)])
    elif fmt == 11: px = a.reshape(h, w, 4)[:, :, [1, 2, 3, 0]]
    elif fmt in (5, 8): g = a.reshape(h, w); px = np.dstack([g, g, g, np.full((h, w), 255, np.uint8) if fmt == 5 else g])
    elif fmt == 6: q = a.reshape(h, w, 2); px = np.dstack([q[:, :, 0]] * 3 + [q[:, :, 1]])
    elif fmt == 24:
        f = np.frombuffer(raw, np.float16).reshape(h, w, 4).astype(np.float32)
        px = (np.clip(f, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
    elif fmt == 4:
        c = np.frombuffer(raw, '<u2').reshape(h, w).astype(np.uint32)
        px = np.dstack([_c565(c).astype(np.uint8)[..., ::-1], np.full((h, w), 255, np.uint8)])
    elif fmt == 17:
        c = np.frombuffer(raw, '<u2').reshape(h, w).astype(np.uint32)
        px = np.dstack([_c565(c).astype(np.uint8)[..., ::-1], np.full((h, w), 255, np.uint8)])
    else:
        raise ValueError('unsupported VTF format %d' % fmt)
    return Image.fromarray(np.ascontiguousarray(px), 'RGBA')

def has_alpha(img): return img.getchannel('A').getextrema()[0] < 255
