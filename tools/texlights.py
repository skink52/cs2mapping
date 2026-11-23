"""Texture lights (lights.rad surfaces) for CS2, and the small CS:GO BSP reader the lighting passes share.

  python texlights.py <map.bsp> [--json]            report: texture lights, compiled lights, fully-bright check
  python texlights.py <addon> <root> [--bsp <map.bsp>] [--apply]   self-illum on the addon's vmats + light_rect list (dry run without --apply)

In Source 1 a material listed in lights.rad lit the map: vrad marked its faces (texinfo flag SURF_LIGHT) and put
surface lights (emit_surface) on them in the BSP's light list. Valve's importer keeps neither, so the area lit by
those panels comes out dark in CS2. This pass works out each material's emission from the BSP and

  - gives the addon's own csgo_complex vmat F_SELF_ILLUM with that brightness and colour (CS2 bakes emissive
    materials into the lightmaps; NOT in-game verified for ported maps), or
  - where the material can't glow (a stock CS2 material not in the addon, water / refract / unlit / other shaders),
    lists light_rect lights in front of its faces (`rect_lights`; the stage step adds them to the vmap).

Brightness: a texture light's surface lights are the same per unit area all over a material (rho, r g b). A big
surface of them lights what faces it with pi x rho (cosine-weighted 1/d^2 over a plane), in lightmap units where 1 is
the texture at full brightness; a CS2 self-illum surface of brightness e lights what faces it with about e, so
e = pi x rho. CS2 glows with tint x 2^SelfIllumBrightness, so brightness = log2(max(e)) and tint = e / max(e).

From CS2-Porter texlights.py (MIT, copyright bcanusar), adapted: our BSP reader (seek per lump, LZMA lumps), our vmat
rewriting (texfix-style insertion, existing self-illum masks kept), rect lights from the BSP faces themselves, a
dry-run report, and stock-material fallback to rect lights.
"""
import collections, json, math, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------ BSP reader (CS:GO VBSP 21; lumps read on demand)
LUMP_ENTITIES = 0
LUMP_PLANES = 1
LUMP_TEXDATA = 2
LUMP_VERTEXES = 3
LUMP_NODES = 5
LUMP_TEXINFO = 6
LUMP_FACES = 7
LUMP_LIGHTING = 8
LUMP_LEAFS = 10
LUMP_EDGES = 12
LUMP_SURFEDGES = 13
LUMP_MODELS = 14
LUMP_WORLDLIGHTS = 15
LUMP_PAKFILE = 40
LUMP_TEXDATA_STRING_DATA = 43
LUMP_TEXDATA_STRING_TABLE = 44
LUMP_LIGHTING_HDR = 53
LUMP_WORLDLIGHTS_HDR = 54
LUMP_FACES_HDR = 58

SURF_LIGHT = 0x1
SURF_SKY2D = 0x2
SURF_SKY = 0x4
SURF_NODRAW = 0x80
EMIT_SURFACE, EMIT_POINT, EMIT_SPOT, EMIT_SKYLIGHT, EMIT_QUAKELIGHT, EMIT_SKYAMBIENT = range(6)


class Bsp:
    """Lumps of a CS:GO .bsp, read with a seek each (BSPs here are 10-150 MB). `lump(i)` -> bytes (LZMA lumps
    decompressed), `size(i)`, `version(i)`, `entities()` -> [dict]."""

    def __init__(s, path):
        s.path = path
        with open(path, 'rb') as f:
            head = f.read(8 + 16 * 64 + 4)
        if head[:4] != b'VBSP':
            raise ValueError('not a BSP: %s' % path)
        s.bsp_version = struct.unpack_from('<i', head, 4)[0]
        s.lumps = [struct.unpack_from('<iiii', head, 8 + 16 * i) for i in range(64)]   # (offset, length, version, fourcc)
        s._cache = {}

    def size(s, i): return s.lumps[i][1]

    def version(s, i): return s.lumps[i][2]

    def lump(s, i):
        if i in s._cache: return s._cache[i]
        off, ln = s.lumps[i][:2]
        if ln <= 0: return b''
        with open(s.path, 'rb') as f:
            f.seek(off); raw = f.read(ln)
        if raw[:4] == b'LZMA':
            import lzma
            size, = struct.unpack_from('<I', raw, 4); props = raw[12:17]
            dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': struct.unpack('<I', props[1:5])[0],
                                                                    'lc': props[0] % 9, 'lp': (props[0] // 9) % 5, 'pb': props[0] // 45}])
            raw = dec.decompress(raw[17:], size)
        if i != LUMP_PAKFILE: s._cache[i] = raw
        return raw

    def entities(s):
        txt = s.lump(LUMP_ENTITIES).decode('latin-1', 'replace')
        out = []
        for block in re.findall(r'\{([^{}]*)\}', txt):
            out.append({k.lower(): v for k, v in re.findall(r'"([^"]*)"\s+"([^"]*)"', block)})
        return out

    def pakfile(s):
        """zipfile.ZipFile over the pakfile lump (read once into memory), or None."""
        import io, zipfile
        data = s.lump(LUMP_PAKFILE)
        if not data: return None
        try: return zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile: return None


def texinfo_list(b):
    """[(flags, material lower-case / separated)] per texinfo."""
    data, table = b.lump(LUMP_TEXDATA_STRING_DATA), b.lump(LUMP_TEXDATA_STRING_TABLE)
    names = []
    for o in range(0, len(table) - 3, 4):
        off = struct.unpack_from('<i', table, o)[0]
        end = data.find(b'\0', off)
        names.append(data[off:end if end >= 0 else len(data)].decode('latin-1').lower().replace('\\', '/'))
    texdata, texinfo = b.lump(LUMP_TEXDATA), b.lump(LUMP_TEXINFO)
    out = []
    for o in range(0, len(texinfo) - 71, 72):
        flags, td = struct.unpack_from('<ii', texinfo, o + 64)
        name = ''
        if 0 <= td and td * 32 + 16 <= len(texdata):
            idx = struct.unpack_from('<i', texdata, td * 32 + 12)[0]
            name = names[idx] if 0 <= idx < len(names) else ''
        out.append((flags, name))
    return out


def faces(b, want=None):
    """[(material, area, points, normal, texinfo flags)] of the world faces (LDR face lump, or the HDR one when only it
    exists). want(flags, material) -> bool filters by texinfo before the polygon is read."""
    tinfo = texinfo_list(b)
    fdata = b.lump(LUMP_FACES) or b.lump(LUMP_FACES_HDR)
    vdata, edata, sdata, pdata = b.lump(LUMP_VERTEXES), b.lump(LUMP_EDGES), b.lump(LUMP_SURFEDGES), b.lump(LUMP_PLANES)
    out = []
    for o in range(0, len(fdata) - 55, 56):
        pn, side, _on, first, num, ti = struct.unpack_from('<HBBihh', fdata, o)
        if not 0 <= ti < len(tinfo): continue
        flags, mat = tinfo[ti]
        if want is not None and not want(flags, mat): continue
        area = struct.unpack_from('<f', fdata, o + 24)[0]
        pts = []
        for k in range(num):
            se = struct.unpack_from('<i', sdata, (first + k) * 4)[0]
            a, c = struct.unpack_from('<2H', edata, abs(se) * 4)
            pts.append(struct.unpack_from('<3f', vdata, (a if se >= 0 else c) * 12))
        n = struct.unpack_from('<3f', pdata, pn * 20)
        if side: n = (-n[0], -n[1], -n[2])
        if len(pts) >= 3 and area > 0: out.append((mat, area, pts, n, flags))
    return out


def hdr_lit(b):
    return b.size(LUMP_LIGHTING_HDR) > 0


def world_lights(b, hdr=None):
    """The compiled light list: [{'origin', 'intensity' (r,g,b linear, vrad units), 'normal', 'type', 'style', 'stopdot',
    'stopdot2', 'exponent', 'radius', 'c', 'l', 'q', 'flags', 'texinfo'}]. HDR list when the map was compiled with HDR
    (that is what CS:GO drew), else LDR; hdr=True/False forces one."""
    idx = LUMP_WORLDLIGHTS
    if hdr is None: hdr = hdr_lit(b) and b.size(LUMP_WORLDLIGHTS_HDR) > 0
    if hdr: idx = LUMP_WORLDLIGHTS_HDR
    data = b.lump(idx)
    if not data: return []
    size = 100 if b.version(idx) >= 1 else 88
    if len(data) % size:
        size = 88 if len(data) % 88 == 0 else 100
        if len(data) % size: return []
    off = 12 if size == 100 else 0           # version 1 adds shadow_cast_offset after the normal
    out = []
    for o in range(0, len(data), size):
        org = struct.unpack_from('<3f', data, o); inten = struct.unpack_from('<3f', data, o + 12); nrm = struct.unpack_from('<3f', data, o + 24)
        _cluster, typ, style = struct.unpack_from('<3i', data, o + 36 + off)
        stopdot, stopdot2, exp, radius, c, l, q = struct.unpack_from('<7f', data, o + 48 + off)
        flags, texinfo, _owner = struct.unpack_from('<3i', data, o + 76 + off)
        out.append({'origin': org, 'intensity': inten, 'normal': nrm, 'type': typ, 'style': style, 'stopdot': stopdot,
                    'stopdot2': stopdot2, 'exponent': exp, 'radius': radius, 'c': c, 'l': l, 'q': q, 'flags': flags, 'texinfo': texinfo})
    return out


def lightmaps_lit(b):
    """False when the map has no baked light at all: no lightmap lumps, or only black luxels (ColorRGBExp32). Such a map
    was drawn fully bright in CS:GO (mat_fullbright-like: every surface shows its texture). From CS2-Porter lighting.py
    fullbright_map (MIT, copyright bcanusar), adapted."""
    for idx in (LUMP_LIGHTING, LUMP_LIGHTING_HDR):
        if b.size(idx) <= 0: continue
        data = b.lump(idx); n = len(data) - len(data) % 4
        try:
            import numpy as np
            if np.frombuffer(data, dtype=np.uint8, count=n).reshape(-1, 4)[:, :3].any(): return True
        except ImportError:
            if any(data[i] or data[i + 1] or data[i + 2] for i in range(0, n, 4)): return True
    return False


# ------------------------------------------------------------------ texture lights
GRID = 512.0
PLANE_EPS = 1.5
EDGE_EPS = 1.0
MIN_LIGHT = 0.05        # emission below this is no light worth keeping
PATCH_RE = re.compile(r'(_wvt_patch|_-?\d+_-?\d+_-?\d+)$')


def unpatched(mat):
    """The material a compiler-made copy (materials/maps/<map>/name_x_y_z, name_wvt_patch) was made from; others unchanged."""
    mm = re.match(r'(?:materials/)?maps/[^/]+/(.+)$', mat)
    if not mm: return mat
    return PATCH_RE.sub('', mm.group(1))


def _inside(p, pts, n):
    """p (on the plane) inside the convex polygon pts, either winding (the compiler winds water the other way)."""
    inner = outer = True
    for i, a in enumerate(pts):
        c = pts[(i + 1) % len(pts)]
        e = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        m = (n[1] * e[2] - n[2] * e[1], n[2] * e[0] - n[0] * e[2], n[0] * e[1] - n[1] * e[0])
        ln = math.sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2])
        if ln < 1e-6: continue
        d = ((p[0] - a[0]) * m[0] + (p[1] - a[1]) * m[1] + (p[2] - a[2]) * m[2]) / ln
        inner = inner and d >= -EDGE_EPS; outer = outer and d <= EDGE_EPS
        if not (inner or outer): return False
    return True


def texture_lights(b, with_faces=False):
    """{material (unpatched, no 'materials/' prefix): (r, g, b) emission e (linear; 1 = the texture at full brightness)}.
    with_faces=True returns (that dict, {material: [(points, normal)]} of the faces that carried surface lights)."""
    fl = faces(b, lambda flags, mat: flags & SURF_LIGHT and mat)
    if not fl: return ({}, {}) if with_faces else {}
    grid = collections.defaultdict(list)
    for i, (_m, _a, pts, _n, _f) in enumerate(fl):
        lo = [int(math.floor((min(p[k] for p in pts) - PLANE_EPS) / GRID)) for k in range(3)]
        hi = [int(math.floor((max(p[k] for p in pts) + PLANE_EPS) / GRID)) for k in range(3)]
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1): grid[(x, y, z)].append(i)
    power = collections.defaultdict(lambda: [0.0, 0.0, 0.0]); lit = set()
    for wl in world_lights(b):
        if wl['type'] != EMIT_SURFACE: continue
        org, inten = wl['origin'], wl['intensity']
        cell = tuple(int(math.floor(org[k] / GRID)) for k in range(3))
        for i in grid.get(cell, ()):
            mat, _a, pts, n, _f = fl[i]
            if abs(sum((org[k] - pts[0][k]) * n[k] for k in range(3))) > PLANE_EPS or not _inside(org, pts, n): continue
            acc = power[mat]
            for k in range(3): acc[k] += inten[k]
            lit.add(i); break
    area = collections.defaultdict(float)
    for i in lit: area[fl[i][0]] += fl[i][1]
    out, where = {}, collections.defaultdict(list)
    for mat, acc in power.items():
        if area[mat] <= 0: continue
        e = tuple(math.pi * v / area[mat] for v in acc)
        if max(e) >= MIN_LIGHT: out.setdefault(unpatched(mat), e)
    if with_faces:
        for i in lit:
            key = unpatched(fl[i][0])
            if key in out: where[key].append((fl[i][2], fl[i][3]))
        return out, dict(where)
    return out


def self_illum(e):
    """(tint with its largest part 1, Self Illum Brightness in doublings) that make a CS2 surface glow with e."""
    peak = max(e)
    if peak <= 0: return (1.0, 1.0, 1.0), 0.0
    return tuple(v / peak for v in e), max(-10.0, min(10.0, math.log2(peak)))


# ------------------------------------------------------------------ rect lights where a material can't glow
# CS2 point light: L lumens light a surface d away like a Source 1 light of L x LUMEN_SCALE / d^2, so 1 lumen per square unit is
# lightmap brightness 4 pi LUMEN_SCALE. Our scale (lighting.py, relight): 1000 lumens = a quadratic 265 _light, so LUMEN_SCALE =
# 1e4 x 265/255 / 1000 (CS2-Porter uses 200/255 for the same thing; see lighting.py lightcal for why ours is kept).
LUMEN_SCALE = 1e4 * (265.0 / 255.0) / 1000.0
LIGHTMAP_PER_LUX = 4.0 * math.pi * LUMEN_SCALE
RECT_TILE = 2048.0      # a surface is covered with squares about this big at most
RECT_MAX = 256          # lights for all surfaces together
RECT_MIN_GLOW = 0.02    # a light reaches as far as it lights brighter than this
RECT_MIN_SIDE = 4.0     # faces thinner than this get no light


def _axis_rect(pts, n):
    """(lo, hi, axis, sign) of an axis-aligned face, None for a slanted one."""
    ax = max(range(3), key=lambda k: abs(n[k]))
    if abs(n[ax]) < 0.99: return None
    lo = [min(p[k] for p in pts) for k in range(3)]; hi = [max(p[k] for p in pts) for k in range(3)]
    return lo, hi, ax, 1 if n[ax] > 0 else -1


def rect_lights(where, glow, limit=RECT_MAX):
    """light_rect specs in front of glowing faces whose material can't glow in CS2.
    where: {material: [(points, normal)]}; glow: {material: (r,g,b)}. Returns [{origin, angles, size, color, lumens,
    range, material}], at most `limit`, brightest materials first. Slanted faces are skipped (counted in 'skipped')."""
    out, skipped = [], 0
    for mat in sorted(where, key=lambda k: -max(glow.get(k, (0,)))):
        e = glow.get(mat)
        if not e or max(e) < MIN_LIGHT: continue
        peak = max(e)
        color = '%d %d %d' % tuple(int(round(255 * max(v, 0.0) / peak)) for v in e)
        for pts, n in where[mat]:
            r = _axis_rect(pts, n)
            if r is None: skipped += 1; continue
            lo, hi, axis, sign = r
            u, v = [k for k in range(3) if k != axis]
            width, height = hi[u] - lo[u], hi[v] - lo[v]
            if width < RECT_MIN_SIDE or height < RECT_MIN_SIDE: continue
            side = min(width, height, RECT_TILE)
            nu, nv = max(1, round(width / side)), max(1, round(height / side))
            w, h = width / nu, height / nv
            lumens = peak * w * h / LIGHTMAP_PER_LUX
            reach = math.sqrt(LIGHTMAP_PER_LUX * lumens / (math.pi * RECT_MIN_GLOW))   # on axis a small lambertian light gives L / (pi d^2)
            rng = max(256.0, min(8192.0, round(reach / 50.0) * 50.0))
            # light_rect shines along its +x: pitch/yaw that turn +x onto the face normal
            ang = {(2, 1): (-90.0, 0.0, 0.0), (2, -1): (90.0, 0.0, 0.0), (0, 1): (0.0, 0.0, 0.0), (0, -1): (0.0, 180.0, 0.0),
                   (1, 1): (0.0, 90.0, 0.0), (1, -1): (0.0, 270.0, 0.0)}[(axis, sign)]
            for i in range(nu):
                for j in range(nv):
                    c = list(lo); c[u] = lo[u] + (i + 0.5) * w; c[v] = lo[v] + (j + 0.5) * h; c[axis] = lo[axis] + 2.0 * sign
                    out.append({'origin': c, 'angles': ang, 'size': (w, h, u, v), 'color': color, 'lumens': lumens, 'range': rng, 'material': mat})
                    if len(out) >= limit: return out, skipped
    return out, skipped


# ------------------------------------------------------------------ apply to an addon (stage step)
NO_GLOW_SHADERS = ('water', 'refract', 'unlit', 'sky', 'static_overlay', 'decal')
SI_KEYS = ('F_SELF_ILLUM', 'g_flSelfIllumBrightness', 'g_flSelfIllumScale', 'g_vSelfIllumTint', 'g_flSelfIllumAlbedoFactor', 'TextureSelfIllumMask')
WHITE_MASK = 'materials/default/default_mask.tga'   # stock white mask (csgo_complex default)
LIGHT_NAME = 'texlight_rect'


def _vmat_text(c, rel):
    if rel in c.files: return c.files[rel].decode('utf-8', 'replace')
    p = os.path.join(c.content, rel)
    return open(p, encoding='utf-8', errors='replace').read() if os.path.exists(p) else None


def glow_vmat(txt, e):
    """vmat text with F_SELF_ILLUM set to glow e (r,g,b): the whole surface glows in the light's colour (albedo factor 0),
    an existing self-illum mask is kept (a $selfillum panel still glows only where it did). None when the shader can't glow."""
    ms = re.search(r'(?im)^\s*"?shader"?\s+"([^"]+)"\s*$', txt)
    if not ms or 'csgo_complex' not in ms.group(1).lower(): return None
    tint, bright = self_illum(e)
    mask = re.search(r'TextureSelfIllumMask"?\s+"([^"]+)"', txt)
    new = re.sub(r'(?im)^\s*"?(%s)"?\s+.*\n?' % '|'.join(SI_KEYS), '', txt)
    ins = ['F_SELF_ILLUM 1', 'g_flSelfIllumBrightness "%.3f"' % bright, 'g_flSelfIllumScale "1.000"',
           'g_vSelfIllumTint "[%.6f %.6f %.6f 0.000000]"' % tint, 'g_flSelfIllumAlbedoFactor "0.000"',
           'TextureSelfIllumMask "%s"' % (mask.group(1) if mask else WHITE_MASK.replace('/', '\\'))]
    ms = re.search(r'(?im)^\s*"?shader"?\s+"[^"]+"\s*$', new)
    return new[:ms.end()] + '\n\t// texlights: CS:GO lights.rad emission %.3f %.3f %.3f' % tuple(e) + ''.join('\n\t%s' % x for x in ins) + new[ms.end():]


def plan(m, c, b):
    """What `run` would do: ({vmat rel: new text}, [rect light specs], report lines)."""
    import assets
    glow, where = texture_lights(b, with_faces=True)
    used = {k[len('materials/'):-len('.vmat')]: k for k in assets.mesh_materials(m) if k.startswith('materials/') and k.endswith('.vmat')}
    edits, no_glow, rep = {}, {}, []
    for mat, e in sorted(glow.items()):
        tint, bright = self_illum(e)
        rel = used.get(mat)
        line = '%s: emission %.2f %.2f %.2f (brightness %.2f)' % (mat, e[0], e[1], e[2], bright)
        if rel is None:
            rep.append(line + ' - not on any vmap mesh (prop / overlay only, or renamed): skipped'); continue
        txt = _vmat_text(c, rel)
        new = glow_vmat(txt, e) if txt is not None else None
        if new is not None:
            edits[rel] = new; rep.append(line + ' -> F_SELF_ILLUM on %s' % rel)
        else:
            no_glow[mat] = where.get(mat, [])
            rep.append(line + (' - %s can\'t glow (shader)' % rel if txt is not None else ' - vmat not in the addon (stock CS2 material)') + ' -> light_rect')
    rects, skipped = rect_lights(no_glow, glow)
    if skipped: rep.append('%d slanted faces of materials that can\'t glow got no light_rect' % skipped)
    return edits, rects, rep


def add_rect_lights(m, rects):
    """light_rect entities for rect_lights() specs; returns the count added."""
    n = 0
    for i, r in enumerate(rects):
        w, h, u, v = r['size']
        # light_rect size_params: width height (in its local y / z); its local y/z follow the face's u/v axes closely
        # enough for a square-ish tile (tiles are cut to squares by rect_lights)
        side = math.sqrt(w * h)
        m.new_entity('light_rect', r['origin'], {
            'targetname': '%s_%d' % (LIGHT_NAME, i + 1), 'color': r['color'], 'colormode': '0', 'brightness_units': '1',
            'brightness_lumens': '%d' % max(1, round(r['lumens'])), 'range': '%g' % r['range'], 'directlight': '1',
            'castshadows': '1', 'shape': '0', 'size_params': '%.1f %.1f 0.15' % (side, side), 'enabled': '1', 'bouncelight': '1'},
            angles=r['angles'])
        n += 1
    return n


def find_bsp(c, bsp=None):
    """The map's BSP: the argument, $CS2PORT_BSP, or <root>/source1/maps/<addon>.bsp."""
    for p in (bsp, os.environ.get('CS2PORT_BSP'), os.path.join(c.root, 'source1', 'maps', c.addon + '.bsp')):
        if p and os.path.isfile(p): return p
    return None


def run(m, c, bsp=None, rects=True):
    """Stage step `texlights`: self-illum on texture-light vmats in the addon, light_rect where they can't glow."""
    p = find_bsp(c, bsp)
    if not p:
        c.todo.append('texlights: no BSP staged (<root>/source1/maps/%s.bsp): lights.rad texture lights not restored' % c.addon); return 0
    b = Bsp(p)
    edits, rl, rep = plan(m, c, b)
    if not edits and not rl and not rep: return 0
    for rel, txt in edits.items(): c.write(rel, txt)
    n = add_rect_lights(m, rl) if rects and rl else 0
    c.log.append('texlights: %d lights.rad texture-light materials -> F_SELF_ILLUM, %d light_rect added (%s)' % (len(edits), n, '; '.join(rep)[:1500]))
    if edits or n:
        c.todo.append('texlights: texture-light glow and light_rect brightness come from the CS:GO light list (e = pi x emission / area) and are '
                      'not in-game verified: compare a lit room with CS:GO after the bake')
    return len(edits) + n


# ------------------------------------------------------------------ CLI
def report(path):
    b = Bsp(path)
    tl = texture_lights(b)
    wl = world_lights(b)
    kinds = collections.Counter(w['type'] for w in wl)
    names = {EMIT_SURFACE: 'surface', EMIT_POINT: 'point', EMIT_SPOT: 'spot', EMIT_SKYLIGHT: 'sky', EMIT_QUAKELIGHT: 'quake', EMIT_SKYAMBIENT: 'skyambient'}
    return {'bsp': os.path.basename(path), 'hdr': hdr_lit(b), 'lightmaps_lit': lightmaps_lit(b),
            'world_lights': {names.get(k, str(k)): v for k, v in sorted(kinds.items())},
            'texture_lights': {k: [round(x, 3) for x in v] + [round(self_illum(v)[1], 2)] for k, v in sorted(tl.items())}}


def main(argv):
    if len(argv) >= 1 and argv[0].lower().endswith('.bsp'):
        r = report(argv[0])
        if '--json' in argv: print(json.dumps(r, indent=1)); return 0
        print('%s: HDR %s, lightmaps %s; light list %s' % (r['bsp'], r['hdr'], 'lit' if r['lightmaps_lit'] else 'NONE / all black (fully bright map)', r['world_lights']))
        for k, v in r['texture_lights'].items(): print('  %-60s emission %.3f %.3f %.3f  -> SelfIllumBrightness %.2f' % (k, *v))
        return 0
    if len(argv) < 2:
        print(__doc__); return 2
    addon, root = argv[0], argv[1]
    bsp = argv[argv.index('--bsp') + 1] if '--bsp' in argv else None
    import stage_c, vmapedit as V
    c = stage_c.Ctx(addon, root)
    m = V.Map(os.path.join(c.content, 'maps', addon + '.vmap'))
    p = find_bsp(c, bsp)
    if not p: print('no BSP: pass --bsp <map.bsp>'); return 1
    edits, rl, rep = plan(m, c, Bsp(p))
    print('\n'.join(rep)); print('%d vmats to change, %d light_rect' % (len(edits), len(rl)))
    if '--apply' not in argv: print('(dry run: --apply writes through run_pass.py texlights instead)'); return 0
    print('use: python run_pass.py %s %s texlights (keeps the backup rules of the stage passes)' % (addon, root)); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
