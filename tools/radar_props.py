"""Props on the radar: every prop_static / prop_dynamic / prop_physics in the vmap -> its upward-facing triangles (world space)
as extra floor polygons for radar.run(extra_polys=...), coloured with the average colour of the prop's texture.

Geometry comes from the CS:GO model (.mdl/.vvd/.dx90.vtx, mdlmesh.py): first the map's embedded files (<embedded dir>),
then CS:GO's pak01 VPK (only the archive chunks present locally). Textures: <embedded>/materials/<vmt>.vmt -> $basetexture
.vtf (vtf.py), same lookup in the VPK; no texture -> the radar's name-guessed colour. Models whose name says roof / ceiling /
cloud / skybox / mountain / tree canopy are left out so they don't cover the rooms under them (radar.run still drops prop tops
with no play space above them). Also writes the world materials' textures as PNGs (<embedded>/materials/<vmt path>.png)
so radartex finds them.

    polys = radar_props.polys(m, embedded_dir, csgo_vpk_dir_or_None, log=list)
From ba_jail_keimusho (31 Oct 2026)."""
import os, re, math, glob
import numpy as np
from PIL import Image
import vtf, mdlmesh

SKIP_NAMES = ('roof', 'ceiling', 'cloud', 'skybox', 'mountain', 'leaves', 'canopy', 'tree_d', 'sky_')
PROP_CLASSES = ('prop_static', 'prop_dynamic', 'prop_physics', 'prop_physics_override', 'prop_physics_multiplayer', 'prop_dynamic_override')

class Source:
    def __init__(s, emb, vpkdir):
        s.emb = emb; s.v = None; s.arcs = {}
        if vpkdir and os.path.exists(os.path.join(vpkdir, 'pak01_dir.vpk')):
            import vpk
            s.v = vpk.VPK(os.path.join(vpkdir, 'pak01_dir.vpk'))
            s.arcs = {int(f[6:9]): os.path.join(vpkdir, f) for f in os.listdir(vpkdir) if re.match(r'pak01_\d{3}\.vpk$', f)}
    def read(s, rel):
        p = os.path.join(s.emb, rel)
        if os.path.exists(p): return open(p, 'rb').read()
        if s.v and s.v.has(rel):
            a = s.v.archive_of(rel)
            if a == 0x7fff or a in s.arcs: return s.v.read(rel, s.arcs)
        return None

def _vmt_base(txt):
    m = re.search(r'"?\$basetexture"?\s+"?([^"\s]+)', txt, re.I)
    return m.group(1).replace('\\', '/').lower() if m else None

_col = {}
def texture_rgb(src, mat):
    """average RGB of a material's base texture, or None"""
    if mat in _col: return _col[mat]
    out = None
    vmt = src.read('materials/%s.vmt' % mat)
    if vmt:
        base = _vmt_base(vmt.decode('latin1'))
        data = src.read('materials/%s.vtf' % base) if base else None
        if data:
            try:
                im = vtf.decode(data).convert('RGB')
                out = tuple(int(x) for x in np.asarray(im.resize((16, 16))).reshape(-1, 3).mean(0))
            except Exception: out = None
    _col[mat] = out
    return out

def world_textures(m, src, out_dir):
    """PNG of each world material's base texture at <out_dir>/<material path>.png (radartex index)"""
    import lighting
    n = 0
    for mat in sorted({mt for mt, _ in lighting.world_polys(m)}):
        rel = re.sub(r'^materials/', '', mat)[:-5] if mat.endswith('.vmat') else mat
        dst = os.path.join(out_dir, rel + '.png')
        if os.path.exists(dst): continue
        vmt = src.read('materials/%s.vmt' % rel)
        base = _vmt_base(vmt.decode('latin1')) if vmt else None
        data = src.read('materials/%s.vtf' % base) if base else None
        if not data: continue
        try:
            im = vtf.decode(data).convert('RGB')
            os.makedirs(os.path.dirname(dst), exist_ok=True); im.save(dst); n += 1
        except Exception: pass
    return n

def rot(ang):
    p, y, r = (math.radians(a) for a in ang)
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return np.array([[cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
                     [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
                     [-sp, sr * cp, cr * cp]])

def polys(m, emb, vpkdir=None, log=None):
    import radartex
    src = Source(emb, vpkdir)
    cache = {}; out = []; used = missing = skipped = 0
    for e in m.entities():
        if m.cls(e) not in PROP_CLASSES: continue
        mdl = (m.P(e, 'model') or '').lower().replace('\\', '/')
        if not mdl or any(k in mdl for k in SKIP_NAMES): skipped += 1; continue
        base = re.sub(r'\.vmdl$', '', mdl)
        if base not in cache:
            a, b, c = src.read(base + '.mdl'), src.read(base + '.vvd'), src.read(base + '.dx90.vtx')
            try: sk = int(float(m.P(e, 'skin', '0') or 0))
            except ValueError: sk = 0                  # CS2 writes skin = "default"
            try: cache[base] = mdlmesh.mesh(a, b, c, sk) if a and b and c else None
            except Exception: cache[base] = None
        meshes = cache[base]
        if not meshes: missing += 1; continue
        sc = np.array(m.g(e, b'scales', [1, 1, 1]), float)
        R = rot(m.g(e, b'angles', [0, 0, 0])); o = np.array(m.origin(e), float)
        for mat, T in meshes:
            W = (T.reshape(-1, 3) * sc) @ R.T + o
            W = W.reshape(-1, 3, 3)
            n = np.cross(W[:, 1] - W[:, 0], W[:, 2] - W[:, 0]); ln = np.linalg.norm(n, axis=1)
            up = (ln > 1e-6) & (n[:, 2] > 0.6 * np.maximum(ln, 1e-9))
            if not up.any(): continue
            rgb = texture_rgb(src, mat) or radartex.guess_colour(mat)
            key = '#rgb:%d,%d,%d' % tuple(rgb)
            out.extend((key, t) for t in W[up])
        used += 1
    if log is not None:
        log.append('radar props: %d props drawn (%d up-facing triangles), %d without model files, %d skipped by name (roof/ceiling/sky/canopy)' % (used, len(out), missing, skipped))
    return out
