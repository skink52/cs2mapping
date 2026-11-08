"""Repack a compiled CS2 map vpk under a new map name without recompiling.

Every file from the old vpk is kept at its old path (world nodes, lightmaps and entity lumps stay in maps/<old>/). The engine
looks for maps/<name>.vmap_c, maps/<name>.nav and maps/<name>/world.vwrld (via the manifest world.vrman), so those and the
other top-level world files are added under the new name, with the new map file and manifests repointed at them.
Writes VPK v2 like the compiler: data embedded (archive index 0x7fff), 1 MiB chunk MD5s, tree/chunk/file MD5s,
and the compiler's empty 20-byte signature section.

usage: python rename_map_vpk.py <old.vpk> <new.vpk> <old_name> <new_name>
  e.g. python rename_map_vpk.py <CS2>/game/csgo_addons/<addon>/maps/ttt_island17_pezversion.vpk ttt_island.vpk ttt_island17_pezversion ttt_island
Then rename the side files (maps/<name>.txt, _cameras.txt, _retakes.txt, resource/overviews/<name>.txt and its key, the radar
panorama/images/overheadmaps/<name>_radar_psd.vtex_c) and delete the old vpk before uploading (docs/reference/cs2-gotchas.md).
The skybox vpk, postprocess and lighting files keep their names: the map refers to them by path. Needs `pip install vpk`.
The new name must not be longer than the old one. Test-load it before uploading. (8 Nov 2026, ttt_island17_pezversion -> ttt_island)
"""
# AI-generated (Claude, for skink52).
import hashlib, struct, sys, zlib
import vpk

# ---- Source 2 resource helpers
def blocks(b):
    hdr_ver, = struct.unpack_from('<H', b, 4)
    off, cnt = struct.unpack_from('<II', b, 8)
    base=8; out={}
    for i in range(cnt):
        p=base+off+i*12
        name=b[p:p+4].decode(); o,s=struct.unpack_from('<II', b, p+4)
        out[name]=(p+4+o, s)
    return out
def rerl(b):
    start,size=blocks(b)['RERL']
    off,cnt=struct.unpack_from('<II', b, start)
    es=start+off; res=[]
    for i in range(cnt):
        p=es+i*16
        rid,=struct.unpack_from('<Q', b, p); so,=struct.unpack_from('<I', b, p+8)
        sp=p+8+so; e=b.index(b'\0', sp)
        res.append((p, rid, sp, b[sp:e].decode()))
    return res
def murmur64b(key, seed=0xEDABCDEF):
    m=0x5bd1e995; r=24; n=len(key); U=0xffffffff
    h1=(seed ^ n)&U; h2=(seed>>32)&U; i=0; L=n
    def mix(h,k):
        k=(k*m)&U; k^=k>>r; k=(k*m)&U; h=(h*m)&U; return h^k
    while L>=8:
        h1=mix(h1,struct.unpack_from('<I',key,i)[0]); h2=mix(h2,struct.unpack_from('<I',key,i+4)[0]); i+=8; L-=8
    if L>=4:
        h1=mix(h1,struct.unpack_from('<I',key,i)[0]); i+=4; L-=4
    if L>0:
        h2^=int.from_bytes(key[i:i+L],'little'); h2=(h2*m)&U
    h1^=h2>>18; h1=(h1*m)&U; h2^=h1>>22; h2=(h2*m)&U
    h1^=h2>>17; h1=(h1*m)&U; h2^=h1>>19; h2=(h2*m)&U
    return (h1<<32)|h2

# ---- repack
src, dst, old, new = sys.argv[1:5]
v = vpk.open(src)
assert v.version == 2 and v.verify(), 'source vpk not a valid v2'
files = {n: v.get_file(n).read() for n in v}
for ext in ('vmap_c', 'nav'):
    o, n = f'maps/{old}.{ext}', f'maps/{new}.{ext}'
    if o in files:
        assert n not in files
        files[n] = files[o]
# the engine finds the world as maps/<map name>/world.vwrld (and its manifest, physics, vis next to it); those files
# reference the world nodes, lightmaps and entity lumps by their old absolute paths, which stay where they are
aliased = []
for p in [p for p in files if p.startswith(f'maps/{old}/') and p.count('/') == 2]:
    files[f'maps/{new}/' + p.split('/')[2]] = files[p]; aliased.append(p.split('/')[2][:-2])   # 'world.vrman' etc.

# The resource system only loads a world a manifest lists. In the new map file and the copied manifests, point the
# references to the copied top-level files at maps/<new>/: the path strings (RERL and DATA) are rewritten in place,
# padded with NULs (the new name must not be longer), and each RERL id is the path's MurmurHash64B (seed 0xEDABCDEF,
# checked against the compiler's ids and the engine's log).
assert len(new) <= len(old)
def repoint(blob):
    b = bytearray(blob); n = 0
    for leaf in aliased:
        o = f'maps/{old}/{leaf}'.encode(); nw = f'maps/{new}/{leaf}'.encode()
        i = 0
        while (i := b.find(o + b'\0', i)) >= 0:
            b[i:i + len(o)] = nw + b'\0' * (len(o) - len(nw)); n += 1; i += len(o)
    for p, rid, sp, s in rerl(bytes(b)):
        h = murmur64b(s.encode())
        if s.startswith(f'maps/{new}/'): struct.pack_into('<Q', b, p, h)
        else: assert h == rid, (s, hex(rid), hex(h))   # untouched refs: the hash function agrees with the compiler
    return bytes(b), n
for p in [f'maps/{new}.vmap_c'] + [f'maps/{new}/{a}_c' for a in aliased if a.endswith('.vrman')]:
    files[p], n = repoint(files[p]); print(f'  {p}: {n} path(s) repointed')

# tree: ext -> dir -> [name]
tree = {}
for path in files:
    d, _, fn = path.rpartition('/')
    name, _, ext = fn.rpartition('.')
    tree.setdefault(ext or ' ', {}).setdefault(d or ' ', []).append((name, path))

data = bytearray(); offsets = {}
for ext in sorted(tree):
    for d in sorted(tree[ext]):
        for name, path in sorted(tree[ext][d]):
            offsets[path] = len(data); data += files[path]

t = bytearray()
for ext in sorted(tree):
    t += ext.encode() + b'\0'
    for d in sorted(tree[ext]):
        t += d.encode() + b'\0'
        for name, path in sorted(tree[ext][d]):
            b = files[path]
            t += name.encode() + b'\0'
            t += struct.pack('<IHHIIH', zlib.crc32(b) & 0xffffffff, 0, 0x7fff, offsets[path], len(b), 0xffff)
        t += b'\0'
    t += b'\0'
t += b'\0'

CH = 1 << 20
chunks = bytearray()
for off in range(0, len(data), CH):
    part = data[off:off + CH]
    chunks += struct.pack('<III', 0x7fff, off, len(part)) + hashlib.md5(part).digest()

header = struct.pack('<7I', 0x55aa1234, 2, len(t), len(data), len(chunks), 48, 20)
tree_md5 = hashlib.md5(t).digest()
chunk_md5 = hashlib.md5(chunks).digest()
file_md5 = hashlib.md5(header + t + data + chunks + tree_md5 + chunk_md5).digest()
with open(src, 'rb') as f:
    f.seek(-20, 2); sig = f.read(20)
with open(dst, 'wb') as f:
    f.write(header + t + data + chunks + tree_md5 + chunk_md5 + file_md5 + sig)

w = vpk.open(dst)
assert w.verify(), 'written vpk fails verify'
for n in files:
    assert w.get_file(n).read() == files[n], n
print(f'{dst}: {len(files)} files ({len(files) - len(v.tree) if v.tree else "?"} added), verify ok')
