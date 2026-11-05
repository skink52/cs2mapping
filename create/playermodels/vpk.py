"""Source 1 VPK (v1/v2) reader: list and extract files from a *_dir.vpk and its numbered archives. Read-only, numpy-free.

usage: python3 -I vpk.py <x_dir.vpk> [--list] [--prefix materials/models/] [--out DIR]

Used for the base-game materials GMod player models expect from Half-Life 2 / CS:S (citizen faces, eyes, the skeleton, CS:S
terrorists): SteamCMD's anonymous Garry's Mod dedicated server (app 4020) ships them in sourceengine/ (hl2_textures, hl2_misc,
content_hl2, content_cstrike). Extract the materials/ subtree once into <work>/basegame/ (fetch.paths 'basegame'); the converter
and the scan use it as the last search root.
"""
import os, struct, sys


def entries(dir_path):
    """yield (path, archive index, offset, length, preload bytes)"""
    with open(dir_path, 'rb') as f:
        data = f.read()
    sig, ver, tree = struct.unpack_from('<III', data, 0)
    if sig != 0x55AA1234: raise ValueError('%s: not a VPK' % dir_path)
    off = 12 if ver == 1 else 28
    end = off + tree
    def cstr():
        nonlocal off
        e = data.index(b'\0', off); s = data[off:e].decode('latin-1'); off = e + 1
        return s
    while off < end:
        ext = cstr()
        if not ext: break
        while True:
            d = cstr()
            if not d: break
            while True:
                n = cstr()
                if not n: break
                crc, pre, arc, eoff, elen, term = struct.unpack_from('<IHHIIH', data, off); off += 18
                preload = data[off:off + pre]; off += pre
                path = ('' if d == ' ' else d + '/') + n + ('' if ext == ' ' else '.' + ext)
                yield path.lower(), arc, (eoff + end if arc == 0x7FFF else eoff), elen, preload


def extract(dir_path, out_dir, prefix='', skip_existing=True):
    base = dir_path[:-len('_dir.vpk')]
    handles, n, total = {}, 0, 0
    try:
        for path, arc, off, ln, pre in entries(dir_path):
            if prefix and not path.startswith(prefix): continue
            dst = os.path.join(out_dir, *path.split('/'))
            if '..' in path.split('/'): continue
            if skip_existing and os.path.exists(dst): continue
            if arc == 0x7FFF: src = dir_path
            else: src = '%s_%03d.vpk' % (base, arc)
            if src not in handles: handles[src] = open(src, 'rb')
            h = handles[src]; h.seek(off)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as o: o.write(pre + h.read(ln))
            n += 1; total += len(pre) + ln
    finally:
        for h in handles.values(): h.close()
    return n, total


if __name__ == '__main__':
    a = sys.argv[1:]
    vp = a[0]
    pfx = a[a.index('--prefix') + 1].lower() if '--prefix' in a else ''
    if '--list' in a:
        for p, arc, off, ln, pre in entries(vp):
            if p.startswith(pfx): print(p, ln + len(pre))
    else:
        out = a[a.index('--out') + 1] if '--out' in a else '.'
        n, t = extract(vp, out, pfx)
        print('%s: %d files, %.0f MB -> %s' % (os.path.basename(vp), n, t / 1e6, out))
