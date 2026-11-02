"""Small importer-repair steps (stage C steps and stage D passes of the same names). Methods from github.com/Ninja-Chris/cs2-slop-porting 3.5
(MIT) unless marked skink52; written for this pipeline 2 Nov 2026.

nullparams    outputs the importer wrote with "(null)" as parameter -> "" (else restore_io re-adds the "" copy and the output fires twice)
trigmat       trigger volumes whose faces store another material (copied floor brush) -> toolstrigger (Hammer draws them as toolstrigger anyway)
toolpaths     tools*.vmat referenced outside materials/tools/ -> materials/tools/<same name>
culled        faces of axis-aligned world boxes the importer culled because a water brush lies on them (sea floors) -> box rebuilt from the
              VMF, nodraw except that face
trigsplit     trigger_teleport / trigger_hurt / trigger_multiple spread over several meshes (or one mesh of separate pieces) don't work in
              game the way Hammer shows them -> one entity per piece, same name / keyvalues / outputs (skink52, as in the cs2kz mapping notes)
displaybrush  func_brush / func_illusionary that only display (never solid, no name / parent / outputs / render settings) and sit flush in a
              world surface of the same material -> world meshes with Physics Type None, so they bake with the surface around them
origindup     world meshes that are the importer's copies of brush entities at their local coordinates (around 0 0 0): reported in stage C,
              deleted only by the stage D pass `origindup` (skink52: delete only when they are a problem)
"""
import math, random, collections
import numpy as np
import dmx, vmapedit as V, vmf as vmfmod

TRIGGER_MAT = b'materials/tools/toolstrigger.vmat'
TRIGGER_CLASSES = ('trigger_', 'func_buyzone', 'func_bomb_target', 'func_hostage_rescue')
SPLIT_CLASSES = ('trigger_teleport', 'trigger_hurt', 'trigger_multiple')


def _is_trigger(cls): return any(cls.startswith(x) if x.endswith('_') else cls == x for x in TRIGGER_CLASSES)


def _stream(m, md, group, prefix):
    return next((st for st in m.g(m.g(md, group), b'streams') or [] if m.E[st]['name'].startswith(prefix)), None)


def null_params(m, c):
    n = 0
    for e, cc in m.all_conns():
        if (dmx.get(cc, b'overrideParam') or b'').strip().lower() == b'(null)':
            dmx.set_(cc, b'overrideParam', dmx.T_STR, b''); n += 1
    if n: c.log.append('nullparams: %d output parameters "(null)" cleared' % n)
    return n


def trigger_materials(m, c):
    n = 0
    for e in m.entities():
        if not _is_trigger(m.cls(e)): continue
        for ch in m.children(e):
            if m.type(ch) != b'CMapMesh': continue
            md = m.g(ch, b'meshData'); mats = [x.lower() for x in m.g(md, b'materials') or []]
            if not mats or mats == [TRIGGER_MAT]: continue
            dmx.set_(m.E[md], b'materials', dmx.ARR + dmx.T_STR, [TRIGGER_MAT])
            mi = _stream(m, md, b'faceData', b'materialindex')
            if mi is not None:
                a = dmx.geta(m.E[mi], b'data'); a[2] = [0] * len(a[2])
            n += 1
    if n: c.log.append('trigmat: %d trigger meshes storing other materials set to toolstrigger' % n)
    return n


def tool_paths(m, c):
    fixed = collections.Counter()
    for nd, _ in m.walk():
        if m.type(nd) != b'CMapMesh': continue
        a = dmx.geta(m.E[m.g(nd, b'meshData')], b'materials')
        if not a: continue
        new = []
        for x in a[2]:
            low = x.decode('utf-8', 'replace').replace('\\', '/').lower(); base = low.rsplit('/', 1)[-1]
            good = 'materials/tools/' + base
            if base.startswith('tools') and not low.startswith('materials/tools/') and not c.exists(low) and (c.cs2v is None or c.cs2v.has(good + '_c')):
                fixed[low] += 1; x = good.encode()
            new.append(x)
        a[2] = new
    if fixed: c.log.append('toolpaths: %d tool material references moved to materials/tools/ (%s)' % (sum(fixed.values()), ', '.join(sorted(fixed))[:300]))
    return sum(fixed.values())


# ---------------------------------------------------------------- VMF solids
def _solids(node, origin=(0, 0, 0)):
    o = np.array(origin, float); out = []
    for sd in node.ch:
        if sd.name != 'solid': continue
        sides = []; pts = []
        for s in sd.ch:
            if s.name != 'side' or any(x.name == 'dispinfo' for x in s.ch): continue
            try:
                pl = [np.array([float(v) for v in t.split()]) - o for t in (s.get('plane') or '').replace('(', '').split(')')[:3]]
                if len(pl) != 3: continue
                nrm = np.cross(pl[1] - pl[0], pl[2] - pl[0]); ln = np.linalg.norm(nrm)
                if ln < 1e-9: continue
                nrm = nrm / ln
            except ValueError: continue
            ua = (s.get('uaxis') or '').replace('[', '').split(']'); va = (s.get('vaxis') or '').replace('[', '').split(']')
            try:
                u4 = [float(x) for x in ua[0].split()[:4]]; us = float(ua[1].split()[0]); v4 = [float(x) for x in va[0].split()[:4]]; vs = float(va[1].split()[0])
            except (ValueError, IndexError): u4 = v4 = None; us = vs = 1.0
            sides.append(dict(n=nrm, d=float(nrm @ pl[0]), mat=(s.get('material') or '').lower().replace('\\', '/'), ua=u4, us=us, va=v4, vs=vs))
            pts += pl
        if len(sides) < 4: continue
        P = np.array(pts); cen = P.mean(0)
        for x in sides:
            if x['n'] @ cen - x['d'] > 0: x['n'] = -x['n']; x['d'] = -x['d']
        out.append(dict(sides=sides, lo=P.min(0), hi=P.max(0)))
    return out


def _vmf(vmfp):
    root = vmfmod.parse(open(vmfp, encoding='utf-8', errors='replace').read())
    world = next((n for n in root.ch if n.name == 'world'), None)
    ents = [n for n in root.ch if n.name == 'entity']
    return world, ents


def _box(m, mn, mx, mat=b'materials/tools/toolsnodraw.vmat'):
    import watervol
    tm = V.Map(watervol.TEMPLATE)
    return watervol.box(m, tm, tm.children(tm.world)[0], mn, mx, mat)


def _faces_world(m, node):
    """[(face, [world pos], [faceVertexData idx], material)]"""
    md = m.g(node, b'meshData')
    pos = m.g(_stream(m, md, b'vertexData', b'position'), b'data')
    evx, nxt, vdi, evd = m.g(md, b'edgeVertexIndices'), m.g(md, b'edgeNextIndices'), m.g(md, b'vertexDataIndices'), m.g(md, b'edgeVertexDataIndices')
    o, a = m.g(node, b'origin', [0, 0, 0]), m.g(node, b'angles', [0, 0, 0])
    mats = [x.decode('utf-8', 'replace').lower() for x in m.g(md, b'materials') or []]
    mi = m.g(_stream(m, md, b'faceData', b'materialindex'), b'data') if _stream(m, md, b'faceData', b'materialindex') is not None else None
    fdi = m.g(md, b'faceDataIndices'); out = []
    for f, h0 in enumerate(m.g(md, b'faceEdgeIndices') or []):
        loop, h = [], h0
        for _ in range(64):
            loop.append((vdi[evx[h]], evd[h])); h = nxt[h]
            if h == h0: break
        j = mi[fdi[f]] if mi is not None else -1
        out.append((f, [V.xform(list(pos[v]), o, a) for v, _ in loop], [k for _, k in loop], mats[j] if 0 <= j < len(mats) else ''))
    return out


def culled_faces(m, c, vmfp):
    import texfix
    world, _ = _vmf(vmfp)
    if world is None: return 0
    sol = _solids(world)
    axis = lambda n: (lambda k: k if abs(abs(n[k]) - 1) < 1e-4 else None)(int(np.argmax(np.abs(n))))
    water = [s for s in sol if all('water' in x['mat'] for x in s['sides'])]
    cands = []
    for s in sol:
        if any(s is w for w in water) or len(s['sides']) != 6 or any(axis(x['n']) is None for x in s['sides']): continue
        for x in s['sides']:
            if (x['mat'].startswith('tools/') and 'skybox' not in x['mat']) or 'water' in x['mat'] or x['ua'] is None: continue
            k = axis(x['n']); plane = s['hi'][k] if x['n'][k] > 0 else s['lo'][k]; o1, o2 = [i for i in range(3) if i != k]
            for w in water:
                wp = w['lo'][k] if x['n'][k] > 0 else w['hi'][k]
                if abs(wp - plane) < 1.5 and w['lo'][o1] < s['hi'][o1] and s['lo'][o1] < w['hi'][o1] and w['lo'][o2] < s['hi'][o2] and s['lo'][o2] < w['hi'][o2]:
                    lo, hi = s['lo'].copy(), s['hi'].copy()
                    for i in (o1, o2): lo[i], hi[i] = max(lo[i], w['lo'][i]), min(hi[i], w['hi'][i])
                    cands.append((x, k, plane, lo, hi))
    if not cands: return 0
    faces = []
    for nd, _ in m.walk():
        if m.type(nd) != b'CMapMesh': continue
        for _f, P, _k, fm in _faces_world(m, nd):
            if len(P) < 3 or ('tools' in fm and 'skybox' not in fm) or 'water' in fm or 'liquids/' in fm: continue
            P = np.array(P)
            for k in range(3):
                if np.ptp(P[:, k]) < 0.05: faces.append((k, P[0, k], P.min(0), P.max(0))); break
    n = 0
    for x, k, plane, lo, hi in cands:
        cen = (lo + hi) / 2; cen[k] = plane
        if any(fk == k and abs(fp - plane) < 0.5 and all(a[i] - 1 <= cen[i] <= b[i] + 1 for i in range(3) if i != k) for fk, fp, a, b in faces): continue
        box = _box(m, lo.tolist(), hi.tolist())
        mat = 'materials/' + x['mat'] + '.vmat'
        ts = texfix.tex_size(c, mat) or (512, 512, 1.0)
        md = m.g(box, b'meshData')
        dmx.set_(m.E[md], b'materials', dmx.ARR + dmx.T_STR, [b'materials/tools/toolsnodraw.vmat', mat.encode()])
        st = {m.E[s]['name'].split(b':')[0]: s for g in (b'faceVertexData', b'faceData') for s in m.g(m.g(md, g), b'streams') or []}
        fdi = m.g(md, b'faceDataIndices')
        for f, P, fv, _m in _faces_world(m, box):
            P = np.array(P); nrm = np.cross(P[1] - P[0], P[2] - P[0]); nrm /= (np.linalg.norm(nrm) or 1)
            fd = fdi[f] if fdi else f
            mine = abs(abs(nrm[k]) - 1) < 1e-3 and abs(P[0, k] - plane) < 0.5
            dmx.geta(m.E[st[b'materialindex']], b'data')[2][fd] = 1 if mine else 0
            if not mine: continue
            ua, va = x['ua'], x['va']
            dmx.geta(m.E[st[b'textureAxisU']], b'data')[2][fd] = [float(v) for v in ua]
            dmx.geta(m.E[st[b'textureAxisV']], b'data')[2][fd] = [float(v) for v in va]
            dmx.geta(m.E[st[b'textureScale']], b'data')[2][fd] = [float(x['us']), float(x['vs'])]
            tc = dmx.geta(m.E[st[b'texcoord']], b'data')[2]
            for q, i in zip(P, fv):
                tc[i] = [(float(q @ ua[:3]) / (x['us'] or 1) + ua[3]) / ts[0], (float(q @ va[:3]) / (x['vs'] or 1) + va[3]) / ts[1]]
        dmx.geta(m.E[m.world], b'children')[2].append(box)
        n += 1
    if n: c.log.append('culled: %d brush faces the importer culled under water brushes rebuilt as boxes (nodraw except that face)' % n)
    return n


# ---------------------------------------------------------------- multi-mesh triggers (skink52)
def _components(polys):
    """polys from splitfaces.mesh_read -> list of index lists, one per connected piece (shared vertex positions)"""
    par = list(range(len(polys))); owner = {}
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i, p in enumerate(polys):
        for cn in p['corners']:
            k = tuple(np.round(cn['pos'], 2))
            if k in owner: par[f(i)] = f(owner[k])
            else: owner[k] = i
    g = collections.defaultdict(list)
    for i in range(len(polys)): g[f(i)].append(i)
    return list(g.values())


def split_triggers(m, c):
    import splitfaces as S
    par = m.parent_of(); made = 0; ents = 0
    for e in [e for e in m.entities() if m.cls(e) in SPLIT_CLASSES]:
        meshes = [ch for ch in m.children(e) if m.type(ch) == b'CMapMesh']
        pieces = []                                     # mesh nodes, each one closed piece
        for nd in meshes:
            try: polys, _ = S.mesh_read(m, nd)
            except Exception: pieces.append(nd); continue
            comps = _components(polys)
            if len(comps) < 2: pieces.append(nd); continue
            if S.mesh_write(m, nd, [polys[i] for i in comps[0]]): pieces.append(nd); continue
            pieces.append(nd)
            for comp in comps[1:]:
                new = m.import_subtree(m, nd, {}, [m.next_node_id()])
                if S.mesh_write(m, new, [polys[i] for i in comp]) is None: pieces.append(new)
        if len(pieces) < 2: continue
        others = [ch for ch in m.children(e) if m.type(ch) != b'CMapMesh']
        kids = dmx.geta(m.E[e], b'children')
        parent = par.get(e, m.world)
        for nd in pieces[1:]:
            kids[2] = others + [nd]
            cl = m.import_subtree(m, e, {}, [m.next_node_id()])
            dmx.set_(m.E[cl], b'referenceID', dmx.T_U64, random.getrandbits(63))
            dmx.geta(m.E[parent], b'children')[2].append(cl)
            made += 1
        kids[2] = others + [pieces[0]]
        ents += 1
    if ents:
        c.log.append('trigsplit: %d trigger_teleport/hurt/multiple spread over several meshes or pieces split into %d extra single-mesh entities (same name, keyvalues and outputs)' % (ents, made))
        c.todo.append('trigsplit: split triggers keep their outputs on every piece; a counter fed by OnStartTouch/OnTrigger can now count once per piece touched')
    return made


# ---------------------------------------------------------------- display brushes
def _plane_key(P):
    nrm = np.zeros(3)
    for i in range(1, len(P) - 1): nrm += np.cross(P[i] - P[0], P[i + 1] - P[0])
    ln = np.linalg.norm(nrm)
    if ln < 1e-6: return None
    nrm /= ln
    return tuple(round(float(x), 3) + 0.0 for x in nrm), round(float(P[0] @ nrm) * 2) / 2


def _world_polys(m, par, nd, S):
    a = m.g(nd, b'angles', [0, 0, 0]); sc = m.g(nd, b'scales', [1, 1, 1])
    if any(abs(x) > 1e-4 for x in a) or any(abs(x - 1) > 1e-4 for x in sc): return None
    off = np.array(m.g(nd, b'origin', [0, 0, 0]), float); q = par.get(nd)
    while q is not None:
        if m.type(q) == b'CMapGroup':
            if any(abs(x) > 1e-4 for x in m.g(q, b'angles', [0, 0, 0])) or any(abs(x - 1) > 1e-4 for x in m.g(q, b'scales', [1, 1, 1])): return None
            off = off + np.array(m.g(q, b'origin', [0, 0, 0]), float)
        q = par.get(q)
    try: polys, mats = S.mesh_read(m, nd)
    except Exception: return None
    return polys, [str(x).lower() for x in mats], off


def _in_entity(m, par, nd):
    q = par.get(nd)
    while q is not None:
        if m.type(q) == b'CMapEntity': return q
        q = par.get(q)
    return None


def display_brushes(m, c):
    import splitfaces as S
    par = m.parent_of(); world = {}
    for nd in list(par):
        if m.type(nd) != b'CMapMesh' or _in_entity(m, par, nd) is not None: continue
        r = _world_polys(m, par, nd, S)
        if not r: continue
        polys, mats, off = r
        for q in polys:
            mat = mats[q['attrs'].get('materialindex:0', 0)]
            if 'materials/tools/' in mat: continue
            P = np.array([cn['pos'] for cn in q['corners']]) + off; k = _plane_key(P)
            if k: world.setdefault((mat, k), []).append((P.min(0), P.max(0)))
    ok = lambda v, good: (v or '').strip() in good
    named = {m.name(x).lower() for x in m.entities() if m.name(x)}
    targeted = {dmx.get(cc, b'targetName').decode().lower() for _, cc in m.all_conns()}
    done = []
    for e in m.by_class('func_brush', 'func_illusionary'):
        if m.cls(e) == 'func_brush' and (m.P(e, 'Solidity', '0') or '0') != '1': continue
        if m.name(e) or m.P(e, 'parentname', '') or m.conns(e): continue
        if not (ok(m.P(e, 'StartDisabled'), ('', '0')) and ok(m.P(e, 'rendermode'), ('', '0', 'kRenderNormal')) and ok(m.P(e, 'renderamt'), ('', '255'))
                and ok(m.P(e, 'renderfx'), ('', '0', 'kRenderFxNone')) and ok(m.P(e, 'rendercolor'), ('', '255 255 255'))
                and ok(m.P(e, 'fademindist'), ('', '-1')) and ok(m.P(e, 'fademaxdist'), ('', '0'))): continue
        meshes = [ch for ch in m.children(e) if m.type(ch) == b'CMapMesh']
        if not meshes or len(meshes) != len(m.children(e)): continue
        flush = False; bad = False
        for ch in meshes:
            r = _world_polys(m, par, ch, S)
            if not r: bad = True; break
            polys, mats, off = r
            for q in polys:
                mat = mats[q['attrs'].get('materialindex:0', 0)]
                if 'materials/tools/' in mat: continue
                P = np.array([cn['pos'] for cn in q['corners']]) + off; k = _plane_key(P); lo, hi = P.min(0), P.max(0)
                if k and any((lo <= wh + 0.1).all() and (wl <= hi + 0.1).all() for wl, wh in world.get((mat, k), ())): flush = True
        if bad or not flush: continue
        done.append((e, meshes))
    for e, meshes in done:
        p = par[e]; a = dmx.geta(m.E[p], b'children'); i = a[2].index(e)
        for ch in meshes: dmx.set_(m.E[ch], b'physicsType', dmx.T_STR, b'none')
        a[2][i:i + 1] = meshes
    if done: c.log.append('displaybrush: %d never-solid, never-changing func_brush/func_illusionary flush in a world surface -> world meshes with Physics Type None (bake with the surface)' % len(done))
    return len(done)


# ---------------------------------------------------------------- importer copies of brush entities at the origin
def origin_duplicates(m, c, vmfp, delete=False):
    world, ents = _vmf(vmfp)
    if world is None: return 0
    bent = []
    for e in ents:
        if not e.get('origin') or not any(x.name == 'solid' for x in e.ch): continue
        try: o = [float(x) for x in e.get('origin').split()[:3]]
        except ValueError: continue
        sl = _solids(e, o)
        if sl: bent.append(('%s %s' % (e.get('classname', ''), e.get('targetname', '') or '(unnamed)'), sl,
                            {x['mat'].rsplit('/', 1)[-1] for s in sl for x in s['sides']}))
    wsol = [s for s in _solids(world) if any(not (x['mat'].startswith('tools/') or 'water' in x['mat'] or 'skybox' in x['mat']) for x in s['sides'])]

    def on_surface(P, sols, tol=1.0):
        on = np.zeros(len(P), bool); lo, hi = P.min(0), P.max(0)
        for s in sols:
            if (hi < s['lo'] - tol).any() or (lo > s['hi'] + tol).any(): continue
            N = np.array([x['n'] for x in s['sides']]); D = np.array([x['d'] for x in s['sides']])
            mx = (P @ N.T - D).max(1); on |= np.abs(mx) <= tol
        return on
    par = m.parent_of(); found = []
    for nd, p in par.items():
        if m.type(nd) != b'CMapMesh' or _in_entity(m, par, nd) is not None: continue
        pts = m.mesh_points(nd)
        if len(pts) < 3: continue
        P = np.array(pts); lo, hi = P.min(0), P.max(0)
        near = [b for b in bent if any(not ((hi < s['lo'] - 1).any() or (lo > s['hi'] + 1).any()) for s in b[1])]
        if not near or on_surface(P, [s for b in near for s in b[1]]).mean() < 0.95: continue
        if wsol and on_surface(P, wsol).mean() >= 0.9: continue
        mats = {x.decode('utf-8', 'replace').lower().rsplit('/', 1)[-1].rsplit('.', 1)[0] for x in m.g(m.g(nd, b'meshData'), b'materials') or []}
        if mats - {x for b in near for x in b[2]}: continue
        found.append((nd, p, lo, hi, sorted({b[0] for b in near})[:3]))
    if not found: return 0
    desc = '; '.join('%s..%s (copy of %s)' % (lo.round().astype(int).tolist(), hi.round().astype(int).tolist(), ', '.join(w)) for _, _, lo, hi, w in found)[:800]
    if delete:
        for nd, p, *_ in found:
            a = dmx.geta(m.E[p], b'children'); a[2] = [x for x in a[2] if x != nd]
        c.log.append('origindup: %d importer copies of brush entities at their local coordinates deleted: %s' % (len(found), desc))
    else:
        c.todo.append('origindup: %d world meshes look like the importer\'s copies of brush entities at the origin (run stage D origindup to delete them if they are in the way): %s' % (len(found), desc))
    return len(found)
