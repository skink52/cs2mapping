"""vmap_refs.py - build a refs list from the .vmap itself instead of trusting the importer's <addon>_refs.txt.

Walks the main vmap and every prefab vmap it references, collects every material (mesh faces, overlays, entity
keys ending in .vmat) and every model (entity keys ending in .vmdl), drops what already exists in the addon or in
CS2's stock pak01, and writes <addon>_vmap_refs.txt in the importer's "file" line format so post_import_cleanup.py
can import/convert the rest. Runs on the PC with Valve's python; needs dmx.py and kv2.py (C:\\source1\\cs2port\\tools).

    python vmap_refs.py <addon> [--steam-root <path>] [--all]

--all lists everything referenced (no present/stock filtering), for comparing against the importer's refs.
"""
import argparse, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, r'C:\source1\cs2port\tools'):
    if p not in sys.path: sys.path.insert(0, p)
import dmx

def norm(p): return p.decode() if isinstance(p, bytes) else p

def normpath(p): return norm(p).lower().replace('\\', '/').strip()

def vpk_tree(dir_path):
    """set of paths in a VPK directory, reading only the tree (CS2's pak01_dir.vpk is large)"""
    out = set()
    with open(dir_path, 'rb') as f:
        hdr = f.read(28); sig, ver, tree = struct.unpack_from('<III', hdr, 0)
        if sig != 0x55aa1234: return out
        f.seek(12 if ver == 1 else 28); d = f.read(tree)
    p = 0
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
                pre = struct.unpack_from('<H', d, p + 4)[0]; p += 18 + pre
                out.add((((path + '/') if path.strip() else '') + name + '.' + ext).lower())
    return out

class Scan:
    def __init__(s, content):
        s.content = content; s.mats = {}; s.mdls = {}; s.seen = set(); s.missing_prefabs = []
    def add(s, d, key, where):
        key = normpath(key)
        if key: d.setdefault(key, set()).add(where)
    def vmap(s, rel):
        rel = normpath(rel)
        if rel in s.seen: return
        s.seen.add(rel)
        path = os.path.join(s.content, rel.replace('/', os.sep))
        if not os.path.exists(path): s.missing_prefabs.append(rel); return
        raw = open(path, 'rb').read()
        if b'encoding keyvalues2' in raw[:80]:           # a fresh import is keyvalues2 text; Hammer saves binary
            import kv2; doc = kv2.loads(raw)
        else:
            doc = dmx.loads(raw)
        for e in doc.elements:
            t = e['type']
            if t == b'CDmePolygonMesh':
                for x in dmx.get(e, b'materials') or []: s.add(s.mats, x, rel)
            elif t == b'CMapEntity':
                props = doc.elements[dmx.get(e, b'entity_properties')] if isinstance(dmx.get(e, b'entity_properties'), int) else None
                if props is None: continue
                for name, at, v in props['attrs']:
                    if at != dmx.T_STR: continue
                    v = normpath(v)
                    if v.endswith('.vmdl'): s.add(s.mdls, v, rel)
                    elif v.endswith('.vmat'): s.add(s.mats, v, rel)
            elif t == b'CMapPrefab':
                for name, at, v in e['attrs']:
                    if at == dmx.T_STR and normpath(v).endswith('.vmap'): s.vmap(v)
        # overlays carry their own mesh (meshData -> CDmePolygonMesh), already covered by the mesh loop above

def exists_any_ext(root, rel):
    base = os.path.splitext(os.path.join(root, rel.replace('/', os.sep)))[0]
    d = os.path.dirname(base); n = os.path.basename(base).lower()
    if not os.path.isdir(d): return False
    return any(os.path.splitext(f)[0].lower() == n for f in os.listdir(d))

def build(addon, steam_root, everything=False):
    content = os.path.join(steam_root, 'content', 'csgo_addons', addon)
    s = Scan(content)
    s.vmap('maps/%s.vmap' % addon)
    stock = set()
    pak = os.path.join(steam_root, 'game', 'csgo', 'pak01_dir.vpk')
    if os.path.exists(pak): stock = vpk_tree(pak)
    mats, mdls, present = [], [], {'mat': 0, 'mdl': 0, 'stock': 0, 'tools': 0}
    for m in sorted(s.mats):
        if not m.endswith('.vmat'): continue
        if m.startswith('materials/tools/') or m.startswith('materials/dev/'): present['tools'] += 1; continue
        if not everything:
            if m + '_c' in stock or m in stock: present['stock'] += 1; continue
            if exists_any_ext(content, m): present['mat'] += 1; continue
        mats.append(m[:-5] + '.vmt')
    for m in sorted(s.mdls):           # models already in the addon stay listed: phase 1 skips the import and recompiles if out of date
        if not everything and m + '_c' in stock: present['stock'] += 1; continue
        if os.path.exists(os.path.join(content, m.replace('/', os.sep))): present['mdl'] += 1
        mdls.append(m[:-5] + '.mdl')
    out = os.path.join(content, 'maps', addon + '_vmap_refs.txt')
    with open(out, 'w') as f:
        f.write('// built by vmap_refs.py from %s.vmap + %d prefab(s)\n' % (addon, len(s.seen) - 1))
        for m in mdls: f.write('"file" "%s"\n' % m)
        for m in mats: f.write('"file" "%s"\n' % m)
    print('vmap_refs: %d vmaps scanned, %d materials / %d models referenced; already in addon %d materials / %d models, stock CS2 %d, tools %d'
          % (len(s.seen), len(s.mats), len(s.mdls), present['mat'], present['mdl'], present['stock'], present['tools']))
    print('vmap_refs: listed %d materials, %d models still needed -> %s' % (len(mats), len(mdls), out))
    for p in s.missing_prefabs: print('vmap_refs: !! prefab not found: %s' % p)
    return out, mats, mdls, s

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('addon'); ap.add_argument('--all', action='store_true')
    ap.add_argument('--steam-root', default=r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive')
    a = ap.parse_args()
    build(a.addon, a.steam_root, a.all)
