"""Garry's Mod addon archives (.gma, and the LZMA-packed legacy .bin that SteamCMD sometimes delivers): list and extract.

usage: python3 -I gma.py <file.gma|file.bin> [out dir] [--only models/,materials/,lua/]

Downloaded archives are untrusted data: paths are sanitised (no absolute paths, no "..") and nothing in them is run.
Without an out dir it lists the files. --only keeps files whose path starts with one of the prefixes (default: models/,
materials/, lua/ - lua is read as text later to find player_manager.AddValidModel lines, never executed).
"""
import io, lzma, os, struct, sys

DEFAULT_ONLY = ('models/', 'materials/', 'lua/')


def _cstr(f):
    b = bytearray()
    while True:
        c = f.read(1)
        if not c or c == b'\0': return b.decode('utf-8', 'replace')
        b += c


def open_gma(path):
    data = open(path, 'rb').read()
    if data[:4] != b'GMAD':
        # legacy .bin: LZMA "alone" stream. Some have no end-of-stream marker, which lzma.decompress() rejects
        # ("Compressed data ended before the end-of-stream marker"); a streaming decompressor returns what's there.
        data = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(data)
        if data[:4] != b'GMAD': raise ValueError('%s: not a GMA archive' % path)
    return data


def read(path):
    """-> (info dict, [(path, size, offset)], raw bytes)"""
    data = open_gma(path)
    f = io.BytesIO(data); f.read(4)
    ver = f.read(1)[0]
    steamid, ts = struct.unpack('<QQ', f.read(16))
    if ver > 1:
        while _cstr(f): pass          # required content list
    info = {'name': _cstr(f), 'description': _cstr(f), 'author': _cstr(f), 'version': ver}
    struct.unpack('<i', f.read(4))
    entries = []
    while True:
        num, = struct.unpack('<I', f.read(4))
        if num == 0: break
        name = _cstr(f); size, crc = struct.unpack('<qI', f.read(12))
        entries.append([name, size])
    off = f.tell()
    out = []
    for name, size in entries:
        out.append((name, size, off)); off += size
    return info, out, data


def safe_rel(name):
    p = name.replace('\\', '/').lower()
    parts = [x for x in p.split('/') if x not in ('', '.')]
    if not parts or any(x == '..' or ':' in x for x in parts): return None
    return '/'.join(parts)


def extract(path, out_dir, only=DEFAULT_ONLY):
    """extracts (lower-cased paths, like the game's case-insensitive lookups); returns (info, [relative paths])"""
    info, files, data = read(path)
    done = []
    for name, size, off in files:
        rel = safe_rel(name)
        if rel is None or (only and not rel.startswith(tuple(only))): continue
        dst = os.path.join(out_dir, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as o: o.write(data[off:off + size])
        done.append(rel)
    return info, done


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only = DEFAULT_ONLY
    for a in sys.argv[1:]:
        if a.startswith('--only='): only = tuple(x for x in a[7:].split(',') if x)
    if len(args) == 1:
        info, files, _ = read(args[0])
        print(info)
        for n, s, _ in files: print('%10d  %s' % (s, n))
    else:
        info, done = extract(args[0], args[1], only)
        print('%s: %d files -> %s' % (info['name'], len(done), args[1]))
