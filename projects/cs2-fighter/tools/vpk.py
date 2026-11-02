"""Minimal VPK v2 directory reader: list files and locate them (archive index, offset, size)."""
import struct


def read_dir(path):
    d = open(path, "rb").read()
    sig, ver, tree_size = struct.unpack_from("<III", d, 0)
    assert sig == 0x55AA1234, hex(sig)
    hdr = 12 if ver == 1 else 28
    p = hdr
    end = hdr + tree_size

    def cstr():
        nonlocal p
        e = d.index(b"\0", p); s = d[p:e].decode("utf-8", "replace"); p = e + 1; return s

    files = {}
    while p < end:
        ext = cstr()
        if not ext: break
        while True:
            folder = cstr()
            if not folder: break
            while True:
                name = cstr()
                if not name: break
                crc, preload, arch, off, size, term = struct.unpack_from("<IHHIIH", d, p)
                p += 18
                pre = d[p:p + preload]; p += preload
                full = (folder.strip() + "/" if folder.strip() not in ("", " ") else "") + name + "." + ext
                files[full] = (arch, off, size, pre)
    return files, hdr + tree_size


_DIR_CACHE = {}


def extract(dirpath, name, archive_dir=None):
    """Return the bytes of one file, reading the archive chunk it lives in."""
    import os
    if dirpath not in _DIR_CACHE: _DIR_CACHE[dirpath] = read_dir(dirpath)
    files, data_off = _DIR_CACHE[dirpath]
    arch, off, size, pre = files[name]
    if arch == 0x7FFF:
        with open(dirpath, "rb") as fh:
            fh.seek(data_off + off); return pre + fh.read(size)
    base = os.path.basename(dirpath).replace("_dir.vpk", "")
    p = os.path.join(archive_dir or os.path.dirname(dirpath), f"{base}_{arch:03d}.vpk")
    with open(p, "rb") as fh:
        fh.seek(off); return pre + fh.read(size)
