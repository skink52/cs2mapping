"""Minimal VPK (v1/v2) directory reader: path -> (archive index, offset, length, preload bytes)."""
import struct

class VPK:
    def __init__(s, dir_path):
        s.path = dir_path; s.files = {}
        d = open(dir_path, 'rb').read()
        sig, ver, tree = struct.unpack_from('<III', d, 0)
        assert sig == 0x55aa1234, 'not a vpk'
        p = 12 if ver == 1 else 28
        s.data_start = p + tree
        def cstr():
            nonlocal p
            e = d.index(b'\0', p); v = d[p:e].decode('utf-8', 'replace'); p = e + 1; return v
        while True:
            ext = cstr()
            if not ext: break
            while True:
                path = cstr()
                if not path: break
                while True:
                    name = cstr()
                    if not name: break
                    crc, pre, arc, off, ln, term = struct.unpack_from('<IHHIIH', d, p); p += 18
                    preload = d[p:p + pre]; p += pre
                    full = ((path + '/') if path.strip() else '') + name + '.' + ext
                    s.files[full.lower()] = (arc, off, ln, preload)
    def has(s, path): return path.lower().replace('\\', '/') in s.files
    def archive_of(s, path):
        a = s.files.get(path.lower().replace('\\', '/'))
        return None if a is None else a[0]
    def read(s, path, archive_paths):
        arc, off, ln, pre = s.files[path.lower().replace('\\', '/')]
        if ln == 0: return pre
        if arc == 0x7fff:
            with open(s.path, 'rb') as f: f.seek(s.data_start + off); return pre + f.read(ln)
        with open(archive_paths[arc], 'rb') as f: f.seek(off); return pre + f.read(ln)
