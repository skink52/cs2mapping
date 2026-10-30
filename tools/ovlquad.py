"""Stage C step / stage D pass `ovlquads`: CS2 static overlays do not project onto brush entities (func_breakable, func_door, func_brush...).
A CMapStaticOverlay whose projection volume reaches a face of exactly one brush entity, and no world face, is replaced by a translucent
quad mesh (same corners, texture coordinates and size, laid OFFSET in front of that face) parented to the entity, so it shows and moves with it.
The quad uses <overlay material>_quad.vmat: csgo_vertexlitgeneric (entity meshes get no lightmap, so per-vertex lighting matches the brush
it sits on), F_TRANSLUCENT with the overlay's own colour + translucency textures, F_RENDER_BACKFACES (the overlay face points into the
surface; the lit shader flips back-face normals, so lighting is still right).
Left as overlays (listed in TO CHECK): overlays that also reach world faces or two entities at the same depth, ones on slanted faces only,
and ones whose material is a stock CS2 one or not in the addon. Importer placeholder quads (2x2, not yet rebuilt by `overlayfix`) are skipped,
so run this after `overlays` and `overlayfix`. Rerunning is safe: converted overlays no longer exist.
Method from github.com/Ninja-Chris/cs2-slop-porting (MIT), reimplemented on this pipeline's vmap model.
"""
import os, re, io, math, random, copy
import dmx, vmapedit as V, texfix

OFFSET = 0.25           # quad sits this far in front of the entity face (z-fighting)
DEFAULT_FAR = 64.0      # projection depth when the overlay has none
OVERLAY_ONLY = (b'projectionTargets', b'renderOrder', b'disabledInLowQuality', b'useBaseNormals', b'projectionFar',
                b'MaterialAdjustmentParamsStruct', b'projectOnBackFaces', b'backFacingAngle', b'projectionMode')
COPY_KEYS = ('g_vColorTint', 'g_fTextureColorBrightness', 'g_flOpacityScale')

QUAD_VMAT = '''// Overlay quad on a brush entity (CS2 static overlays don't project onto entities): textures of %(src)s.
// Lit per vertex (entity meshes have no lightmap), translucent, both faces drawn.

Layer0
{
	shader "csgo_vertexlitgeneric.vfx"

	//---- Translucent ----
	F_TRANSLUCENT %(tr)d
	F_RENDER_BACKFACES 1

	//---- Color ----
	TextureColor "%(col)s"
%(extra)s}
'''

# ------------------------------------------------------------------ geometry
def _world_pts(m, node, pts, parent):
    """node origin/angles/scales, then the CMapGroups it sits in (children of a brush entity are stored in world space)"""
    def one(n, ps):
        o, a, s = m.g(n, b'origin', [0, 0, 0]), m.g(n, b'angles', [0, 0, 0]), m.g(n, b'scales', [1, 1, 1])
        return [V.xform([p[0] * s[0], p[1] * s[1], p[2] * s[2]], o, a) for p in ps]
    pts = one(node, pts)
    p = parent.get(node)
    while p is not None and m.type(p) == b'CMapGroup':
        pts = one(p, pts); p = parent.get(p)
    return pts

def _owner(m, node, parent):
    p = parent.get(node)
    while p is not None:
        t = m.type(p)
        if t == b'CMapEntity': return p
        if t != b'CMapGroup': return None
        p = parent.get(p)
    return None

def _faces(m, md):
    """[(local polygon, material)] of a CDmePolygonMesh element"""
    pos = texfix.stream(m, m.g(md, b'vertexData'), b'position')
    mi = texfix.stream(m, m.g(md, b'faceData'), b'materialindex')
    mats = [x.decode().lower().replace('\\', '/') for x in m.g(md, b'materials') or []]
    fe, nx, ev, vdi, fdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeNextIndices', b'edgeVertexIndices', b'vertexDataIndices', b'faceDataIndices'))
    out = []
    if pos is None or not fe or nx is None or ev is None or vdi is None: return out
    for f, h0 in enumerate(fe):
        poly, h = [], h0
        for _ in range(4096):
            poly.append(pos[vdi[ev[h]]]); h = nx[h]
            if h == h0: break
        fi = fdi[f] if fdi and f < len(fdi) and fdi[f] >= 0 else f
        mat = mats[mi[fi]] if mi and 0 <= fi < len(mi) and 0 <= mi[fi] < len(mats) else (mats[0] if mats else '')
        if len(poly) >= 3: out.append((poly, mat))
    return out

def _normal(pts):
    nx = ny = nz = 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        nx += (p[1] - q[1]) * (p[2] + q[2]); ny += (p[2] - q[2]) * (p[0] + q[0]); nz += (p[0] - q[0]) * (p[1] + q[1])
    l = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / l, ny / l, nz / l) if l > 1e-9 else None

def _overlap(rect, poly, eps=0.5):
    """rect (x0, y0, x1, y1) and convex 2D poly overlap by more than eps on every separating axis"""
    axes = [(1.0, 0.0), (0.0, 1.0)]
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]; ex, ey = q[0] - p[0], q[1] - p[1]; l = math.hypot(ex, ey)
        if l > 1e-9: axes.append((-ey / l, ex / l))
    rc = [(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])]
    for ax in axes:
        a = [ax[0] * x + ax[1] * y for x, y in rc]; b = [ax[0] * x + ax[1] * y for x, y in poly]
        if min(max(a), max(b)) - max(min(a), min(b)) <= eps: return False
    return True

# ------------------------------------------------------------------ material
def _read(c, rel):
    rel = rel.replace('\\', '/')
    if rel in c.files: return c.files[rel]
    p = os.path.join(c.content, rel)
    return open(p, 'rb').read() if os.path.exists(p) else None

def quad_material(c, mat):
    """-> (quad vmat path, colour texture rel, translucent?) or a reason string"""
    raw = _read(c, mat)
    if raw is None:
        if c.cs2v is not None and c.cs2v.has(mat + '_c'): return 'stock CS2 material (its textures exist only compiled in the VPK)'
        return 'vmat not in the addon'
    txt = raw.decode('utf-8', 'replace')
    mc = re.search(r'TextureColor"?\s+"([^"]+)"', txt)
    if not mc: return 'no TextureColor in its vmat'
    col = mc.group(1); mt = re.search(r'TextureTranslucency"?\s+"([^"]+)"', txt)
    mask = mt.group(1) if mt else None
    if mask is None:   # not yet converted by `overlays`: mask from the colour alpha, same file name `overlays` uses
        data = _read(c, col)
        if data is None: return 'colour texture %s missing' % col
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            if 'A' in im.getbands() and im.getchannel('A').getextrema()[0] < 255:
                mask = os.path.splitext(col.replace('\\', '/'))[0] + '_mask.png'
                if _read(c, mask) is None:
                    b = io.BytesIO(); im.getchannel('A').convert('L').save(b, 'PNG'); c.write(mask, b.getvalue())
        except Exception as ex: return 'colour texture %s unreadable (%s)' % (col, ex)
    extra = []
    if mask: extra += ['\tTextureTranslucency "%s"' % mask.replace('/', '\\')]
    for k in COPY_KEYS:
        mk = re.search(r'(?m)^\s*"?%s"?\s+("[^"]*"|\S+)' % k, txt)
        if mk and (mask or k != 'g_flOpacityScale'): extra.append('\t%s %s' % (k, mk.group(1)))
    if mask and not any(x.startswith('\tg_flOpacityScale') for x in extra): extra.append('\tg_flOpacityScale "1.000"')
    qmat = mat[:-5] + '_quad.vmat'
    body = QUAD_VMAT % dict(src=mat, tr=1 if mask else 0, col=col.replace('/', '\\'), extra=('\n'.join(extra) + '\n') if extra else '')
    if (_read(c, qmat) or b'') != body.encode(): c.write(qmat, body)
    return qmat, col.replace('\\', '/'), bool(mask)

def _tex_size(c, col):
    data = _read(c, col)
    if data is None: return None
    try:
        from PIL import Image
        return Image.open(io.BytesIO(data)).size
    except Exception: return None

def _uv_axes(m, md, vloc, tw, th):
    """overlay texcoords -> [(axis (x, y, 0, shift), scale)] for u and v, in the mesh's local space, or None"""
    tc = texfix.stream(m, m.g(md, b'faceVertexData'), b'texcoord')
    fe, nx, ev, vdi, evd = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeNextIndices', b'edgeVertexIndices', b'vertexDataIndices', b'edgeVertexDataIndices'))
    if tc is None or not fe or evd is None: return None
    vt, h = {}, fe[0]
    for _ in range(4):
        vt[vdi[ev[h]]] = tc[evd[h]]; h = nx[h]
    if sorted(vt) != [0, 1, 2, 3]: return None
    x0, y0, x1, y1, x3, y3 = vloc[0][0], vloc[0][1], vloc[1][0], vloc[1][1], vloc[3][0], vloc[3][1]
    det = (x1 - x0) * (y3 - y0) - (y1 - y0) * (x3 - x0)
    if abs(det) < 1e-6: return None
    sol = []
    for k, tex in ((0, tw), (1, th)):
        du, dv = vt[1][k] - vt[0][k], vt[3][k] - vt[0][k]
        gx = (du * (y3 - y0) - (y1 - y0) * dv) / det; gy = ((x1 - x0) * dv - du * (x3 - x0)) / det
        c0 = vt[0][k] - gx * x0 - gy * y0; gl = math.hypot(gx, gy)
        if gl < 1e-9 or max(abs(gx * v[0] + gy * v[1] + c0 - vt[i][k]) for i, v in enumerate(vloc)) > 1e-3: return None
        sol.append(([gx / gl, gy / gl, 0.0, c0 * tex], 1.0 / (gl * tex)))
    return sol

# ------------------------------------------------------------------ pass
def run(m, c):
    parent = m.parent_of()
    ovs = [n for n, p in m.walk() if m.type(n) == b'CMapStaticOverlay' and m.type(p) != b'CMapEntity']
    if not ovs: return
    meshes = []   # (owner entity or None, [(world polygon, normal)], bbox)
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        polys = []
        for loc, mat in _faces(m, md):
            if mat.startswith('materials/tools/') or mat.endswith('_quad.vmat'): continue
            w = _world_pts(m, n, loc, parent); fn = _normal(w)
            if fn: polys.append((w, fn))
        if not polys: continue
        allp = [p for pl, _ in polys for p in pl]
        meshes.append((_owner(m, n, parent), polys, ([min(p[k] for p in allp) for k in range(3)], [max(p[k] for p in allp) for k in range(3)])))
    nid = [m.next_node_id()]; mats = {}; made = []; left = []
    for ov in ovs:
        md = m.g(ov, b'meshData')
        if md is None or md < 0: continue
        vloc = texfix.stream(m, m.g(md, b'vertexData'), b'position')
        if not vloc or len(vloc) != 4 or texfix.is_placeholder(vloc): continue   # placeholders: overlayfix's job first
        mat = ((m.g(md, b'materials') or [b''])[0]).decode().lower().replace('\\', '/')
        ang = m.g(ov, b'angles', [0, 0, 0]); O = list(m.g(ov, b'origin', [0, 0, 0]))
        rm = V.rot_matrix(ang); ex, ey, nz = ([rm[r][k] for r in range(3)] for k in range(3))
        g = parent.get(ov); rotated = False
        while g is not None and m.type(g) == b'CMapGroup':
            rotated |= any(abs(x) > 1e-4 for x in m.g(g, b'angles', [0, 0, 0])) or any(abs(x - 1) > 1e-4 for x in m.g(g, b'scales', [1, 1, 1]))
            g = parent.get(g)
        if rotated: continue                 # inside a rotated / scaled group: projection axes unknown here, left alone
        pw = _world_pts(m, ov, vloc, parent)
        Ow = _world_pts(m, ov, [[0, 0, 0]], parent)[0]
        to2 = lambda p: (texfix.dot(texfix.sub(p, Ow), ex), texfix.dot(texfix.sub(p, Ow), ey))
        l2 = [to2(p) for p in pw]
        rect = (min(p[0] for p in l2), min(p[1] for p in l2), max(p[0] for p in l2), max(p[1] for p in l2))
        far = m.g(ov, b'projectionFar'); far = DEFAULT_FAR if not isinstance(far, float) else far
        lo = [min(min(p[k] for p in pw), Ow[k]) - far - 1 for k in range(3)]; hi = [max(max(p[k] for p in pw), Ow[k]) + far + 1 for k in range(3)]
        hits_e, hits_w, slanted = [], 0, 0
        for own, polys, bb in meshes:
            if any(bb[1][k] < lo[k] or bb[0][k] > hi[k] for k in range(3)): continue
            for pl, fn in polys:
                t = texfix.dot(texfix.sub(pl[0], Ow), nz)
                if t < -0.5 or t > far + 0.5: continue
                if not _overlap(rect, [to2(p) for p in pl]): continue
                d = texfix.dot(fn, nz)
                if d > -0.99:
                    if d <= -0.7: slanted += 1     # back / perpendicular faces aren't projected on
                    continue
                if own is None: hits_w += 1
                else: hits_e.append((t, own))
        where = '%s at %s' % (os.path.basename(mat)[:-5], ' '.join('%g' % round(x, 1) for x in Ow))
        if not hits_e:
            if slanted and not hits_w: left.append('%s: only slanted entity faces under it' % where)
            continue
        if hits_w: left.append('%s: reaches world faces as well as an entity' % where); continue
        hits_e.sort(key=lambda h: h[0]); t, ent = hits_e[0]
        if any(e != ent and h - t <= 0.5 for h, e in hits_e): left.append('%s: on faces of two entities' % where); continue
        who = '%s %s' % (m.cls(ent), m.name(ent) or '#%d' % (m.g(ent, b'nodeID') or 0))
        if mat not in mats: mats[mat] = quad_material(c, mat)
        q = mats[mat]
        if isinstance(q, str): left.append('%s on %s: %s' % (where, who, q)); continue
        qmat, col, tr = q
        # clone the overlay as a CMapMesh, laid OFFSET in front of the entity face
        n0 = len(m.E); j = m.import_subtree(m, ov, {}, nid)
        for e in m.E[n0:]:                   # import_subtree copies lists shallowly: vectors would stay shared with the overlay
            for a in e['attrs']:
                if isinstance(a[2], list): a[2] = copy.deepcopy(a[2])
        el = m.E[j]; el['type'] = b'CMapMesh'
        el['attrs'] = [a for a in el['attrs'] if a[0] not in OVERLAY_ONLY]
        dmx.set_(el, b'referenceID', dmx.T_U64, random.getrandbits(63))
        dmx.set_(el, b'randomSeed', dmx.T_INT, random.randint(1, 2 ** 31 - 1))
        dmx.set_(el, b'disableShadows', dmx.T_INT, 1)
        sz = (m.g(ov, b'scales', [1, 1, 1]) or [1, 1, 1])[2]; zl = sum(p[2] for p in vloc) / 4.0 * sz
        dmx.set_(el, b'origin', dmx.T_V3, [float(Ow[k] + nz[k] * (t - OFFSET - zl)) for k in range(3)])
        qmd = m.g(j, b'meshData')
        dmx.set_(m.E[qmd], b'materials', dmx.ARR + dmx.T_STR, [qmat.encode()])
        ts = _tex_size(c, col); axes = _uv_axes(m, qmd, vloc, *ts) if ts else None
        if axes:
            for st in m.g(m.g(qmd, b'faceData'), b'streams') or []:
                nm = m.E[st]['name'].lower(); a = dmx.geta(m.E[st], b'data')
                if a is None: continue
                if nm.startswith(b'texturescale'): a[2] = [[axes[0][1], axes[1][1]]] * len(a[2])
                elif nm.startswith(b'textureaxisu'): a[2] = [list(axes[0][0])] * len(a[2])
                elif nm.startswith(b'textureaxisv'): a[2] = [list(axes[1][0])] * len(a[2])
        pa = dmx.geta(m.E[parent[ov]], b'children'); pa[2] = [x for x in pa[2] if x != ov]
        dmx.geta(m.E[ent], b'children')[2].append(j)
        made.append('%s on %s%s' % (where, who, '' if tr else ' (opaque)'))
    if made:
        c.log.append('ovlquads: %d static overlays on brush entities -> translucent quads parented to the entity (<material>_quad.vmat, csgo_vertexlitgeneric; '
                     'CS2 overlays do not project onto entities): %s' % (len(made), '; '.join(made)[:900]))
        c.todo.append('check the %d overlay quads on brush entities in Hammer / game (right way round, not z-fighting, move with the entity)' % len(made))
    if left: c.todo.append('%d static overlays touching brush entities left as overlays (will not show on the entity): %s' % (len(left), '; '.join(left)[:800]))
