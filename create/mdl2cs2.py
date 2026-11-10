"""Source 1 studio models (Garry's Mod / HL2 / CS:S .mdl + .vvd + .vtx, VMT/VTF materials) -> CS2 static props.

The mesh is written in its reference (bind) pose as one or more `static_prop_model` vmdls: SMD render mesh (ModelDoc's 90-degree
SMD turn compensated), `csgo_complex` vmats with colour / normal (green flipped) / roughness / alpha test / self-illum from the VMT,
PNG textures capped at --maxtex, one convex hull per model, LODs decimated from LOD0 (create/lod_decimate.py), a 4-view textured
preview and a JSON report (bounds, hit spheres, hardpoint guesses, triangle counts, materials). Readers reused from
create/playermodels (srcmdl.py, vtf.py); writers from modelio.py / lod_decimate.py.

usage: python3 -I create/mdl2cs2.py <model.mdl[,more.mdl]> <addon content root> <name> [options]
  <model.mdl>              one file, or several sharing a skeleton separated by commas (packs that split a mech into head/core/arm/leg
                           files): their meshes are merged, bones matched by name
  --sub models/x/y         folder of the vmdl/SMD files inside the addon (default models/ext/<name>); files <sub>/<name>[_group].*
  --matsub materials/x/y   folder of the vmats and PNGs (default materials/<sub>)
  --roots a;b              extra folders searched for materials/ (the model's own item root and C:\\source1\\playermodels\\basegame are always tried)
  --scale S | --height H | --length L     uniform scale: given, or so the z extent is H, or the longest horizontal side is L
  --origin feet|center|keep               feet: z = 0 under the feet, x/y centred on the lowest quarter of the mesh (default);
                                          center: each written model centred on its own bounds; keep: the source origin
  --yaw auto|long|deg      rotation before writing (auto: toe/camera/thruster bones, else -Y facing -> +90 so the model faces +X;
                           long: weapons, the longest axis becomes +x with the muzzle bone or the thinner end forward)
  --skin N                 skin family (default 0)      --bodygroup part=i   (repeatable; default model 0 of every part)
  --only-parts a,b         keep only these body parts   --drop-materials a,b  drop meshes using these texture names (substrings)
  --drop-parts a,b         drop these body parts (case-insensitive fnmatch on the part name: `rifle`, `*_weapon`): weapons a mech model
                           carries as body groups without an empty choice (--bodygroup part=<empty index> when it has one)
  --only-bones <regex>     keep only faces owned by matching bones (one half of a dual back unit)
  --drop-bones <regex>     drop faces owned by matching bones (a held gun, a back unit skinned to its own bone)
  --drop-boxes "x0,y0,z0,x1,y1,z1;..."   drop every connected piece of the mesh whose bounds lie inside one of the boxes (source units and
                           axes, before the turn and the scale): a gun or blade modelled as its own shell in a one-skin mesh (Tripo GLBs).
                           --list-pieces prints every piece's bounds, triangle count and main bones, then stops
  --split legs=<bone regex>;upper=<regex>  several models from one mesh by the vertex's heaviest bone; bones matching no group go to
                           the group named `upper`, else the last group. Each keeps the common origin (feet) unless --origin center.
  --maxtex 2048            texture size cap            --surface metal        physics surface
  --arms-down 65           T-posed rigs (ValveBiped player models, AC packs with Upperarm/Forearm bones): upper arms turned down toward
                           the body (to ~20 degrees out) and the forearms --fore-deg (15) forward, skinned with the model's own weights;
                           arms already hanging are left alone, mis-scaled skeletons keep the raw reference mesh
  --no-lods                LOD0 only                  --dynamic  a prop a script moves (model_archetype "", prop_dynamic)
  --report out.json  --preview out.png  --skeleton out.json (default next to the vmdl)
  --credit "text"          goes into every vmat's comment line
  <model.glb>              a rigged glTF binary instead (Tripo / Mixamo rigs; create/glbrig.py): bones renamed to ValveBiped, colour map
                           only (the hard-surface pass derives the rest); --decimate N reduces LOD0 to ~N triangles first
  --plain-mat              skip the hard-surface pass (default on: create/hardsurface_mat.py derives per-pixel roughness, metalness,
                           AO, a team-tint mask, edge wear and grime from the colour/normal maps, the source gloss masks and the mesh)
  --retint 0.4             with the hard-surface pass: pull colours toward the roster palette (gunmetal / off-white / hazard yellow)
Prints one line per written model; exit code 1 on failure. Animation (`--animate`) is not implemented: the skeleton JSON keeps the
bone names, parents and reference positions so a later pass can build rig clips.
"""
import argparse, fnmatch, json, os, re, sys, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'playermodels'))
import modelio, lod_decimate                                  # noqa: E402
from srcmdl import SrcModel                                   # noqa: E402
import vtf                                                    # noqa: E402

BASEGAME = r'C:\source1\playermodels\basegame'
LEG_WORDS = ('thigh', 'calf', 'knee', 'foot', 'toe', 'heel', 'leg', 'pelvis', 'hip', 'lower body', 'lowerbody')


def log(*a):
    print(*a, flush=True)


def fix_name(s):
    """bone names come out of the MDL as latin-1; packs made on Japanese PCs carry UTF-8 (sometimes twice over): undo what we can"""
    for _ in range(2):
        try:
            t = s.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if t == s: break
        s = t
    return s


def safe(s):
    return re.sub(r'[^a-z0-9_]+', '_', s.lower()).strip('_') or 'm'


# ---------------------------------------------------------------- loading and merging
def load(paths, skin, choices, only_parts, drop_mats, drop_parts=()):
    """-> dict(V, N, UV, own (heaviest bone per vertex), bones [{name,parent,pos}], meshes [(texture name, tris)], warnings)"""
    warns = []
    bones, bone_ix = [], {}
    V, N, UV, OWN, WW, BB = [], [], [], [], [], []
    meshes = []
    base = 0
    item_roots = []
    for p in paths:
        m = SrcModel(p)
        item_roots.append(item_root(p))
        remap = np.zeros(len(m.bones), int)
        for i, b in enumerate(m.bones):
            nm = fix_name(b['name'])
            key = nm.lower()
            if key not in bone_ix:
                bone_ix[key] = len(bones)
                par = m.bones[b['parent']]['name'] if b['parent'] >= 0 else None
                bones.append({'name': nm, 'parent': fix_name(par).lower() if par else None, 'pos': b['world'][:, 3].astype(float), 'from': os.path.basename(p)})
            remap[i] = bone_ix[key]
        heavy = m.B[np.arange(len(m.W)), m.W.argmax(1)]
        own = remap[np.clip(heavy, 0, len(m.bones) - 1)]
        skins = m.skins[min(skin, len(m.skins) - 1)] if m.skins else list(range(len(m.textures)))
        if skin >= len(m.skins): warns.append('%s: skin %d not in the model (%d skins), using 0' % (os.path.basename(p), skin, len(m.skins)))
        for part in m.parts:
            j = choices.get(part['name'].lower(), choices.get(part['name'], 0))
            if only_parts and not any(o.lower() in part['name'].lower() for o in only_parts): continue
            if drop_parts and any(fnmatch.fnmatch(part['name'].lower(), d.lower()) for d in drop_parts): continue
            ms = part['models']
            if not 0 <= j < len(ms) or ms[j]['nverts'] == 0: continue
            for me in ms[j]['meshes']:
                ti = skins[me['material']] if me['material'] < len(skins) else me['material']
                tex = m.textures[ti] if 0 <= ti < len(m.textures) else 'missing'
                if any(d.lower() in tex.lower() for d in drop_mats): continue
                if not len(me['tris']): continue
                meshes.append((tex, me['tris'] + base, [c.replace('\\', '/') for c in m.cdtextures], len(item_roots) - 1))
        V.append(m.V); N.append(m.N); UV.append(m.UV); OWN.append(own); base += len(m.V)
        WW.append(m.W); BB.append(remap[np.clip(m.B, 0, len(m.bones) - 1)])
    for b in bones:
        b['parent'] = bone_ix.get(b['parent'], -1) if b['parent'] is not None else -1
    return dict(V=np.vstack(V), N=np.vstack(N), UV=np.vstack(UV), own=np.concatenate(OWN), W=np.vstack(WW), B=np.vstack(BB), bones=bones,
                meshes=meshes, roots=item_roots, warnings=warns)


def mesh_pieces(V, F):
    """connected pieces of a mesh after welding vertices by position: -> piece id per face"""
    key = np.round(V / max(1e-9, float(np.ptp(V, 0).max()) * 1e-5)).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
    Fw = inv[F]; parent = np.arange(inv.max() + 1)
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for f in Fw:
        ra = find(f[0])
        for q in f[1:]:
            rq = find(q)
            if rq != ra: parent[rq] = ra
    return np.array([find(i) for i in Fw[:, 0]])


def item_root(mdl_path):
    """the extracted item's root (the folder holding models/ and materials/)"""
    p = os.path.abspath(mdl_path).replace('\\', '/')
    i = p.lower().rfind('/models/')
    return p[:i] if i > 0 else os.path.dirname(p)


# ---------------------------------------------------------------- orientation and scale
def auto_yaw(bones, V, own):
    """degrees to turn so the model faces +X: toe-minus-foot, camera/scanner/head-vs-thruster bones, else assume Source's -Y facing"""
    names = [b['name'].lower() for b in bones]
    pos = lambda i: bone_centroid(V, own, i, bones)
    def find(words, exclude=()):
        return [i for i, n in enumerate(names) if any(w in n for w in words) and not any(e in n for e in exclude)]
    fwd = None
    toes, feet = find(('toe',)), find(('foot',), exclude=('toe', 'back foot'))
    if toes and feet:
        d = np.mean([pos(i) for i in toes], 0) - np.mean([pos(i) for i in feet], 0); d[2] = 0
        if np.linalg.norm(d) > 1e-3: fwd = d; how = 'toes'
    if fwd is None:
        front, back = find(('camera', 'scanner', 'canopy', 'visor', 'eye')), find(('thruster', 'booster', 'back unit', 'back thruster'))
        if front and back:
            d = np.mean([pos(i) for i in front], 0) - np.mean([pos(i) for i in back], 0); d[2] = 0
            if np.linalg.norm(d) > 1e-3: fwd = d; how = 'camera/thrusters'
    if fwd is None:
        if len(bones) <= 1: return 0.0, 'default (static prop, +X facing assumed)'
        return 90.0, 'default (-Y facing assumed)'
    ang = np.degrees(np.arctan2(fwd[1], fwd[0]))
    yaw = -ang
    yaw = round(yaw / 90.0) * 90.0            # snap: source models are axis aligned
    return float(yaw % 360), how


def bone_centroid(V, own, i, bones):
    sel = own == i
    if sel.sum() >= 3: return V[sel].mean(0)
    return bones[i]['pos']


def align_long(Pu, bones, V, own):
    """weapons: turn the longest axis onto +x, muzzle forward (a muzzle/flash bone, else the thinner end); -> (R, how)"""
    lo, hi = Pu.min(0), Pu.max(0); ext = hi - lo
    ax = int(np.argmax(ext))
    if ax == 0: R = np.eye(3)
    elif ax == 1: R = rot_z(-90.0)                       # +y -> +x
    else: R = np.array([[0, 0, 1.0], [0, 1.0, 0], [-1.0, 0, 0]])   # +z -> +x
    Q = Pu @ R.T
    fwd = None; how = ''
    mz = find_bones(bones, ('muzzle', 'muzzle_flash', 'barrel_tip'))
    if mz:
        mp = (np.array(bones[mz[0]]['pos']) @ R.T)
        c = (Q.min(0) + Q.max(0)) / 2
        if abs(mp[0] - c[0]) > 0.2 * ext[ax]: fwd = np.sign(mp[0] - c[0]); how = 'longest axis, muzzle bone %s' % bones[mz[0]]['name']
    if fwd is None:                                       # a gun's grip hangs below and behind the body: muzzle = away from it
        x0, x1 = Q[:, 0].min(), Q[:, 0].max(); L = x1 - x0
        zlo = Q[:, 2].min(); band = Q[Q[:, 2] < zlo + 0.25 * (Q[:, 2].max() - zlo)]
        if len(band) > 10:
            off = band[:, 0].mean() - Q[:, 0].mean()
            if abs(off) > 0.08 * L: fwd = -np.sign(off); how = 'longest axis, grip behind'
    if fwd is None:                                       # thin end forward: compare the cross sections of the two ends
        x0, x1 = Q[:, 0].min(), Q[:, 0].max(); L = x1 - x0
        def area(sel): q = Q[sel]; return float(np.prod(q[:, 1:].max(0) - q[:, 1:].min(0))) if sel.sum() > 3 else 1e9
        a_front, a_back = area(Q[:, 0] > x1 - 0.2 * L), area(Q[:, 0] < x0 + 0.2 * L)
        fwd = 1.0 if a_front <= a_back else -1.0; how = 'longest axis, thin end forward'
    if fwd < 0: R = rot_z(180.0) @ R
    return R, how


def _rodrigues(axis, deg):
    k = np.asarray(axis, float); k /= np.linalg.norm(k); a = np.radians(deg)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


UPPER_ARM_RX = re.compile(r'(?i)upper.?arm|uparm|shoulder.*arm|^def_(l|r)_shoulder$|^(l|r)_ude$')
FOREARM_RX = re.compile(r'(?i)fore.?arm|lower.?arm|^def_(l|r)_elbow$|^(l|r)_2ude$')


def pose_arms(V, N, W, B, bones, own, fwd, deg, fore_deg):
    """T-pose -> standing: each upper arm bone (with its subtree) turns about the shoulder joint down toward the body until it hangs
    about 20 degrees out, then the forearm (a matching child, else the child owning most vertices) turns fore_deg forward about the
    elbow; linear blend skinning with the model's own weights. Arms already hanging (< 40 degrees from straight down) are left alone.
    Returns (V, N, bone positions, note)."""
    nb = len(bones)
    kids = {i: [] for i in range(nb)}
    for i, b in enumerate(bones):
        if b['parent'] >= 0: kids[b['parent']].append(i)
    def subtree(i):
        out, todo = [], [i]
        while todo:
            j = todo.pop(); out.append(j); todo += kids[j]
        return out
    pos = np.array([b['pos'] for b in bones])
    T = np.tile(np.eye(4), (nb, 1, 1))
    down = np.array([0, 0, -1.0]); notes = []
    def xf(M, p): return M[:3, :3] @ p + M[:3, 3]
    def at(j, R):
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = j - R @ j; return M
    for side in ('r', 'l'):
        ups = [i for i in range(nb) if UPPER_ARM_RX.search(bones[i]['name']) and side_of(bones[i]['name']) == side]
        if not ups: continue
        u = max(ups, key=lambda i: (own == i).sum())
        sub_u = subtree(u)
        fores = [i for i in sub_u if i != u and FOREARM_RX.search(bones[i]['name'])]
        if not fores and kids[u]: fores = [max(kids[u], key=lambda i: sum((own == j).sum() for j in subtree(i)))]
        f = max(fores, key=lambda i: (own == i).sum()) if fores else None
        ju = pos[u]
        d = (pos[f] - ju) if f is not None else (V[own == u].mean(0) - ju if (own == u).sum() > 3 else None)
        if d is None or np.linalg.norm(d) < 1e-3: continue
        d = d / np.linalg.norm(d)
        ang = np.degrees(np.arccos(np.clip(d @ down, -1, 1)))
        if ang < 40: notes.append('%s arm already down (%.0f deg)' % (side, ang)); continue
        th = min(deg, ang - 20.0)
        axis = np.cross(d, down)
        if np.linalg.norm(axis) < 1e-6: continue
        Mu = at(ju, _rodrigues(axis, th))
        for b in sub_u: T[b] = Mu @ T[b]
        if f is not None and fore_deg:
            jf = xf(Mu, pos[f])
            hands = [i for i in subtree(f) if i != f and re.search(r'(?i)hand|_te$', bones[i]['name'])]
            tip = xf(Mu, pos[hands[0]]) if hands else (xf(Mu, V[own == f].mean(0)) if (own == f).sum() > 3 else None)
            if tip is not None:
                df = tip - jf
                if np.linalg.norm(df) > 1e-3:
                    df /= np.linalg.norm(df); ax2 = np.cross(df, fwd)
                    if np.linalg.norm(ax2) > 1e-6:
                        Mf = at(jf, _rodrigues(ax2, fore_deg))
                        for b in subtree(f): T[b] = Mf @ T[b]
        notes.append('%s arm down %.0f deg (%s)' % (side, th, bones[u]['name']))
    if not any('arm down' in n for n in notes):
        return V, N, pos, '; '.join(notes) or 'no upper arm bones'
    Vp = np.zeros_like(V); Np = np.zeros_like(N)
    for k in range(W.shape[1]):
        w = W[:, k]; bi = B[:, k]
        Rk = T[bi, :3, :3]; tk = T[bi, :3, 3]
        Vp += w[:, None] * (np.einsum('nij,nj->ni', Rk, V) + tk)
        Np += w[:, None] * np.einsum('nij,nj->ni', Rk, N)
    Np /= np.maximum(np.linalg.norm(Np, axis=1, keepdims=True), 1e-9)
    posp = np.einsum('nij,nj->ni', T[:, :3, :3], pos) + T[:, :3, 3]
    return Vp, Np, posp, '; '.join(notes)


def rot_z(deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# ---------------------------------------------------------------- materials
HS_DEFAULT = True     # the hard-surface pass runs unless --plain-mat (or env MDL2CS2_PLAIN_MAT=1)
HS_SRC = {}          # vmat rel -> colour / normal / gloss / self-illum arrays for the hard-surface pass


def write_material(tex, cds, roots, out, matsub, maxtex, credit, cache, warns):
    """one Source texture name -> (vmat rel path, preview rgb HxWx3, info dict); cache keyed by the vmat path"""
    base = safe(os.path.basename(tex))
    rel_vmat = '%s/%s.vmat' % (matsub, base)
    if rel_vmat in cache: return cache[rel_vmat]
    vmt = None
    for c in list(cds) + ['']:
        vmt = vtf.find_file('materials/%s%s.vmt' % (c, tex), roots)
        if vmt: break
    info = {'texture': tex, 'vmt': bool(vmt)}
    shader, prm = ('missing', {}) if vmt is None else vtf.load_vmt(vmt, roots)
    info['shader'] = shader
    g = lambda k, d='0': str(prm.get(k, d)).strip('"').strip()
    def tex_of(key):
        v = prm.get(key)
        if not v: return None
        v = v.strip('"').replace('\\', '/')
        v = re.sub(r'\.vtf$', '', v, flags=re.I)
        p = vtf.find_file('materials/%s.vtf' % v, roots) or vtf.find_file('materials/%s.png' % v, roots)
        if not p: info.setdefault('missing', []).append(v); return None
        try: return vtf.load_vtf(p)
        except Exception as e: info.setdefault('missing', []).append('%s (%s)' % (v, e)); return None
    d = os.path.join(out, matsub); os.makedirs(d, exist_ok=True)
    def save(arr, suffix, mode='RGB'):
        im = Image.fromarray(arr).convert(mode)
        if max(im.size) > maxtex:
            s = maxtex / max(im.size); im = im.resize((max(4, int(im.width * s)), max(4, int(im.height * s))), Image.LANCZOS)
        fn = '%s_%s.png' % (base, suffix); im.save(os.path.join(d, fn), optimize=True)
        return '%s/%s' % (matsub, fn)
    if g('$additive') == '1':
        info['additive'] = True                       # holograms, glows: light added in Source; a static prop would draw a solid sheet
    col = tex_of('$basetexture')
    if col is None and (prm.get('$envmap') or 'glass' in tex.lower()):
        col = np.full((8, 8, 4), (40, 45, 52, 70), np.uint8); info['glass'] = True
    if col is None:
        col = np.full((8, 8, 4), (150, 150, 150, 255), np.uint8); info['flat'] = True
        warns.append('%s: no base texture (%s), flat grey' % (tex, 'no vmt' if vmt is None else shader))
    if col.shape[-1] == 3: col = np.dstack([col, np.full(col.shape[:2], 255, np.uint8)])
    tint = re.findall(r'[-\d.]+', g('$color2', '') or g('$color', ''))
    lines = ['// %s (%s%s)' % (tex, shader, ('; ' + credit) if credit else ''), 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1']
    lines.append('\tTextureColor "%s"' % save(col[..., :3], 'color'))
    lines.append('\tg_flModelTintAmount "1.000"')              # a script's SetColor tints the prop (team paint)
    if len(tint) >= 3:
        t = [float(x) for x in tint[:3]]
        if max(t) > 1.5: t = [x / 255.0 for x in t]
        if any(abs(x - 1) > 0.02 for x in t): lines.append('\tg_vColorTint "[%.4f %.4f %.4f 0.000000]"' % tuple(t))
    alphatest = g('$alphatest') == '1'
    translucent = g('$translucent') == '1' or info.get('glass') or info.get('additive')
    if alphatest or translucent:
        a = col[..., 3]
        if info.get('additive'): a = np.minimum(a, 110)
        lines.append('\tTextureTranslucency "%s"' % save(np.repeat(a[..., None], 3, 2), 'trans', 'L'))
        if alphatest: lines += ['\tF_ALPHA_TEST 1', '\tg_flAlphaTestReference "%s"' % (g('$alphatestreference', '0.5') or '0.5')]
        else: lines.append('\tF_TRANSLUCENT 1')
    if g('$nocull') == '1': lines.append('\tF_RENDER_BACKFACES 1')
    nrm = tex_of('$bumpmap')
    if nrm is None and prm.get('$normalmap'): nrm = tex_of('$normalmap')
    phong, envmap = g('$phong') == '1', bool(prm.get('$envmap'))
    rough_default = 0.45 if envmap else (0.6 if phong else 0.8)
    metal_default = 0.6 if envmap else (0.15 if phong else 0.0)
    if nrm is not None:
        n = nrm[..., :3].copy(); n[..., 1] = 255 - n[..., 1]          # Source 1 normal maps are Y-down; Source 2 wants Y-up
        lines.append('\tTextureNormal "%s"' % save(n, 'normal'))
        if (phong or envmap) and nrm.shape[-1] == 4 and nrm[..., 3].min() < 250 and g('$normalmapalphaenvmapmask') == '1':
            # normal alpha = env-map mask: shiny where white
            r = (235 - nrm[..., 3].astype(np.float32) * 0.65).clip(50, 235).astype(np.uint8)
            lines.append('\tTextureRoughness "%s"' % save(np.repeat(r[..., None], 3, 2), 'rough', 'L'))
            mt = (nrm[..., 3].astype(np.float32) * 0.8).clip(0, 255).astype(np.uint8)
            lines += ['\tF_METALNESS_TEXTURE 1', '\tTextureMetalness "%s"' % save(np.repeat(mt[..., None], 3, 2), 'metal', 'L')]
            rough_default = None
    else:
        lines.append('\tTextureNormal "materials/default/default_normal.tga"')
    if rough_default is not None:
        ex = tex_of('$phongexponenttexture') if phong else None
        if ex is not None:                                                 # exponent map: high = tight highlight = smooth
            r = (230 - ex[..., 0].astype(np.float32) * 0.7).clip(60, 235).astype(np.uint8)
            lines.append('\tTextureRoughness "%s"' % save(np.repeat(r[..., None], 3, 2), 'rough', 'L'))
        else:
            lines.append('\tTextureRoughness "%s"' % save(np.full((4, 4), int(rough_default * 255), np.uint8), 'rough%d' % int(rough_default * 100), 'L'))
        lines.append('\tg_flMetalness "%.3f"' % metal_default)
    # self-illumination: $selfillum (mask texture or base alpha) or a $detail texture blended additively (blend mode 5, ME3 ports)
    si_mask = None
    if g('$selfillum') == '1':
        mk = tex_of('$selfillummask')
        si_mask = mk[..., 0] if mk is not None else (col[..., 3] if not (alphatest or translucent) else np.full(col.shape[:2], 255, np.uint8))
        info['selfillum'] = True
    elif prm.get('$detail') and g('$detailblendmode') in ('5', '6'):
        dt = tex_of('$detail')
        if dt is not None:
            si_mask = dt[..., :3].max(2); info['selfillum'] = 'detail'
    if si_mask is not None and si_mask.max() > 8:
        lines += ['\tF_SELF_ILLUM 1', '\tTextureSelfIllumMask "%s"' % save(np.repeat(si_mask[..., None], 3, 2), 'illum', 'L'),
                  '\tg_flSelfIllumScale "1.000"', '\tg_flSelfIllumBrightness "4.000"', '\tg_flSelfIllumAlbedoFactor "1.000"']
    lines.append('}')
    open(os.path.join(out, rel_vmat), 'w', newline='\n').write('\n'.join(lines) + '\n')
    try:                                     # inputs for the hard-surface pass (create/hardsurface_mat.py), run once the mesh is placed
        import hardsurface_mat as HS
        gl, ghow = HS.gloss_from_vmt(prm, tex_of, col.shape[:2]) if vmt else (None, 'no vmt')
        HS_SRC[rel_vmat] = dict(col=np.ascontiguousarray(col[..., :3]), nrm=n if nrm is not None else None, gloss=gl, gloss_how=ghow,
                                illum=(si_mask.astype(np.float32) / 255.0) if (si_mask is not None and si_mask.max() > 8) else None)
    except Exception as e:
        warns.append('%s: hard-surface inputs skipped (%s)' % (tex, e))
    prev = col[..., :3].copy()
    if info.get('glass') or info.get('additive'): prev = (prev * 0.5 + 40).astype(np.uint8)
    cache[rel_vmat] = (rel_vmat, prev, info)
    return cache[rel_vmat]


def write_material_img(tex, rgb, out, matsub, maxtex, credit, cache):
    """a colour image (GLB base colour) -> plain csgo_complex vmat + png; the hard-surface pass then adds normal / roughness / metal / AO"""
    base = safe(tex); rel_vmat = '%s/%s.vmat' % (matsub, base)
    if rel_vmat in cache: return cache[rel_vmat]
    d = os.path.join(out, matsub); os.makedirs(d, exist_ok=True)
    im = Image.fromarray(rgb)
    if max(im.size) > maxtex: im = im.resize((maxtex, int(maxtex * im.size[1] / im.size[0])), Image.LANCZOS)
    rgb = np.asarray(im); fn = '%s_color.png' % base; im.save(os.path.join(d, fn), optimize=True)
    lines = ['// %s (glTF base colour%s)' % (tex, ('; ' + credit) if credit else ''), 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1',
             '\tTextureColor "%s/%s"' % (matsub, fn), '\tg_flModelTintAmount "1.000"', '\tTextureNormal "materials/default/default_normal.tga"',
             '\tTextureRoughness "materials/default/default_rough.tga"', '\tg_flMetalness "0.000"', '}']
    open(os.path.join(out, rel_vmat), 'w', newline='\n').write('\n'.join(lines) + '\n')
    HS_SRC[rel_vmat] = dict(col=rgb, nrm=None, gloss=None, gloss_how='none (glTF colour only)', illum=None)
    cache[rel_vmat] = (rel_vmat, np.asarray(im.resize((512, 512))), {'texture': tex, 'shader': 'gltf'})
    return cache[rel_vmat]


# ---------------------------------------------------------------- hit spheres, hardpoints
def hit_spheres(P, height, kmax=6, kmin=3, seed=0):
    """3-6 spheres covering the points: k-means (k from kmin up until the largest radius is <= 30 % of the height), radius = farthest
    member, overlapping spheres merged. Returns [[x, y, z, r], ...]"""
    rng = np.random.RandomState(seed)
    pts = P[rng.choice(len(P), min(len(P), 6000), replace=False)] if len(P) > 6000 else P
    best = None
    for k in range(kmin, kmax + 1):
        # k-means++ seeding on z-sorted quantiles for stability
        order = np.argsort(pts[:, 2]); C = pts[order[((np.arange(k) + 0.5) / k * len(pts)).astype(int)]].copy()
        for _ in range(25):
            d = ((pts[:, None, :] - C[None]) ** 2).sum(2); a = d.argmin(1)
            newC = np.array([pts[a == j].mean(0) if (a == j).any() else C[j] for j in range(k)])
            if np.allclose(newC, C, atol=1e-3): break
            C = newC
        d = np.sqrt(((pts[:, None, :] - C[None]) ** 2).sum(2)); a = d.argmin(1)
        r = np.array([d[a == j, j].max() if (a == j).any() else 0 for j in range(k)])
        best = (C, r)
        if r.max() <= 0.30 * height: break
    C, r = best
    sph = [[*C[j], r[j]] for j in range(len(C)) if r[j] > 0]
    # merge a sphere mostly inside another
    merged = True
    while merged and len(sph) > kmin:
        merged = False
        for i in range(len(sph)):
            for j in range(len(sph)):
                if i == j: continue
                ci, ri = np.array(sph[i][:3]), sph[i][3]; cj, rj = np.array(sph[j][:3]), sph[j][3]
                dist = np.linalg.norm(ci - cj)
                if dist + ri <= rj * 1.05:                      # i inside j
                    sph.pop(i); merged = True; break
            if merged: break
    return [[round(float(v), 1) for v in s] for s in sph]


SIDE = {'r': ('right', ' r ', '_r_', ' r', 'r_', '.r', 'r1', 'r2', 'r3'), 'l': ('left', ' l ', '_l_', ' l', 'l_', '.l', 'l1', 'l2', 'l3')}


def side_of(name):
    n = ' ' + name.lower().replace('valvebiped.bip01_', ' ').replace('_', ' ') + ' '
    if re.search(r'(^|[ .\-])(r|right)([ .\-\d]|$)', n): return 'r'
    if re.search(r'(^|[ .\-])(l|left)([ .\-\d]|$)', n): return 'l'
    return None


def find_bones(bones, words, exclude=()):
    out = []
    for i, b in enumerate(bones):
        n = b['name'].lower()
        if any(w in n for w in words) and not any(e in n for e in exclude): out.append(i)
    return out


def hardpoints(bones, V, own, height, upper_sel, lo, hi):
    """right/left hand (ra/la), shoulders (rs/ls), muzzle and booster guesses, in the written frame; bone positions come from the
    vertices the bone owns (bone matrices in some packs are mis-scaled), else the bone itself"""
    hp, src = {}, {}
    def pick(words, exclude, key_r, key_l):
        ids = find_bones(bones, words, exclude)
        for side, key in (('r', key_r), ('l', key_l)):
            cands = [i for i in ids if side_of(bones[i]['name']) == side]
            if not cands: continue
            # the bone owning the most vertices wins (the hand itself, not a finger)
            cands.sort(key=lambda i: -(own == i).sum())
            hp[key] = [round(float(x), 1) for x in bone_centroid(V, own, cands[0], bones)]; src[key] = bones[cands[0]]['name']
    pick(('hand', 'weapon attach', 'weapon_bone', 'wrist'), ('finger', 'thumb', 'pinky', 'index', 'ring', 'mid'), 'ra', 'la')
    pick(('shoulder', 'clavicle', 'clav', 'shoulderpad'), ('cannon', 'vent', 'pad', 'gren'), 'rs', 'ls')
    if not hp.get('ra') and not hp.get('la'):          # no arms: hang weapons off the upper body's sides at 60 % height
        hp['ra'] = [round(float(x), 1) for x in ((lo[0] + hi[0]) / 2, lo[1] + 0.1 * (hi[1] - lo[1]), lo[2] + 0.6 * (hi[2] - lo[2]))]
        hp['la'] = [round(float(x), 1) for x in ((lo[0] + hi[0]) / 2, hi[1] - 0.1 * (hi[1] - lo[1]), lo[2] + 0.6 * (hi[2] - lo[2]))]
        src['ra'] = src['la'] = 'bounds (no hand bones)'
    if not hp.get('rs') and not hp.get('ls'):
        hp['rs'] = [round(float(x), 1) for x in ((lo[0] + hi[0]) / 2 - 0.1 * (hi[0] - lo[0]), lo[1] + 0.2 * (hi[1] - lo[1]), lo[2] + 0.9 * (hi[2] - lo[2]))]
        hp['ls'] = [round(float(x), 1) for x in ((lo[0] + hi[0]) / 2 - 0.1 * (hi[0] - lo[0]), hi[1] - 0.2 * (hi[1] - lo[1]), lo[2] + 0.9 * (hi[2] - lo[2]))]
        src['rs'] = src['ls'] = 'bounds (no shoulder bones)'
    for a, b in (('ra', 'la'), ('la', 'ra'), ('rs', 'ls'), ('ls', 'rs')):   # mirror a missing side
        if a not in hp and b in hp: hp[a] = [hp[b][0], -hp[b][1], hp[b][2]]; src[a] = 'mirror of ' + b
    muzzles = {k: [round(hp[k][0] + 0.25 * height, 1), hp[k][1], hp[k][2]] for k in ('ra', 'la') if k in hp}
    muzzle_bones = find_bones(bones, ('muzzle', 'cannon tube', 'barrel', 'gun_tip'))
    for i in muzzle_bones[:2]:
        muzzles['bone:' + bones[i]['name']] = [round(float(x), 1) for x in bone_centroid(V, own, i, bones)]
    boost_bones = find_bones(bones, ('thruster', 'booster', 'exhaust', 'jet', 'engine', 'fan'), ('cover', 'vent'))
    boosters = [[round(float(x), 1) for x in bone_centroid(V, own, i, bones)] for i in boost_bones if (own == i).sum() >= 3][:6]
    if not boosters:
        U = V[upper_sel] if upper_sel is not None and upper_sel.any() else V
        ulo, uhi = U.min(0), U.max(0)
        zb = ulo[2] + 0.55 * (uhi[2] - ulo[2]); xb = ulo[0] + 0.1 * (uhi[0] - ulo[0])
        boosters = [[round(float(xb), 1), round(float(-0.2 * (uhi[1] - ulo[1])), 1), round(float(zb), 1)], [round(float(xb), 1), round(float(0.2 * (uhi[1] - ulo[1])), 1), round(float(zb), 1)]]
        src['boosters'] = 'back of the upper body (no thruster bones)'
    else:
        src['boosters'] = ', '.join(bones[i]['name'] for i in boost_bones[:6])
    return hp, muzzles, boosters, src


# ---------------------------------------------------------------- writing
def write_smd(path, P, Nn, UV, faces_by_mat):
    """faces_by_mat: [(smd material name, (m,3) vertex ids)]; ModelDoc turns SMDs 90 degrees: positions written (y, -x, z), v flipped"""
    out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f"
    for mat, F in faces_by_mat:
        for f in F:
            out.append(mat)
            for i in f:
                x, y, z = P[i]; nx, ny, nz = Nn[i]
                out.append(fmt % (y, -x, z, ny, -nx, nz, UV[i, 0], 1 - UV[i, 1]))
    out.append("end")
    open(path, 'w', newline='\n').write('\n'.join(out) + '\n')


def hull_points(P, seed=0):
    pts = P[np.random.RandomState(seed).choice(len(P), min(len(P), 4000), replace=False)] if len(P) > 4000 else P
    lo, hi = pts.min(0), pts.max(0)
    if (hi - lo).min() < 0.5:                       # flat: thicken into a slab so the hull has volume
        pts = np.vstack([pts, pts + np.where(hi - lo < 0.5, 1.0, 0.0)])
    return pts


def make_lods(content, rel_dir, name, size=100.0, labels=None):
    """LOD1..4 decimated from LOD0 (lod_decimate.cluster), vmdl rewritten; returns per-LOD triangle counts and a note.
    lod_decimate's cell sizes suit human-scale props: they grow with the model's size (a 300 u mech switches further away).
    labels: optional per-corner label [faces, 3] in LOD0's file order (the skin bone): clusters never span two labels, so a decimated LOD
    does not bridge one bone's part to another's (stretch when the bones move apart); each LOD's labels are saved beside it (<lod>.lab.npy)"""
    src = os.path.join(content, rel_dir)
    head, fm_names, A = lod_decimate.read_smd(os.path.join(src, name + '.smd'))
    mats = sorted(set(fm_names)); mi = {m: i for i, m in enumerate(mats)}; fm = np.array([mi[m] for m in fm_names])
    meshes, th, counts, notes = [name], [0.0], [len(A)], []
    P, F, VM = lod_decimate.weld_pos(A, fm, labels); CH = lod_decimate.charts(A)
    prev = len(F); lo = 0.05
    grow = max(1.0, size / 120.0)
    for k, (mc, t, tg) in enumerate(zip(lod_decimate.MAX_CELL, lod_decimate.THRESH, lod_decimate.TARGET)):
        mc *= grow
        res = lod_decimate.cluster(P, F, A, fm, mc, VM, CH, ret_labels=True); cell = mc
        if len(res[0]) < tg * len(A):
            a_, b_ = lo, mc
            for _ in range(8):
                mid = (a_ * b_) ** 0.5; r = lod_decimate.cluster(P, F, A, fm, mid, VM, CH, ret_labels=True)
                if len(r[0]) <= tg * len(A): b_, res, cell = mid, r, mid
                else: a_ = mid
        OP, ON, OU, OM, NP, OL = res; lo = cell
        if len(OP) > prev * lod_decimate.MIN_GAIN or len(OP) == 0: notes.append('lod%d skipped' % (k + 1)); continue
        mname = '%s_lod%dd' % (name, k + 1)
        lod_decimate.write_smd(os.path.join(src, mname + '.smd'), head, mats, OP, ON, OU, OM)
        if labels is not None: np.save(os.path.join(src, mname + '.lab.npy'), OL)
        meshes.append(mname); th.append(t); counts.append(len(OP)); prev = len(OP)
    vm = open(os.path.join(src, name + '.vmdl')).read()
    open(os.path.join(src, name + '.vmdl'), 'w', newline='\n').write(lod_decimate.vmdl_rewrite(vm, name, rel_dir, meshes, th))
    return counts, notes


def preview(path, P, UV, groups, marks, label, box=None, H=720):
    import preview as pv
    pv.render(P, UV, groups, path, views=('front', 'three', 'side', 'back'), H=H, marks=marks, label=label, box=box)


def hardsurface_pass(a, M, P, Nn, mat_of, warns):
    """per-pixel roughness / metalness / AO / tint mask, edge wear and grime for every written material (create/hardsurface_mat.py),
    with feature edges and AO baked from the placed mesh. Never fails the conversion: on an error the plain materials stay."""
    try:
        import hardsurface_mat as HS
        Fs, fv = [], []
        for tex, F, cds, ri in M['meshes']:
            if mat_of[tex][2].get('additive'): continue
            Fs.append(F); fv += [mat_of[tex][0]] * len(F)
        if not Fs: return
        F_all = np.vstack(Fs); fv = np.array(fv)
        items = []
        for rel in sorted(set(fv)):
            src = HS_SRC.get(rel)
            if src is None: continue
            items.append(dict(vmat=rel, faces=np.nonzero(fv == rel)[0], seed=rel, **src))
        t = time.time()
        opts = dict({'retint': a.retint} if a.retint else {}, **({'auto_glow': True} if 'images' in M else {}))   # GLB colour maps: painted lights glow
        rep = HS.upgrade_set(a.out, items, (P, F_all, M['UV'], Nn), opts or None, a.maxtex, log)
        log('  hard-surface materials: %d in %.0f s' % (len(rep), time.time() - t))
    except Exception as e:
        import traceback; traceback.print_exc()
        warns.append('hard-surface material pass failed (%s): plain materials kept' % e)


# ---------------------------------------------------------------- main
def convert(a):
    t0 = time.time()
    paths = [p for p in a.src.split(',') if p]
    choices = {}
    for bg in a.bodygroup or []:
        k, _, v = bg.partition('='); choices[k.lower()] = int(v or 0)
    only_parts = [x for x in (a.only_parts or '').split(',') if x]
    drop_mats = [x for x in (a.drop_materials or '').split(',') if x]
    drop_parts = [x for x in (a.drop_parts or '').split(',') if x]
    if paths[0].lower().endswith('.glb'):              # rigged glTF (Tripo, Mixamo): create/glbrig.py gives the same model dict
        import glbrig
        M = glbrig.load(paths[0], rename='valve', decimate=a.decimate, log=log)
    else:
        M = load(paths, a.skin, choices, only_parts, drop_mats, drop_parts)
    warns = list(M['warnings'])
    V, N, UV, own, bones = M['V'], M['N'], M['UV'], M['own'], M['bones']
    roots = M['roots'] + [r for r in (a.roots or '').split(';') if r] + ([BASEGAME] if os.path.isdir(BASEGAME) else [])
    # used vertices (optionally only those whose heaviest bone matches --only-bones: one half of a dual back unit)
    if a.only_bones:
        pat = re.compile(a.only_bones); keep_b = np.array([bool(pat.search(b['name'])) for b in bones])
        kept = []
        for tex, F, cds, ri in M['meshes']:
            fm = keep_b[own[F]].sum(1) >= 2
            if fm.any(): kept.append((tex, F[fm], cds, ri))
        M['meshes'] = kept
    if a.drop_bones:                                   # built-in weapons skinned to their own bones (and everything hanging off them)
        pat = re.compile(a.drop_bones); drop_b = np.array([bool(pat.search(b['name'])) for b in bones])
        for bi, b in enumerate(bones):                 # children of a dropped bone go with it
            q, seen = b['parent'], 0
            while q is not None and q >= 0 and seen < 64 and not drop_b[bi]:
                if drop_b[q]: drop_b[bi] = True
                q = bones[q]['parent']; seen += 1
        kept, ndrop = [], 0
        for tex, F, cds, ri in M['meshes']:
            fm = drop_b[own[F]].sum(1) >= 2
            ndrop += int(fm.sum())
            if (~fm).any(): kept.append((tex, F[~fm], cds, ri))
        M['meshes'] = kept
        log('  drop-bones: %d faces of %s' % (ndrop, ', '.join(b['name'] for b, d in zip(bones, drop_b) if d)[:200]))
    if a.drop_boxes or a.list_pieces:                  # connected pieces of the welded mesh (one-skin models carry their weapons as separate shells)
        Fall = np.vstack([F for _, F, _, _ in M['meshes']]); piece = mesh_pieces(V, Fall)
        ids = np.unique(piece); lo_ = np.array([V[Fall[piece == i].ravel()].min(0) for i in ids]); hi_ = np.array([V[Fall[piece == i].ravel()].max(0) for i in ids])
        if a.list_pieces:
            for k in np.argsort([-(piece == i).sum() for i in ids]):
                ob = np.bincount(own[Fall[piece == ids[k]].ravel()], minlength=len(bones))
                log('piece %5d tris  %s .. %s  %s' % ((piece == ids[k]).sum(), lo_[k].round(3).tolist(), hi_[k].round(3).tolist(), ', '.join(bones[i]['name'] for i in np.argsort(-ob)[:2] if ob[i])))
            raise SystemExit(0)
        boxes = [np.array([float(x) for x in b.split(',')]) for b in a.drop_boxes.split(';') if b.strip()]
        gone = np.zeros(len(ids), bool)
        for b in boxes:
            blo, bhi = np.minimum(b[:3], b[3:]), np.maximum(b[:3], b[3:])
            gone |= (lo_ >= blo).all(1) & (hi_ <= bhi).all(1)
        dropf = np.isin(piece, ids[gone]); kept, o = [], 0
        for tex, F, cds, ri in M['meshes']:
            m_ = ~dropf[o:o + len(F)]; o += len(F)
            if m_.any(): kept.append((tex, F[m_], cds, ri))
        M['meshes'] = kept
        log('  drop-boxes: %d pieces, %d faces' % (int(gone.sum()), int(dropf.sum())))
    used = np.zeros(len(V), bool)
    for tex, F, cds, ri in M['meshes']: used[F.ravel()] = True
    if not used.any(): raise SystemExit('no geometry selected')
    # orientation
    if a.yaw in ('long', 'long180'):
        R, how = align_long(V[used], bones, V, own); yaw = 0.0
        if a.yaw == 'long180': R = rot_z(180.0) @ R; how += ', flipped 180 (heuristic picked the wrong end)'
    else:
        if a.yaw == 'auto':
            yaw, how = auto_yaw(bones, V, own)
        else:
            yaw, how = float(a.yaw), 'given'
        R = rot_z(yaw)
    bpos0 = np.array([b['pos'] for b in bones]) if bones else np.zeros((0, 3))
    pose_note = ''
    if a.arms_down and len(bones) > 1:
        bone_span = (bpos0.max(0) - bpos0.min(0)).max(); mesh_span = (V[used].max(0) - V[used].min(0)).max()
        if bone_span > 0.3 * mesh_span:
            V, N, bpos0, pose_note = pose_arms(V, N, M['W'], M['B'], bones, own, R.T @ np.array([1.0, 0, 0]), a.arms_down, a.fore_deg)
            for i, b in enumerate(bones): b['pos'] = bpos0[i]
        else:
            pose_note = 'skipped (mis-scaled skeleton, raw reference mesh written)'
        log('  arms-down: ' + pose_note)
    P = V @ R.T; Nn = N @ R.T
    bpos = bpos0 @ R.T if bones else np.zeros((0, 3))
    lo, hi = P[used].min(0), P[used].max(0)
    if a.height: s = a.height / max(1e-6, hi[2] - lo[2])
    elif a.length: s = a.length / max(1e-6, hi[0] - lo[0], hi[1] - lo[1])
    else: s = a.scale or 1.0
    P *= s; bpos *= s
    lo, hi = P[used].min(0), P[used].max(0)
    # groups by bone ownership
    groups = []                                   # [(name, vertex mask)]
    if a.split:
        specs = [g.partition('=') for g in a.split.split(';') if g]
        names = [k for k, _, _ in specs]
        gid = np.full(len(bones), -1, int)
        default = names.index('upper') if 'upper' in names else len(names) - 1
        for gi, (k, _, rx) in enumerate(specs):
            if gi == default and rx in ('.*', '^.*$'): continue          # the catch-all takes what is left AFTER the leg-descendant rule below (else it grabs every thigh armour bone)
            pat = re.compile(rx)
            for bi, b in enumerate(bones):
                if gid[bi] < 0 and pat.search(b['name']): gid[bi] = gi
        if 'legs' in names:                       # everything hanging below a thigh follows the legs (knee armour, shock rods, rack bones)
            try:
                import mech_anim
                ch = mech_anim.find_chain(bones, 'leg')
                if ch:
                    lg = names.index('legs'); lroots = {ch['l'][0], ch['r'][0]}
                    for bi, b in enumerate(bones):
                        if gid[bi] >= 0: continue
                        q, seen = b['parent'], 0
                        while q is not None and q >= 0 and seen < 64:
                            if q in lroots: gid[bi] = lg; break
                            q = bones[q]['parent']; seen += 1
            except Exception as ex: warns.append('leg-descendant split skipped: %s' % ex)
        gid[gid < 0] = default
        vg = gid[own]
        if getattr(a, 'torso_to_upper', False) and 'legs' in names and 'upper' in names:
            # A torso shell skinned to the pelvis (an auto-rig on a mech with a block torso: IRONFRAME's Tripo "Bastion", whose whole back
            # and spine block was owned by the hips) lands in the legs model: the back of the upper model is an open hole and the block
            # turns with the legs. Vertices of the legs group that are not on a leg bone and lie above the pelvis and
            # thigh joints go to the upper group (the seam is cut there, like any frame's waist).
            try:
                import mech_anim
                ch = mech_anim.find_chain(bones, 'leg')
                lg, ug = names.index('legs'), names.index('upper')
                legbone = np.zeros(len(bones), bool)
                if ch:
                    lroots = {ch['l'][0], ch['r'][0]}
                    for bi, b in enumerate(bones):
                        q, seen = bi, 0
                        while q is not None and q >= 0 and seen < 64:
                            if q in lroots: legbone[bi] = True; break
                            q = bones[q]['parent']; seen += 1
                    # the cut: above the pelvis joint (the thighs' parent) and the thigh joints, a little over them
                    pj = bones[ch['l'][0]]['parent']
                    zj = max(float(bpos[ch['l'][0]][2]), float(bpos[ch['r'][0]][2]), float(bpos[pj][2]) if pj is not None and pj >= 0 else -1e9)
                    Hh = float(P[used][:, 2].max() - P[used][:, 2].min())
                    sel = (vg == lg) & ~legbone[own] & (P[:, 2] > zj + 0.03 * Hh) & used
                    if sel.any():
                        vg[sel] = ug
                        warns.append('torso-to-upper: %d pelvis-skinned vertices above z %.0f (pelvis / thigh joints + 3 %%) moved from legs to upper' % (int(sel.sum()), zj + 0.03 * Hh))
            except Exception as ex: warns.append('torso-to-upper skipped: %s' % ex)
        for gi, k in enumerate(names): groups.append((k, vg == gi))
        groups = [(k, m) for k, m in groups if (m & used).any()]
    else:
        groups = [('', used.copy())]
    # origin
    if a.origin == 'feet':
        low = P[used & (P[:, 2] <= lo[2] + 0.25 * (hi[2] - lo[2]))]
        c = np.array([(low[:, 0].min() + low[:, 0].max()) / 2, (low[:, 1].min() + low[:, 1].max()) / 2, lo[2]])
        P -= c; bpos -= c
    elif a.origin == 'center' and len(groups) == 1:
        c = (lo + hi) / 2; P -= c; bpos -= c
    lo, hi = P[used].min(0), P[used].max(0)
    height = float(hi[2] - lo[2])
    bone_ok = len(bones) > 1 and (bpos.max(0) - bpos.min(0)).max() > 0.3 * (hi - lo).max()
    if not bone_ok and len(bones) > 1: warns.append('bone matrices do not span the mesh (mis-scaled skeleton): hardpoints from owned vertices')
    # materials
    sub = a.sub or 'models/ext/%s' % a.name
    matsub = a.matsub or 'materials/' + sub
    cache = {}
    mat_of = {}                                   # texture -> (vmat rel, preview rgb, info)
    for tex, F, cds, ri in M['meshes']:
        if tex not in mat_of:
            rr = [M['roots'][ri]] + [r for r in roots if r != M['roots'][ri]]
            mat_of[tex] = (write_material_img(tex, M['images'][tex], a.out, matsub, a.maxtex, a.credit, cache) if 'images' in M
                           else write_material(tex, cds, rr, a.out, matsub, a.maxtex, a.credit, cache, warns))
    if not a.plain_mat and HS_DEFAULT and os.environ.get('MDL2CS2_PLAIN_MAT') != '1':
        hardsurface_pass(a, M, P, Nn, mat_of, warns)
    # per-group write
    os.makedirs(os.path.join(a.out, sub), exist_ok=True)
    report = {'name': a.name, 'source': [os.path.basename(p) for p in paths], 'yaw': yaw, 'yaw_how': how, 'scale': round(float(s), 5), 'pose': pose_note,
              'height': round(height, 1), 'bounds': [lo.round(1).tolist(), hi.round(1).tolist()], 'models': {}, 'warnings': warns,
              'materials': {t: {k: v for k, v in mat_of[t][2].items()} for t in mat_of}}
    upper_sel = next((m for k, m in groups if k == 'upper'), None)
    if upper_sel is not None:
        report['hip_z'] = round(float(P[upper_sel & used][:, 2].min()), 1)
    prev_groups, prev_marks = [], []
    for gname, gmask in groups:
        mname = a.name + ('_' + gname if gname else '')
        faces = []
        tris_total = 0
        for tex, F, cds, ri in M['meshes']:
            info = mat_of[tex][2]
            if info.get('additive'): continue
            fm = gmask[F].sum(1) >= 2            # a face belongs to the group owning most of its corners
            if a.origin == 'center' and len(groups) > 1: pass
            Fg = F[fm]
            if not len(Fg): continue
            faces.append((os.path.basename(mat_of[tex][0]), Fg)); tris_total += len(Fg)
        if not tris_total: continue
        gv = np.unique(np.concatenate([F for _, F in faces]).ravel())
        Pg = P.copy()
        off = np.zeros(3)
        if a.origin == 'center' and len(groups) > 1:
            off = (P[gv].min(0) + P[gv].max(0)) / 2; Pg = P - off
        glo, ghi = Pg[gv].min(0), Pg[gv].max(0)
        write_smd(os.path.join(a.out, sub, mname + '.smd'), Pg, Nn, UV, faces)
        hull = mname + '_hull'
        modelio.write_hull_smd(os.path.join(a.out, sub, hull + '.smd'), [hull_points(Pg[gv])])
        remaps = sorted({(os.path.basename(v[0]), v[0]) for t, v in mat_of.items() if any(os.path.basename(v[0]) == f[0] for f in faces)})
        txt = modelio.vmdl_text(mname, sub, [mname], remaps, [hull], surface=a.surface, entity='prop_dynamic' if a.dynamic else 'prop_static',
                                archetype='' if a.dynamic else 'static_prop_model')          # props a script moves: no archetype
        open(os.path.join(a.out, sub, mname + '.vmdl'), 'w', newline='\n').write(txt)
        counts, notes = ([tris_total], ['lods off']) if a.no_lods else make_lods(a.out, sub, mname, float((ghi - glo).max()))
        anim_info = None
        if a.animate and gname in ('legs', 'upper') and not off.any():
            import mech_anim
            lods = [mname] + [m for m in ('%s_lod%dd' % (mname, k) for k in range(1, 5)) if os.path.exists(os.path.join(a.out, sub, m + '.smd'))]
            anim_info = mech_anim.animate_group(a.out, sub, mname, gname, P, Nn, UV, faces, M['W'], M['B'],
                                                [{'name': b['name'], 'parent': b['parent'], 'pos': bpos[i], 'src': b.get('src')} for i, b in enumerate(bones)],
                                                bone_ok, height, lods[1:], warns.append,
                                                lod_cb=None if a.no_lods else (lambda lab, _m=mname, _s=sub, _g=ghi - glo: make_lods(a.out, _s, _m, float(_g.max()), lab)))
            if anim_info and anim_info.get('lod_counts'): counts, notes = anim_info['lod_counts'], anim_info['lod_notes']
        if a.damage_skins:
            import damage_tex
            damage_tex.apply_vmdl(a.out, '%s/%s.vmdl' % (sub, mname))
        hp, muz, boost, src = hardpoints([dict(b, pos=bpos[i] - off) for i, b in enumerate(bones)], Pg, own, height, gmask & used if gname == 'upper' or not gname else None, glo, ghi) if (gname in ('upper', '') ) else ({}, {}, [], {})
        entry = {'vmdl': '%s/%s.vmdl' % (sub, mname), 'bounds': [glo.round(1).tolist(), ghi.round(1).tolist()], 'tris': counts, 'lod_notes': notes,
                 'spheres': hit_spheres(Pg[gv], height), 'offset': off.round(1).tolist(), 'materials': sorted({f[0] for f in faces})}
        if anim_info: entry.update(anims=anim_info['anims'], anim_len=anim_info['anim_len'], anim_family=anim_info['family'])
        if anim_info and anim_info.get('meta'): entry['gait'] = anim_info['meta']
        if hp: entry.update(hardpoints=hp, muzzles=muz, boosters=boost, hardpoint_sources=src)
        report['models'][gname or 'model'] = entry
        for tex, F, cds, ri in M['meshes']:
            if mat_of[tex][2].get('additive'): continue
            Fg = F[gmask[F].sum(1) >= 2]
            if len(Fg): prev_groups.append((Fg, mat_of[tex][1], off))
        if hp: prev_marks += [np.array(v) + off for v in hp.values()]
        log('%-28s %7d tris %s  bounds %s..%s  %s' % (mname, tris_total, counts[1:] or '', glo.round(1), ghi.round(1), '; '.join(notes)))
    # whole-model spheres (all groups together, common origin)
    report['spheres'] = hit_spheres(P[used], height)
    # skeleton
    skel = {'yaw': yaw, 'scale': round(float(s), 5), 'bones_reliable': bool(bone_ok),
            'bones': [{'name': b['name'], 'parent': b['parent'], 'pos': bpos[i].round(2).tolist(),
                       'centroid': bone_centroid(P, own, i, [{'pos': bpos[j]} for j in range(len(bones))]).round(1).tolist() if (own == i).sum() >= 3 else None,
                       'verts': int((own == i).sum())} for i, b in enumerate(bones)]}
    sk_path = a.skeleton or os.path.join(a.out, sub, a.name + '_skeleton.json')
    json.dump(skel, open(sk_path, 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    if a.preview:
        os.makedirs(os.path.dirname(os.path.abspath(a.preview)), exist_ok=True)
        if a.origin == 'center' and len(groups) > 1:
            P2 = P.copy(); pg = [(F, tex) for F, tex, off in prev_groups]
        else:
            P2 = P; pg = [(F, tex) for F, tex, off in prev_groups]
        marks = np.array(prev_marks) if prev_marks else None
        lab = '%s  %s  h %.0f  yaw %.0f (%s)  %s' % (a.name, '+'.join(report['source']), height, yaw, how, '; '.join(w[:60] for w in warns[:2]))
        preview(a.preview, P2, UV, pg, marks, lab)
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        json.dump(report, open(a.report, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for w in warns: log('  ! ' + w)
    log('%s: %.1fs' % (a.name, time.time() - t0))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('name')
    ap.add_argument('--sub'); ap.add_argument('--matsub'); ap.add_argument('--roots')
    ap.add_argument('--scale', type=float); ap.add_argument('--height', type=float); ap.add_argument('--length', type=float)
    ap.add_argument('--origin', default='feet', choices=('feet', 'center', 'keep')); ap.add_argument('--yaw', default='auto', help='auto | long (weapons: longest axis forward) | long180 (same, then turned round) | degrees')
    ap.add_argument('--skin', type=int, default=0); ap.add_argument('--bodygroup', action='append')
    ap.add_argument('--only-parts'); ap.add_argument('--drop-materials'); ap.add_argument('--drop-parts'); ap.add_argument('--drop-bones', help='drop faces owned by bones matching this regex (and their child bones)'); ap.add_argument('--drop-boxes', help='x0,y0,z0,x1,y1,z1;... : drop connected pieces lying inside a box (source units)'); ap.add_argument('--list-pieces', action='store_true'); ap.add_argument('--split'); ap.add_argument('--only-bones', help='keep only faces owned by bones matching this regex')
    ap.add_argument('--maxtex', type=int, default=2048); ap.add_argument('--surface', default='metal')
    ap.add_argument('--arms-down', type=float, default=0.0, help='T-posed rigs: turn each upper arm down by up to this many degrees (to ~20 from the body)')
    ap.add_argument('--fore-deg', type=float, default=15.0, help='with --arms-down: forearm turned this far forward')
    ap.add_argument('--animate', action='store_true', help='legs/upper groups become skinned props with procedural clips (create/mech_anim.py)')
    ap.add_argument('--no-lods', action='store_true'); ap.add_argument('--dynamic', action='store_true', help='a prop a script moves: model_archetype "" and entity prop_dynamic (default static_prop_model / prop_static)')
    ap.add_argument('--damage-skins', action='store_true', help='add MaterialGroups scorched (1) and wrecked (2) with darkened/soot/burn colour maps (create/damage_tex.py)')
    ap.add_argument('--decimate', type=int, help='GLB sources: quadric-decimate LOD0 to about this many triangles (create/glbrig.py)')
    ap.add_argument('--plain-mat', action='store_true', help='skip the hard-surface material pass (flat roughness, no metal / AO / wear maps)')
    ap.add_argument('--retint', type=float, default=0.0, help='hard-surface pass: pull the colour maps this far (0..1) toward the roster palette')
    ap.add_argument('--torso-to-upper', action='store_true', help='with --split legs / upper: pelvis-skinned shells whose centre is well above the thigh joints go to the upper model')
    ap.add_argument('--report'); ap.add_argument('--preview'); ap.add_argument('--skeleton'); ap.add_argument('--credit', default='')
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    convert(a)


if __name__ == '__main__':
    main()
