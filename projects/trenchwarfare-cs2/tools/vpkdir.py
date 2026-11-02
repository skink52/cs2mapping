"""Index a Source 2 VPK directory: path -> (archive index, offset, length, preload bytes)."""
import struct, sys, pickle
def read_dir(path):
    d = open(path, 'rb').read()
    sig, ver, tree = struct.unpack_from('<III', d, 0)
    hdr = 28 if ver == 2 else 12
    p = hdr; end = hdr + tree; out = {}
    def cstr():
        nonlocal p
        q = d.index(b'\0', p); s = d[p:q].decode('utf-8', 'replace'); p = q + 1; return s
    while True:
        ext = cstr()
        if not ext: break
        while True:
            folder = cstr()
            if not folder: break
            while True:
                name = cstr()
                if not name: break
                crc, pre, arc, off, ln, term = struct.unpack_from('<IHHIIH', d, p); p += 18
                preload = d[p:p + pre]; p += pre
                full = (folder + '/' if folder.strip() else '') + name + '.' + ext
                out[full] = (arc, off, ln, preload, hdr + tree if arc == 0x7fff else None)
    return out
if __name__ == '__main__':
    idx = read_dir(sys.argv[1]); pickle.dump(idx, open(sys.argv[2], 'wb')); print(len(idx))
