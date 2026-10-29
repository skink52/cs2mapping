"""Texture-mapping repairs after Valve's map importer, done on the vmap elements (stage C steps / stage D passes).

overlay_geometry  static overlays the importer left as its 2x2 placeholder quad (CMapStaticOverlay, from CS:GO infodecal /
                  info_overlay) are rebuilt from the decompiled VMF: size = CS:GO texture x $decalscale (infodecal) or the
                  overlay's own uv0..uv3 extent (info_overlay), laid on the brush face under the decal, texture the right way up.
                  depth=N also sets every overlay's projection depth (the importer sometimes writes 64: a 2x2x64 box, overlay invisible).
face_scales       brush faces whose texture mapping the importer got wrong: matched to a VMF side (see face_scales), absurd scales (<0.01 or >8) put back to the VMF
                  side's scale/axes/shift, and stored texture coordinates (what Hammer and the compiler actually draw) are
                  rewritten from the Source 1 formula u = (P.axisU / scaleU + shiftU) / texture width.
material_flags    CS:GO $additive / $nocull / $ssbump that the importer dropped or got wrong: csgo_unlitgeneric F_BLEND_MODE 4 (LIT_ADDITIVE:
                  lightmapped stays lit with F_TRANSLUCENT + F_ADDITIVE_BLEND), F_RENDER_BACKFACES (+ F_DONT_FLIP_BACKFACE_NORMALS on lit
                  shaders), and $ssbump bump maps rebuilt as real normal maps.

Method from github.com/Ninja-Chris/cs2-slop-porting (vmap_asset_slop_import.py), reimplemented for this pipeline's vmap model.
"""
import os, re, math, struct, collections
import dmx, vmf as vmfmod

NORMAL_OFFSET = 4.0          # the importer puts an overlay origin this far off the surface
MATCH_RADIUS = 40.0          # importer moves an overlay ~16 units from the VMF decal; hand-moved ones can be further
BAD_RATIO = (0.75, 1.5)      # vmap scale / vmf scale outside this = broken (axis normalisation alone gives up to ~1.3)

# ------------------------------------------------------------------ vectors
def sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a):
    n = math.sqrt(dot(a, a)) or 1.0
    return [x / n for x in a]
def vec(s, n=3):
    try: return [float(x) for x in str(s).replace('[', ' ').replace(']', ' ').split()[:n]]
    except ValueError: return None

def angles_from_axes(x, z):
    """Source QAngle whose forward is x and up is z"""
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, -x[2]))))
    yaw = math.degrees(math.atan2(x[1], x[0])) if abs(x[0]) + abs(x[1]) > 1e-6 else 0.0
    cp, sp, cy, sy = math.cos(math.radians(pitch)), math.sin(math.radians(pitch)), math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    best = (9.0, 0.0)
    for r10 in range(-1800, 1800):
        r = r10 / 10.0; cr, sr = math.cos(math.radians(r)), math.sin(math.radians(r))
        up = [cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp]
        e = sum((up[k] - z[k]) ** 2 for k in range(3))
        if e < best[0]: best = (e, r)
    return [round(pitch, 2) + 0.0, round(yaw, 2) + 0.0, round(best[1], 2) + 0.0]

def angle_axes(a):
    p, y, r = [math.radians(v) for v in a]
    return ([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)],
            [math.cos(r) * math.sin(p) * math.cos(y) + math.sin(r) * math.sin(y), math.cos(r) * math.sin(p) * math.sin(y) - math.sin(r) * math.cos(y), math.cos(r) * math.cos(p)])

def matkey(s):
    """'materials/a b/c.vmat' / 'A B/C' -> 'a_b/c' (the importer turns spaces into underscores)"""
    s = s.lower().replace('\\', '/')
    if s.startswith('materials/'): s = s[10:]
    if s.endswith('.vmat') or s.endswith('.vmt'): s = s.rsplit('.', 1)[0]
    return s.replace(' ', '_')

# ------------------------------------------------------------------ VMF
def _disp_reach(sd):
    """how far a displacement's surface can sit off its base face: |elevation| + largest |distance| + largest |offset|"""
    di = next((x for x in sd.ch if x.name == 'dispinfo'), None)
    if di is None: return None
    def rows(name, step):
        blk = next((x for x in di.ch if x.name == name), None); out = []
        for _, v in (blk.items() if blk else []):
            try: f = [float(t) for t in v.split()]
            except ValueError: continue
            out += [math.sqrt(sum(q * q for q in f[i:i + step])) for i in range(0, len(f) - step + 1, step)]
        return max(out) if out else 0.0
    try: el = abs(float(di.get('elevation', 0) or 0))
    except ValueError: el = 0.0
    return el + rows('distances', 1) + rows('offsets', 3) + 2.0

def vmf_brushes(root):
    """[sides] per convex brush; side = dict(n, d, mat, ua, va, us, vs, bb=(min, max) of the brush, disp=reach or None); planes point outward"""
    out = []
    def walk(node):
        for ch in node.ch:
            if ch.name == 'solid':
                sides = []; pts = []
                for sd in ch.ch:
                    if sd.name != 'side': continue
                    pl = [vec(t) for t in re.findall(r'\(([^)]*)\)', sd.get('plane', ''))]
                    if len(pl) != 3 or None in pl: continue
                    n = norm(cross(sub(pl[1], pl[0]), sub(pl[2], pl[0]))); pts += pl
                    ua = re.match(r'\[([^\]]*)\]\s*(\S+)', sd.get('uaxis', '')); va = re.match(r'\[([^\]]*)\]\s*(\S+)', sd.get('vaxis', ''))
                    s = dict(n=n, d=dot(n, pl[0]), mat=matkey(sd.get('material', '')), disp=_disp_reach(sd))
                    if ua and va:
                        try: s.update(ua=vec(ua.group(1), 4), va=vec(va.group(1), 4), us=float(ua.group(2)), vs=float(va.group(2)))
                        except (ValueError, TypeError): pass
                    sides.append(s)
                if sides and pts:
                    cen = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
                    bb = ([min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)])
                    for s in sides:
                        s['bb'] = bb
                        if dot(s['n'], cen) - s['d'] > 0: s['n'] = [-x for x in s['n']]; s['d'] = -s['d']
                    out.append(sides)
            elif ch.name in ('world', 'entity'):
                walk(ch)
    walk(root)
    return out

def surface_under(brushes, p, tol=3.0):
    best = None
    for sides in brushes:
        for s in sides:
            if s['mat'].startswith('tools/') and 'nodraw' not in s['mat']: continue
            d = dot(s['n'], p) - s['d']
            if abs(d) > tol: continue
            q = [p[k] - s['n'][k] * d for k in range(3)]
            if all(dot(o['n'], q) - o['d'] <= 1.0 for o in sides):
                if best is None or abs(d) < best[0]: best = (abs(d), s['n'], q)
    return (best[1], best[2]) if best else None

# ------------------------------------------------------------------ Source 1 texture sizes
def _vmt_kv(raw):
    import assets
    return assets.parse_vmt(raw.decode('utf-8', 'replace'))

def _read_src(c, rel):
    rel = rel.lower()
    if c.src is not None:
        try:
            if c.src.has(rel): return c.src.read(rel)
        except Exception: return None
        return None
    p = os.path.join(c.root, 'embedded', c.addon, rel)
    return open(p, 'rb').read() if os.path.exists(p) else None

def load_vmt(c, vmt):
    raw = _read_src(c, vmt)
    if raw is None: return None, None
    shader, kv = _vmt_kv(raw)
    if shader == 'patch' and kv.get('include'):
        r2 = _read_src(c, kv['include'].replace('\\', '/'))
        if r2 is not None:
            s2, kv2 = _vmt_kv(r2); shader = s2; kv = {**kv2, **kv}
    return shader, kv

def _addon_size(c, k, base):
    vp = k if k.endswith('.vmat') else base + '.vmat'
    txt = c.files[vp].decode('utf-8', 'replace') if vp in c.files else (open(os.path.join(c.content, vp), encoding='utf-8', errors='replace').read() if os.path.exists(os.path.join(c.content, vp)) else '')
    mc = re.search(r'TextureColor"?\s+"([^"]+)"', txt)
    if not mc: return None
    rel = mc.group(1).replace('\\', '/')
    try:
        from PIL import Image
        if rel in c.files:
            import io as _io
            return Image.open(_io.BytesIO(c.files[rel])).size + (1.0,)
        cp = os.path.join(c.content, rel)
        if os.path.exists(cp): return Image.open(cp).size + (1.0,)
    except Exception: pass
    return None

def tex_size(c, mat, addon_first=False):
    """(width, height, $decalscale) of the CS:GO texture behind a material, else the addon's colour texture size, else None.
    addon_first: the addon's converted colour texture wins (it is what Hammer draws the stored texture coordinates against)"""
    cache = c.__dict__.setdefault('_texsize', {})
    k = mat.lower().replace('\\', '/')
    base = 'materials/' + matkey(k) if not k.startswith('materials/') else k.rsplit('.', 1)[0]
    if addon_first:
        ck = ('addon', k)
        if ck not in cache: cache[ck] = _addon_size(c, k, base) or tex_size(c, mat)
        return cache[ck]
    if k in cache: return cache[k]
    r = None
    shader, kv = load_vmt(c, base + '.vmt')
    if kv is not None:
        bt = (kv.get('$basetexture') or '').lower().replace('\\', '/')
        if bt:
            if bt.endswith('.vtf'): bt = bt[:-4]
            v = _read_src(c, 'materials/' + bt + '.vtf')
            if v is not None and v[:4] == b'VTF\0':
                w, h = struct.unpack_from('<HH', v, 16)
                try: ds = float(kv.get('$decalscale') or 1)
                except ValueError: ds = 1.0
                r = (w, h, ds)
    if r is None: r = _addon_size(c, k, base)
    cache[k] = r
    return r

# ------------------------------------------------------------------ mesh helpers
def stream(m, arr_el, prefix):
    if arr_el is None or arr_el < 0: return None
    for st in m.g(arr_el, b'streams') or []:
        if m.E[st]['name'].lower().startswith(prefix): return m.g(st, b'data')
    return None

# ------------------------------------------------------------------ static overlays
def _vmf_decals(root):
    out = []
    for e in root.ch:
        if e.name != 'entity': continue
        cl = (e.get('classname') or '').lower()
        if cl == 'infodecal' and e.get('texture'):
            out.append(dict(kind='decal', tex=matkey(e.get('texture')), o=vec(e.get('origin', '0 0 0')), yaw=(vec(e.get('angles', '0 0 0')) or [0, 0, 0])[1], used=False))
        elif cl == 'info_overlay' and e.get('material'):
            bo, bn, bu, bv = (vec(e.get(k, '')) for k in ('BasisOrigin', 'BasisNormal', 'BasisU', 'BasisV'))
            uv = [vec(e.get('uv%d' % i, '')) for i in range(4)]
            if None in (bo, bn, bu, bv) or None in uv:
                bo = vec(e.get('origin', '0 0 0')); bn = None
            d = dict(kind='overlay', tex=matkey(e.get('material')), o=bo, used=False, n=bn, u=bu, v=bv, uv=uv)
            try: d['st'] = [float(e.get(k, dflt)) for k, dflt in (('StartU', 0), ('EndU', 1), ('StartV', 0), ('EndV', 1))]
            except ValueError: d['st'] = [0.0, 1.0, 0.0, 1.0]
            out.append(d)
    return out

def is_placeholder(pos):
    return pos is not None and len(pos) == 4 and all(abs(abs(q[0]) - 1) < 1e-3 and abs(abs(q[1]) - 1) < 1e-3 for q in pos)

def overlay_geometry(m, c, vmfpath, depth=None, only_placeholders=True):
    if not os.path.exists(vmfpath): return
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    brushes = vmf_brushes(root); decals = _vmf_decals(root)
    fixed, nomatch, notex, nosurf, deep, depthset = [], 0, set(), 0, 0, 0
    total = 0
    for n, _ in m.walk():
        if m.type(n) != b'CMapStaticOverlay': continue
        total += 1
        el = m.E[n]; md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        mats = [x.decode() for x in m.g(md, b'materials') or []]
        mat = mats[0].lower().replace('\\', '/') if mats else ''
        pos = stream(m, m.g(md, b'vertexData'), b'position')
        pf = m.g(n, b'projectionFar')
        if depth is not None and isinstance(pf, float) and abs(pf - depth) > 1e-3:
            dmx.set_(el, b'projectionFar', dmx.T_FLOAT, float(depth)); depthset += 1
        elif isinstance(pf, float) and pf >= 32: deep += 1
        if only_placeholders and not is_placeholder(pos): continue
        o = list(m.g(n, b'origin', [0, 0, 0])); key = matkey(mat)
        cand = [d for d in decals if not d['used'] and d['tex'] == key and d['o'] and sum((d['o'][k] - o[k]) ** 2 for k in range(3)) < MATCH_RADIUS ** 2]
        if not cand: nomatch += 1; continue
        d = min(cand, key=lambda q: sum((q['o'][k] - o[k]) ** 2 for k in range(3))); d['used'] = True
        st = [0.0, 1.0, 0.0, 1.0]
        if d['kind'] == 'overlay' and d.get('n'):
            nrm = norm(d['n']); U = norm(sub(d['u'], [nrm[k] * dot(d['u'], nrm) for k in range(3)])); V = norm(cross(nrm, U))
            Vs = d['v'] if dot(d['v'], V) >= 0 else [-x for x in d['v']]
            xs = [q[0] for q in d['uv']]; ys = [q[1] for q in d['uv']]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            cu, cv = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
            surf = [d['o'][k] + U[k] * cu + norm(Vs)[k] * cv for k in range(3)]
            st = d['st']
            if w < 0.5 or h < 0.5: notex.add(mat + ' (info_overlay with no uv extent)'); continue
        else:
            ts = tex_size(c, mat)
            if not ts: notex.add(mat); continue
            w, h = ts[0] * ts[2], ts[1] * ts[2]
            sh = surface_under(brushes, d['o'])
            if not sh: nosurf += 1; continue
            nrm, surf = sh
            if abs(nrm[2]) > 0.9:
                a = math.radians(d.get('yaw', 0.0)); x = [math.cos(a), math.sin(a), 0.0]
                U = norm(sub(x, [nrm[k] * dot(x, nrm) for k in range(3)]))
            else:
                U = norm(cross([0.0, 0.0, 1.0], nrm))
        # CS2 projects along local +Z, so Z points into the surface; X = -texture right (corner signs map u so the image isn't mirrored)
        X = [-q for q in U]; Z = [-q for q in nrm]
        ang = angles_from_axes(X, Z)
        neworg = [surf[k] + nrm[k] * NORMAL_OFFSET for k in range(3)]
        dmx.set_(el, b'origin', dmx.T_V3, neworg); dmx.set_(el, b'angles', dmx.T_QANG, ang)
        if m.g(n, b'scales') is not None: dmx.set_(el, b'scales', dmx.T_V3, [1.0, 1.0, 1.0])
        signs = []
        for q in pos:
            sx, sy = (1 if q[0] > 0 else -1), (1 if q[1] > 0 else -1)
            signs.append((sx, sy)); q[0], q[1], q[2] = sx * w / 2, sy * h / 2, 0.0
        tc = stream(m, m.g(md, b'faceVertexData'), b'texcoord')
        evi = m.g(md, b'edgeVertexIndices') or []; efi = m.g(md, b'edgeFaceIndices') or []
        evd = m.g(md, b'edgeVertexDataIndices') or list(range(len(evi))); vdi = m.g(md, b'vertexDataIndices') or list(range(len(pos)))
        if tc is not None:
            for he, vi in enumerate(evi):
                if he >= len(efi) or efi[he] < 0 or vi >= len(vdi) or vdi[vi] >= len(signs) or he >= len(evd) or evd[he] >= len(tc): continue
                sx, sy = signs[vdi[vi]]
                fu, fv = (1 - sx) / 2, (1 - sy) / 2
                tc[evd[he]][0] = st[0] + (st[1] - st[0]) * fu; tc[evd[he]][1] = st[2] + (st[3] - st[2]) * fv
        fixed.append('%s %gx%g' % (os.path.basename(mat)[:-5], round(w, 1), round(h, 1)))
    if fixed:
        cnt = collections.Counter(fixed)
        c.log.append('static overlays: %d of %d importer placeholder quads rebuilt from the VMF (size from the CS:GO texture x $decalscale or the info_overlay uv, laid on the surface): %s'
                     % (len(fixed), total, ', '.join(('%s x%d' % (k, v)) if v > 1 else k for k, v in sorted(cnt.items()))[:900]))
    if depthset: c.log.append('static overlays: projection depth set to %g on %d overlays' % (depth, depthset))
    if deep: c.todo.append('%d static overlays have a projection depth >= 32 (can show as a box with the overlay invisible) - stage_d overlaydepth sets them to 8' % deep)
    if nomatch: c.todo.append('%d placeholder static overlays had no infodecal/info_overlay of the same material within %d units in the VMF - size them by hand (scale = size/2)' % (nomatch, MATCH_RADIUS))
    if nosurf: c.todo.append('%d placeholder static overlays: no brush face under the VMF decal (on a displacement or model?) - left as placeholders' % nosurf)
    if notex: c.todo.append('placeholder static overlays left alone, no CS:GO texture size: %s' % ', '.join(sorted(notex))[:600])

# ------------------------------------------------------------------ brush face texture scales
def _bad(sc): return min(abs(sc[0]), abs(sc[1])) < 0.01 or max(abs(sc[0]), abs(sc[1])) > 8

PLANE_TOL = 0.6   # every face corner within this of the VMF side's plane (importer leaves corners ~0.1 off; measuring at one corner tilted d by 1.5-3u)
ROUND_TOL = 2.5   # rounded/bevelled corners: corners up to this far off the plane, normals agree, centre inside the brush
PUSH_TOL = 6.0    # flat faces parallel to a side but pushed out up to this far (all corners the same distance off)
SLIVER = 1.0      # triangles thinner than this are matched by their corners only (their own normal is noise)

def _face_normal(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
    n = norm(n)
    for k in range(3):
        if abs(n[k]) > 0.999: return [0.0 if j != k else math.copysign(1.0, n[k]) for j in range(3)]
    return n

def _thickness(pts):
    if len(pts) != 3: return 1e9
    e = [sub(pts[(i + 1) % 3], pts[i]) for i in range(3)]
    cr = cross(e[0], e[1])
    return math.sqrt(dot(cr, cr)) / (max(math.sqrt(dot(x, x)) for x in e) or 1.0)

def _inside(s, p, tol=0.6):
    """p inside the brush of side s, ignoring s's own plane"""
    return all(dot(o['n'], p) - o['d'] <= tol for o in s['solid'] if o is not s)

def _same_map(a, b):
    return (max(abs(a['ua'][k] - b['ua'][k]) + abs(a['va'][k] - b['va'][k]) for k in range(4)) < 0.01
            and abs(a['us'] - b['us']) < 1e-4 and abs(a['vs'] - b['vs']) < 1e-4)

def _moved(s, t):
    """side s of a brush copied and moved by t in Hammer with texture lock: plane moved, shift corrected so the texture stays put on the brush"""
    r = dict(s); r['d'] = s['d'] + dot(s['n'], t); r['moved'] = t
    r['ua'] = s['ua'][:3] + [s['ua'][3] - dot(s['ua'][:3], t) / s['us']]
    r['va'] = s['va'][:3] + [s['va'][3] - dot(s['va'][:3], t) / s['vs']]
    return r

def face_scales(m, c, vmfpath):
    """Faces are matched to a VMF side, first try wins: same plane + material (slivers by corners only; a renamed material = the one VMF
    material with the same file name) -> a moved copy of a VMF brush of the same size (texture lock) -> rounded corners (2.5u) -> pushed-off
    faces (6u) -> a displacement's base face -> (absurd scales only) a side of another material on the same plane."""
    lo, hi = BAD_RATIO
    sides, brushes = [], []
    if os.path.exists(vmfpath):
        for br in vmf_brushes(vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())):
            ok = False
            for s in br:
                s['solid'] = br
                if 'us' in s and s.get('ua') and s.get('va') and len(s['ua']) == 4 and len(s['va']) == 4 and s['us'] and s['vs']:
                    sides.append(s); ok = True
                else: s['nomap'] = True
            if ok: brushes.append(br)
    idx = collections.defaultdict(lambda: collections.defaultdict(list)); allidx = collections.defaultdict(list)
    disp = collections.defaultdict(list); byname = collections.defaultdict(set); bysize = collections.defaultdict(list)
    for s in sides:
        idx[s['mat']][math.floor(s['d'])].append(s); allidx[math.floor(s['d'])].append(s); byname[s['mat'].rsplit('/', 1)[-1]].add(s['mat'])
        if s['disp']: disp[s['mat']].append(s)
    for br in brushes:
        bb = br[0]['bb']; bysize[tuple(round(bb[1][k] - bb[0][k]) for k in range(3))].append(br)
    vmf_scales = collections.defaultdict(collections.Counter)
    for s in sides: vmf_scales[s['mat']][(round(s['us'], 4), round(s['vs'], 4))] += 1

    def near(pool, d, tol):
        r, seen = int(math.ceil(tol)) + 2, set()
        for c_ in {math.floor(d), math.floor(-d)}:
            for b in range(c_ - r, c_ + r + 1):
                for s in pool.get(b, ()):
                    if id(s) not in seen: seen.add(id(s)); yield s

    def on_plane(s, pts, tol): return all(abs(dot(s['n'], p) - s['d']) <= tol for p in pts)
    def par(s, nrm): return abs(dot(s['n'], nrm)) > 0.999

    def pick(cands, cen, u0, v0, sc0):
        if len(cands) > 1:
            c0 = [s for s in cands if 'moved' not in s and _inside(s, cen)]
            if c0: cands = c0
        if len(cands) > 1:
            c1 = [s for s in cands if sum(abs(s['ua'][k] - u0[k]) + abs(s['va'][k] - v0[k]) for k in range(3)) < 0.02]
            if c1: cands = c1
            if len(cands) > 1:
                c2 = [s for s in cands if all(min((s[ax][3] - cur[3]) % 16.0, 16.0 - (s[ax][3] - cur[3]) % 16.0) < 0.1 for ax, cur in (('ua', u0), ('va', v0)))]
                if c2: cands = c2
        sd = min(cands, key=lambda s: abs(sc0[0] / s['us'] - 1) + abs(sc0[1] / s['vs'] - 1))
        return sd, (sd if all(_same_map(s, sd) for s in cands) else None)

    def match(key, pts, nrm, cen, sliver, moves):
        d = dot(nrm, cen); pool = idx.get(key, {})
        cands = [s for s in near(pool, d, PLANE_TOL) if (sliver or par(s, nrm)) and on_plane(s, pts, PLANE_TOL)]
        inside = [s for s in cands if _inside(s, cen, 1.0)]
        if inside: return inside, 'same plane'
        mv = [ms for t, br in moves for ms in (_moved(s, t) for s in br if s['mat'] == key and 'nomap' not in s and (sliver or par(s, nrm))) if on_plane(ms, pts, PLANE_TOL)]
        if mv: return mv, 'moved copy of a VMF brush (texture lock)'
        if cands: return cands, 'same plane (outside the brush)'
        if not sliver:
            cands = [s for s in near(pool, d, ROUND_TOL) if par(s, nrm) and on_plane(s, pts, ROUND_TOL) and _inside(s, cen)]
            if cands: return cands, 'rounded corner (<= %gu off the plane)' % ROUND_TOL
            best = []
            for s in near(pool, d, PUSH_TOL):
                if not par(s, nrm): continue
                offs = [dot(s['n'], p) - s['d'] for p in pts]
                if max(offs) - min(offs) > PLANE_TOL: continue
                off = sum(offs) / len(offs)
                if not (PLANE_TOL < abs(off) <= PUSH_TOL): continue
                if _inside(s, [cen[k] - s['n'][k] * off for k in range(3)]): best.append((round(abs(off), 1), s))
            if best:
                mn = min(b[0] for b in best)
                return [s for o, s in best if o <= mn + 0.1], 'pushed off its plane (<= %gu)' % PUSH_TOL
        cands = []
        for s in disp.get(key, ()):
            off = dot(s['n'], cen) - s['d']
            if abs(off) <= s['disp'] and _inside(s, [cen[k] - s['n'][k] * off for k in range(3)], 1.0): cands.append(s)
        if cands: return cands, 'displacement (base face mapping)'
        return [], None

    faces = []; stat = collections.Counter(); renamed = collections.Counter()
    for node, _ in m.walk():
        if m.type(node) != b'CMapMesh': continue
        md = m.g(node, b'meshData')
        if md is None or md < 0: continue
        o = m.g(node, b'origin', [0, 0, 0])
        ident = all(abs(x) < 1e-4 for x in m.g(node, b'angles', [0, 0, 0])) and all(abs(x - 1) < 1e-4 for x in m.g(node, b'scales', [1, 1, 1]))
        mats = [x.decode().lower().replace('\\', '/') for x in m.g(md, b'materials') or []]
        fd = m.g(md, b'faceData')
        scs, us, vs, mis = (stream(m, fd, p) for p in (b'texturescale', b'textureaxisu', b'textureaxisv', b'materialindex'))
        pos = stream(m, m.g(md, b'vertexData'), b'position'); tc = stream(m, m.g(md, b'faceVertexData'), b'texcoord')
        fei, evi, nxt, vdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices'))
        fdi = m.g(md, b'faceDataIndices'); evd = m.g(md, b'edgeVertexDataIndices')
        if None in (scs, us, vs, mis, pos, fei, evi, nxt, vdi): continue
        keys = {}
        def keyof(mat):
            if mat not in keys:
                k = matkey(mat)
                if k not in idx:
                    alt = byname.get(k.rsplit('/', 1)[-1], ())
                    if len(alt) == 1: k = next(iter(alt))
                keys[mat] = k
            return keys[mat]
        moves = None
        for f, he in enumerate(fei):
            fi = fdi[f] if fdi and f < len(fdi) else f
            if fi >= len(scs) or not (0 <= mis[fi] < len(mats)): continue
            mat = mats[mis[fi]]
            if mat.startswith('materials/tools/') or 'moondome' in mat: continue
            pts, hs, h = [], [], he
            for _ in range(256):
                pts.append([pos[vdi[evi[h]]][k] + o[k] for k in range(3)]); hs.append(h); h = nxt[h]
                if h == he: break
            uv = [(pts[i], evd[hs[i]]) for i in range(len(pts))] if (tc is not None and evd and ident and max(hs) < len(evd) and all(evd[x] < len(tc) for x in hs)) else None
            ratio = tgt = how = None; sliver = False; cands = []
            if ident and len(pts) >= 3 and sides:
                if moves is None:   # this mesh as a moved copy of VMF brushes of the same size (and, if any, the same materials)
                    wp = [[p[k] + o[k] for k in range(3)] for p in pos]; mn = [min(p[k] for p in wp) for k in range(3)]; mx = [max(p[k] for p in wp) for k in range(3)]
                    same = [br for br in bysize.get(tuple(round(mx[k] - mn[k]) for k in range(3)), ())
                            if all(abs((br[0]['bb'][1][k] - br[0]['bb'][0][k]) - (mx[k] - mn[k])) <= 0.3 for k in range(3))]
                    mk = {keyof(x) for x in mats if not x.startswith('materials/tools/')}
                    same = [br for br in same if mk <= {s['mat'] for s in br}] or same
                    moves = [(t, br) for t, br in ((sub(mn, br[0]['bb'][0]), br) for br in same) if max(abs(x) for x in t) > 0.5]
                nrm = _face_normal(pts); cen = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
                sliver = _thickness(pts) < SLIVER
                key = keyof(mat)
                if key != matkey(mat): renamed['%s -> %s' % (matkey(mat), key)] += 1
                cands, how = match(key, pts, nrm, cen, sliver, moves)
                if not cands and _bad(scs[fi]):
                    cands = [s for s in near(allidx, dot(nrm, cen), PLANE_TOL) if (sliver or par(s, nrm)) and on_plane(s, pts, PLANE_TOL) and _inside(s, cen)]
                    if cands: how = 'absurd scale, mapping of another material on the same plane'
                if cands:
                    sd, tgt = pick(cands, cen, us[fi], vs[fi], scs[fi])
                    ratio = (scs[fi][0] / sd['us'], scs[fi][1] / sd['vs'])
                    if tgt: stat['matched: ' + how] += 1
                    else: stat['overlapping VMF brushes with different mappings (left as imported)'] += 1
                else: stat['no VMF side on the same plane + material'] += 1
            faces.append(dict(mat=mat, fi=fi, sc=scs, u=us, v=vs, ratio=ratio, tgt=tgt, uv=uv, tc=tc, sliver=sliver, cands=cands))
    per = collections.defaultdict(list)
    for fc in faces: per[fc['mat']].append(fc)
    res = {}; uv_done = set(); no_tex = set(); no_size = collections.Counter(); usual = 0
    for mat, fl in per.items():
        matched = [fc['ratio'] for fc in fl if fc['ratio']]
        bad = [fc['ratio'] for fc in fl if fc['ratio'] and _bad(fc['sc'][fc['fi']]) and not (lo <= fc['ratio'][0] <= hi and lo <= fc['ratio'][1] <= hi)]
        fac = None
        if matched and bad and len(bad) >= 0.8 * len(matched):
            fac = sorted(bad)[len(bad) // 2]
            if sum(1 for r in bad if abs(r[0] / fac[0] - 1) < 0.02 and abs(r[1] / fac[1] - 1) < 0.02) < 0.8 * len(bad): fac = None
        common = collections.Counter((fc['tgt']['us'], fc['tgt']['vs']) for fc in fl if fc['tgt']).most_common(1)
        cnt = res.setdefault(mat, [0, 0, 0, 0])   # rescaled by match, by material factor, broken but unmatched, coords rewritten
        ts = tex_size(c, mat, addon_first=True)
        if not ts:   # implied by the stored coordinates (what Hammer itself used)
            tv = [collections.Counter(), collections.Counter()]
            for fc in fl[:400]:
                if not fc['uv'] or _bad(fc['sc'][fc['fi']]): continue
                (p0, i0) = fc['uv'][0]
                for ci, ax in ((0, fc['u'][fc['fi']]), (1, fc['v'][fc['fi']])):
                    for (p1, i1) in fc['uv'][1:]:
                        dp = sum((p1[k] - p0[k]) * ax[k] for k in range(3)) / fc['sc'][fc['fi']][ci]
                        du = fc['tc'][i1][ci] - fc['tc'][i0][ci]
                        if abs(dp) > 2.0 and abs(du) > 1e-9: tv[ci][round(dp / du)] += 1; break
            if tv[0] and tv[1]:
                (a, na), (b, nb) = tv[0].most_common(1)[0], tv[1].most_common(1)[0]
                if a > 0 and b > 0 and na >= 0.6 * sum(tv[0].values()) and nb >= 0.6 * sum(tv[1].values()): ts = (a, b, 1.0)
        if not ts and any(fc['uv'] for fc in fl): no_size[os.path.basename(mat)[:-5]] = len(fl)
        for fc in fl:
            fi = fc['fi']; sc0, u0, v0 = list(fc['sc'][fi]), list(fc['u'][fi]), list(fc['v'][fi])
            r = fc['ratio']; fix = False
            if r and _bad(sc0) and not (lo <= r[0] <= hi and lo <= r[1] <= hi): fix = True
            elif not r and fac and _bad(sc0): r, fix = fac, True
            elif not r and _bad(sc0) and fc['sliver'] and common:   # sliver with no VMF side: the material's usual scale
                r, fix = (sc0[0] / common[0][0][0], sc0[1] / common[0][0][1]), True; usual += 1
            elif not r and _bad(sc0): cnt[2] += 1
            if fix and (r[0] <= 0 or r[1] <= 0): fix = False
            tg = fc['tgt']
            if tg and (abs(sc0[0] - tg['us']) > 1e-4 * max(1.0, abs(tg['us'])) or abs(sc0[1] - tg['vs']) > 1e-4 * max(1.0, abs(tg['vs']))
                       or any(abs(u0[k] - tg['ua'][k]) > 0.01 or abs(v0[k] - tg['va'][k]) > 0.01 for k in range(4))):
                fc['sc'][fi] = [tg['us'], tg['vs']]; fc['u'][fi] = list(tg['ua']); fc['v'][fi] = list(tg['va'])
                cnt[0] += 1; fix = True
            elif fix:
                fc['sc'][fi] = [sc0[0] / r[0], sc0[1] / r[1]]
                fc['u'][fi] = u0[:3] + [u0[3] * r[0]]; fc['v'][fi] = v0[:3] + [v0[3] * r[1]]
                cnt[0 if fc['ratio'] else 1] += 1
            sc2, u2, v2 = fc['sc'][fi], fc['u'][fi], fc['v'][fi]
            if ts and fc['uv'] and not _bad(sc2):
                flat = (lambda P: P) if not (tg and tg.get('disp')) else (lambda P, s=tg: [P[k] - s['n'][k] * (dot(s['n'], P) - s['d']) for k in range(3)])
                wrong = fix
                if not wrong:
                    for (P, ti) in fc['uv']:
                        Q = flat(P); nu = (dot(Q, u2) / sc2[0] + u2[3]) / ts[0]; nv = (dot(Q, v2) / sc2[1] + v2[3]) / ts[1]
                        du, dv = (fc['tc'][ti][0] - nu) % 1.0, (fc['tc'][ti][1] - nv) % 1.0
                        if min(du, 1 - du) > 0.003 or min(dv, 1 - dv) > 0.003: wrong = True; break
                if wrong:
                    for (P, ti) in fc['uv']:
                        if (id(fc['tc']), ti) in uv_done: continue
                        uv_done.add((id(fc['tc']), ti)); Q = flat(P)
                        fc['tc'][ti] = [(dot(Q, u2) / sc2[0] + u2[3]) / ts[0], (dot(Q, v2) / sc2[1] + v2[3]) / ts[1]]
                    cnt[3] += 1
            elif fix and not ts: no_tex.add(mat)
    done = ['%s (%d)' % (os.path.basename(k)[:-5], max(a + b, d)) for k, (a, b, _, d) in sorted(res.items()) if a + b + d]
    tg = sum(1 for f in faces if f['tgt'])
    c.log.append('face texture scales: %d brush faces, %d matched to one VMF mapping%s' % (len(faces), tg, ''.join('; %d %s' % (v, k) for k, v in sorted(stat.items()))))
    if renamed: c.log.append('face texture scales: vmap materials not in the VMF matched to the one VMF material with the same file name: %s'
                             % ', '.join('%s (%d)' % kv for kv in sorted(renamed.items()))[:900])
    if usual: c.log.append('face texture scales: %d sliver faces with no VMF side given their material\'s usual scale' % usual)
    if done: c.log.append('face texture mapping repaired: %d faces re-scaled / re-shifted from the VMF, %d faces with texture coordinates rewritten: %s'
                          % (sum(a + b for a, b, _, _ in res.values()), sum(d for _, _, _, d in res.values()), ', '.join(done)[:900]))
    absurd = collections.Counter(fc['mat'] for fc in faces if _bad(fc['sc'][fc['fi']]))
    if absurd:
        def says(mat):
            vs_ = vmf_scales.get(matkey(mat))
            return 'VMF: ' + '/'.join('%gx%g' % k for k, _ in vs_.most_common(3)) if vs_ else 'not in the VMF'
        c.todo.append('faces still with an absurd texture scale (<0.01 or >8), left as imported: %s'
                      % ', '.join('%s x%d (%s)' % (os.path.basename(k)[:-5], v, says(k)) for k, v in absurd.most_common())[:900])
    if no_size: c.log.append('face texture scales: no known texture size (coordinates not checked): %s' % ', '.join(sorted(no_size))[:600])
    if no_tex: c.todo.append('face scales fixed but texture coordinates not rewritten (no CS:GO texture size): %s' % ', '.join(sorted(no_tex))[:600])

# ------------------------------------------------------------------ material flags the importer dropped
LIT_ADDITIVE = False   # True: lightmapped $additive stays lit (F_TRANSLUCENT + F_ADDITIVE_BLEND); a black additive material (mg_n64_goldeneye glass04) then draws opaque black in Hammer, so by default every $additive material goes to csgo_unlitgeneric F_BLEND_MODE 4

def ssbump_to_normal(img):
    """$ssbump: R, G, B are the light from Source 1's three radiosity basis directions, not a tangent-space normal (as a normal map they
    average ~(122,123,116) and light wrongly). n = R*b0 + G*b1 + B*b2, normalised; same y orientation as a Source 1 normal map."""
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert('RGB'), dtype=np.float32) / 255.0
    r2, r6, r3, h2 = math.sqrt(2 / 3), 1 / math.sqrt(6), 1 / math.sqrt(3), 1 / math.sqrt(2)
    n = a @ np.array([[r2, 0.0, r3], [-r6, h2, r3], [-r6, -h2, r3]], dtype=np.float32)
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    return Image.fromarray(np.clip((n * 0.5 + 0.5) * 255.0 + 0.5, 0, 255).astype(np.uint8), 'RGB')

def material_flags(m, c):
    import assets
    add, back, unlit, ssb = [], [], [], []
    for mat in sorted(assets.mesh_materials(m)):
        if not mat.endswith('.vmat') or mat.startswith('materials/tools/'): continue
        vp = os.path.join(c.content, mat)
        if mat in c.files: txt = c.files[mat].decode('utf-8', 'replace')
        elif os.path.exists(vp): txt = open(vp, encoding='utf-8', errors='replace').read()
        else: continue
        shader, kv = load_vmt(c, mat[:-5] + '.vmt')
        if not kv: continue
        ms = re.search(r'(?im)^\s*"?shader"?\s+"([^"]+)"', txt)
        if not ms: continue
        sh = ms.group(1).lower(); new = txt; ins = []
        if kv.get('$nocull') == '1' and 'F_RENDER_BACKFACES' not in txt:
            ins.append('F_RENDER_BACKFACES 1'); back.append(os.path.basename(mat)[:-5])
            if 'unlit' not in sh and 'F_DONT_FLIP_BACKFACE_NORMALS' not in txt: ins.append('F_DONT_FLIP_BACKFACE_NORMALS 1')   # Source 1 never flipped them
        mn = re.search(r'TextureNormal"?\s+"([^"]+)"', new)
        if kv.get('$ssbump') == '1' and mn and not mn.group(1).lower().endswith('_ssbn.png') and 'default_normal' not in mn.group(1).lower():
            rel = mn.group(1).replace('\\', '/'); np_ = os.path.join(c.content, rel)
            try:
                import io as _io
                from PIL import Image
                img = Image.open(_io.BytesIO(c.files[rel])) if rel in c.files else (Image.open(np_) if os.path.exists(np_) else None)
                if img is not None:
                    out = os.path.splitext(rel)[0] + '_ssbn.png'; b = _io.BytesIO(); ssbump_to_normal(img).save(b, 'PNG'); c.write(out, b.getvalue())
                    new = new[:mn.start(1)] + out.replace('/', '\\') + new[mn.end(1):]; ssb.append(os.path.basename(mat)[:-5])
            except ImportError: c.todo.append('$ssbump normal maps not converted: needs numpy')
            except Exception: pass
        if kv.get('$additive') == '1' and not re.search(r'F_BLEND_MODE"?\s+"?4', txt) and ('F_ADDITIVE_BLEND' not in txt or not LIT_ADDITIVE):
            if LIT_ADDITIVE and (any(k in (shader or '').lower() for k in ('lightmappedgeneric', 'worldvertextransition')) or 'lightmappedgeneric' in sh):   # judged by the CS:GO shader
                new = re.sub(r'(?im)^\s*"?F_ALPHA_TEST"?\s+"?1"?\s*$\n?', '', new)
                if 'F_TRANSLUCENT' not in new: ins.append('F_TRANSLUCENT 1')
                ins.append('F_ADDITIVE_BLEND 1'); add.append(os.path.basename(mat)[:-5])
            elif 'static_overlay' not in sh and 'sky' not in sh:
                new = new[:ms.start(1)] + 'csgo_unlitgeneric.vfx' + new[ms.end(1):]
                new = re.sub(r'(?im)^\s*"?F_(ALPHA_TEST|TRANSLUCENT|BLEND_MODE|ADDITIVE_BLEND)"?\s+"?\d"?\s*$\n?', '', new)
                ins.append('F_BLEND_MODE 4'); unlit.append(os.path.basename(mat)[:-5])
        if 'csgo_unlitgeneric' in new: ins = [x for x in ins if 'DONT_FLIP' not in x]
        if not ins:
            if new != txt: c.write(mat, new)
            continue
        ms = re.search(r'(?im)^\s*"?shader"?\s+"[^"]+"\s*$', new)
        new = new[:ms.end()] + ''.join('\n\t%s' % x for x in ins) + new[ms.end():]
        c.write(mat, new)
    if add: c.log.append('$additive materials kept lit with F_TRANSLUCENT + F_ADDITIVE_BLEND: %s' % ', '.join(add))
    if unlit: c.log.append('$additive materials moved to csgo_unlitgeneric (F_BLEND_MODE 4, additive): %s' % ', '.join(unlit))
    if back: c.log.append('$nocull materials -> F_RENDER_BACKFACES: %s' % ', '.join(back))
    if ssb: c.log.append('$ssbump bump maps converted to real normal maps (*_ssbn.png): %s' % ', '.join(ssb))

