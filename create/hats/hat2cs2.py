"""Garry's Mod hat / accessory prop (Source 1 .mdl) -> CS2 hat model that bone-merges onto a player's head.

usage: python3 -I hat2cs2.py <catalog.json> [--only id,..] [--no-preview] [--compile] [--sheet]

For every catalog `hats` entry: reads the GMod model, places it on the head, writes
    <out>/models/hats/<id>/<id>.vmdl + <id>_fit<k>.dmx      the hat on CS2's agent skeleton, every vertex on head_0
    <out>/materials/models/hats/<id>/*.vmat|png             (playermodels/gmod2cs2.write_material: VMT handling, PlayerColor
                                                              tint baked in, additive materials left out)
and previews in <work>/preview/<id>.png (on a stock agent's head, three views; on two converted GMod player models).

How a hat follows the head in CS2: the server spawns the hat as a prop_dynamic and FollowEntity's it onto the player's pawn,
which bone-merges it: every bone of the hat with a name the pawn also has takes the pawn's pose. The hat's skeleton is CS2's
agent skeleton (the template's body DMX) and all its vertices are on head_0, so it moves with the head through every animation.
No attachment is needed (CS2 agents have no head attachment: knife, grenade0-4, c4, primary, eholster, pistol, clip_limit,
weapon, weapon_hand_r/l, weapon_center).

Placement (where the hat sits on the head, all in the agent's bind pose):
  1. Pointshop lua (luahats.py) when the item ships one: GMod's eyes attachment (or head bone) on an HL2 citizen, then the item's
     ModifyClientsideModel offsets / rotations / scale replayed. The citizen's head is mapped onto the CS2 agent's head
     (eye centre onto eye centre, turned to face +X, scaled by the head sizes): HEAD_MAP.
  2. Otherwise an automatic fit by kind (hat / glasses / mask / face), from the model's bounds: see autofit().
  3. Catalog overrides on top, in CS2 head space (x forward, y left, z up): `offset` [x, y, z] u, `rotate` [pitch, yaw, roll]
     degrees and `scale` about the hat's centre; `pre_rotate` [rx, ry, rz] turns the source model before the automatic fit.
Fit variants: the hat is written FIT_SHIFTS times, shifted by (dx, dz) (bodygroup "fit", choice k). GMod player models keep
their own (lower) heads on head_0 (playermodels report `head_hitbox_shift`); the server picks the choice nearest that shift.
"""
import json, math, os, re, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PM = os.path.join(os.path.dirname(HERE), 'playermodels')
for p_ in (HERE, PM, os.path.dirname(HERE)): sys.path.insert(0, p_)
import hatpaths, luahats, mdlextra, agents
import gmod2cs2, vtf, preview, dmx9
from srcmdl import SrcModel
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')

MODEL_DIR = 'models/hats'
MAT_DIR = 'materials/models/hats'
REF_AGENT = 'tm_leet_variantf'           # bare-headed stock agent: the head hats are fitted to and previewed on
GMOD_REF = 'ref/male_09.mdl'              # an HL2 citizen player model (what Pointshop offsets were made on), in <work>
FIT_DZ = (0.0, -1.5, -3.0, -4.5)          # fit variants: head lower by ... (GMod heads sit a median 3.6 u under CS2's)
FIT_DX = (0.0, -2.0, 2.0)                 # ... and further back / forward
FIT_SHIFTS = [(dx, dz) for dz in FIT_DZ for dx in FIT_DX]
HAT_SEAT = 0.8              # autofit hats: the hat's bottom this far above the eyes (1.8 left caps floating, 6 Nov review)
PREVIEW_MODELS = ('gordon_restored', 'apoc_female')      # converted GMod player models (gmod_playermodels) the previews also show
RC_DEFAULT = r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe'
HIDER = re.compile(r'(?i)hider')       # Splatoon gear's weapon_hider / gear_hider meshes (they hide the Inklings' hair)
NOT_HEAD = re.compile(r'(?i)tail|wing|jetpack|cape|backpack|_arms|c_arms|player|ragdoll|^v_|^w_')
KINDS = [('headphones', re.compile(r'(?i)headphone|headset|noise_cancel|earmuff|earphone')),
         ('glasses', re.compile(r'(?i)glass|goggle|shades|specs|aviator|monocle|visor')),
         ('mask', re.compile(r'(?i)mask|helmet|bag|head$|legohead|servbot|skull|deadmau5|ledmau5|pumpkin|bucket')),
         ('face', re.compile(r'(?i)mustache|moustache|beard')),
         ('hat', re.compile(r'.'))]


def rot(axis, deg):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a); t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def euler(pitch, yaw, roll):
    """CS2/Source order: roll about x, then pitch about y, then yaw about z (positive pitch tips the front down)"""
    return rot([0, 0, 1], yaw) @ rot([0, 1, 0], pitch) @ rot([1, 0, 0], roll)


# ---------------------------------------------------------------- the two heads
class Heads:
    def __init__(self, p):
        self.agent = agents.Agent(os.path.join(p['work'], 'agents', REF_AGENT + '.json'))
        HP, h = self.agent.head()
        self.c_eye = h['eye']; self.c_top = h['top']
        self.c_lo, self.c_hi = h['lo'], h['hi']
        self.head_R, self.head_t = self.agent.world['head_0']
        band = HP[np.abs(HP[:, 2] - self.c_eye[2]) < 1.0]
        self.c_face = float(band[:, 0].max())               # front of the face at eye height (x)
        self.c_width = float(np.ptp(HP[HP[:, 2] > self.c_eye[2], 1]))   # head width above the eyes
        self.c_back = float(band[:, 0].min())
        g = self.g = SrcModel(os.path.join(p['work'], GMOD_REF))
        self.g_eyes = mdlextra.attachment_world(g, 'eyes')
        eb = [g.bones[e['bone']]['world'][:, :3] @ e['org'] + g.bones[e['bone']]['world'][:, 3] for e in g.eyeballs]
        self.g_eye = np.mean(eb, 0)
        hb = g.bone_index('ValveBiped.Bip01_Head1')
        w = np.zeros(len(g.V))
        for k in range(3): w += np.where(g.B[:, k] == hb, g.W[:, k], 0)
        GP = g.V[w > 0.5]
        g_top = float(GP[:, 2].max()); g_width = float(np.ptp(GP[GP[:, 2] > self.g_eye[2], 0]))
        # GMod citizens face -Y; CS2 agents face +X: turn +90 deg about z. Scale: eye-to-top height and head width, averaged.
        self.Rz = rot([0, 0, 1], 90)
        self.s = float(np.mean([(self.c_top - self.c_eye[2]) / (g_top - self.g_eye[2]), self.c_width / g_width]))

    def gmod_to_cs2(self, P):
        return self.c_eye + self.s * (np.asarray(P) - self.g_eye) @ self.Rz.T

    def frame(self, lua):
        """GMod frame (R columns = forward, left, up; t) the item attaches to on the reference citizen"""
        if lua.get('attach_kind') == 'bone':
            b = self.g.bone_index(lua['attach'])
            if b < 0: b = self.g.bone_index('ValveBiped.Bip01_Head1')
            M = self.g.bones[b]['world']
        else:
            M = mdlextra.attachment_world(self.g, lua['attach'])
            if M is None: M = self.g_eyes
        return M[:, :3].copy(), M[:, 3].copy()


def lua_place(heads, lua, V):
    """replay the Pointshop ops: GMod model-space vertices on the citizen, then mapped onto the CS2 head"""
    R, t = heads.frame(lua)
    for op, axis, v in lua['ops']:
        col = {'forward': R[:, 0], 'right': -R[:, 1], 'up': R[:, 2]}[axis]
        if op == 'move': t = t + col * v
        else: R = rot(col, v) @ R
    S = np.asarray(lua.get('scale', [1, 1, 1]), float)
    Pg = (V * S) @ R.T + t
    return heads.gmod_to_cs2(Pg), heads.Rz @ R


def kind_of(name):
    for k, rx in KINDS:
        if rx.search(name): return k
    return 'hat'


def mirror_score(V, ax):
    """mean distance (share of the model's size) between the model and its mirror image across its centre plane on axis ax"""
    from scipy.spatial import cKDTree
    S = V[np.linspace(0, len(V) - 1, min(len(V), 3000)).astype(int)]
    M = S.copy(); c = (V[:, ax].min() + V[:, ax].max()) / 2; M[:, ax] = 2 * c - M[:, ax]
    return float(cKDTree(V).query(M)[0].mean() / max(np.ptp(V, 0).max(), 1e-6))


def facing(V, kind):
    """yaw (degrees) that turns the model to face +x. A worn item is mirror-symmetric left to right, so its left-right axis is
    the horizontal axis it mirrors across. Left-right on x means it faces +-y: GMod models made for players face -y (as GMod's
    player models do); glasses face the end their lenses (most of their vertices) are at. Left-right on y: faces +x (Source).
    Round items (both mirror) keep their yaw. Returns (yaw, note)."""
    sx, sy = mirror_score(V, 0), mirror_score(V, 1)
    if sx < 0.02 and sy < 0.02: return 0.0, 'round'
    if sx < sy * 0.5:                                   # left-right is x: faces -y or +y
        if kind == 'glasses':
            lo, hi = V[:, 1].min(), V[:, 1].max(); band = 0.25 * (hi - lo)
            front_neg = (V[:, 1] < lo + band).sum() >= (V[:, 1] > hi - band).sum()
            return (90.0 if front_neg else -90.0), 'glasses face %sy' % ('-' if front_neg else '+')
        return 90.0, 'faces -y'
    if kind == 'glasses':
        lo, hi = V[:, 0].min(), V[:, 0].max(); band = 0.25 * (hi - lo)
        if (V[:, 0] < lo + band).sum() > (V[:, 0] > hi - band).sum(): return 180.0, 'glasses face -x'
    return 0.0, 'faces +x'


def crown_radius(V):
    """radius of a hat's opening: in the lowest 35 % of the hat, the 25th percentile of the vertices' distance from the
    vertical axis through the crown (a brim's vertices lie further out, so the low percentile stays on the crown)"""
    lo, hi = V.min(0), V.max(0)
    top = V[V[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
    c = top[:, :2].mean(0) if len(top) > 3 else (lo[:2] + hi[:2]) / 2       # crown centre from its top (brims can be lopsided)
    low = V[V[:, 2] < lo[2] + 0.35 * (hi[2] - lo[2])]
    if len(low) < 4: low = V
    r = np.linalg.norm(low[:, :2] - c, axis=1)
    return float(np.percentile(r, 25)), c


def autofit(heads, V, kind):
    """place a model with no placement data (after facing(): upright, z up, facing +x)"""
    lo, hi = V.min(0), V.max(0); size = hi - lo
    c_eye = heads.c_eye
    head_r = (heads.c_width + (heads.c_face - heads.c_back)) / 4      # mean head radius above the eyes
    if kind == 'glasses':
        s = heads.c_width * 0.92 / max(size[1], 1e-3)
        P = (V - [hi[0], (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]) * s       # lens front at the origin
        return P + [heads.c_face + 0.9, 0, c_eye[2]], s
    if kind == 'headphones':
        # the band over the top of the head, the cups over the ears: the gap between the cups a little over the head's width
        mid = V[np.abs(V[:, 2] - (lo[2] + 0.3 * size[2])) < 0.2 * size[2]]
        inner = np.percentile(np.abs(mid[:, 1] - (lo[1] + hi[1]) / 2), 10) * 2 if len(mid) > 3 else size[1] * 0.6
        s = float(np.clip((heads.c_width + 0.8) / max(inner, 1e-3), 0.15, 6.0))
        P = (V - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2]]) * s                 # top of the band at the origin
        return P + [(heads.c_back + heads.c_face) / 2 - 0.5, 0, heads.c_top + 0.6], s
    if kind == 'face':
        s = heads.c_width * 0.6 / max(size[1], 1e-3)
        P = (V - [hi[0], (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]) * s
        return P + [heads.c_face + 0.6, 0, c_eye[2] - 3.0], s
    if kind == 'mask':
        whole = size[0] > 0.8 * size[1]                       # deep (a helmet, a bag, a head) vs. a flat face mask
        s = heads.c_width * (1.3 if whole else 1.15) / max(size[1], 1e-3)
        if whole:
            P = (V - (lo + hi) / 2) * s
            return P + [(heads.c_back + heads.c_face) / 2, 0, c_eye[2] + 0.8], s
        P = (V - [hi[0], (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]) * s       # mask front at the origin
        return P + [heads.c_face + 1.4, 0, c_eye[2] - 0.6], s
    # hat: the crown's opening fits round the head, its bottom at the forehead
    r, c = crown_radius(V)
    s = float(np.clip(head_r * 1.12 / max(r, 1e-3), 0.15, 6.0))
    P = (V - [c[0], c[1], lo[2]]) * s
    return P + [(heads.c_back + heads.c_face) / 2 - 0.4, 0, c_eye[2] + HAT_SEAT], s


def apply_overrides(P, N, h):
    R = np.eye(3)
    if h.get('rotate') or h.get('scale', 1.0) != 1.0:
        piv = (P.min(0) + P.max(0)) / 2
        R = euler(*h.get('rotate', [0, 0, 0]))
        P = (P - piv) @ R.T * h.get('scale', 1.0) + piv
        N = N @ R.T
    if h.get('offset'): P = P + np.asarray(h['offset'], float)
    return P, N


# ---------------------------------------------------------------- one hat
def find_mdl(p, h):
    for d in [h['item']] + h.get('depends', []):
        f = os.path.join(p['work'], 'extract', str(d), h['mdl'])
        if os.path.exists(f): return f
    raise FileNotFoundError(h['mdl'])


def lua_for(p, cat, h):
    """this item's lua placement, else one from any catalog item for the same model path (packs share models)"""
    if h.get('lua') is False: return None
    scan = os.path.join(p['work'], 'logs', 'scan.json')
    found = None
    if os.path.exists(scan):
        res = json.load(open(scan, encoding='utf-8'))
        for iid in [str(h['item'])] + [k for k in res if k != str(h['item'])]:
            for r in res.get(iid, []):
                if r['mdl'] == h['mdl'].lower() and 'lua' in r and r['lua'].get('ops') is not None:
                    found = dict(r['lua'], from_item=int(iid)); break
            if found: break
    return found


def convert(p, cat, h, heads, tpl, log=print, do_preview=True):
    hid = h['id']
    mdl = find_mdl(p, h)
    m = SrcModel(mdl)
    roots = [os.path.join(p['work'], 'extract', str(d)) for d in [h['item']] + h.get('depends', [])]
    if os.path.isdir(os.path.join(p['basegame'], 'materials')): roots.append(p['basegame'])
    fam0 = m.skins[h.get('skin', 0)] if h.get('skin', 0) < len(m.skins) else m.skins[0]
    meshes = [me for me in m.default_meshes(h.get('bodygroups'))      # hider meshes out before the bounds are measured
              if not HIDER.search(os.path.basename(m.textures[fam0[me['material']] if me['material'] < len(fam0) else me['material']]))]
    used = np.unique(np.concatenate([me['tris'].ravel() for me in meshes if len(me['tris'])]))
    remap = np.full(len(m.V), -1); remap[used] = np.arange(len(used))
    V0 = m.V[used]; N0 = m.N[used]; UV = m.UV[used].copy()
    rep = {'id': hid, 'mdl': h['mdl'], 'item': h['item'], 'verts': int(len(V0))}
    lua = lua_for(p, cat, h)
    kind = h.get('kind') or kind_of(os.path.basename(h['mdl'])[:-4])
    rep['kind'] = kind
    # the model turned to face +x: catalog pre_rotate [rx, ry, rz], else facing() (mirror symmetry)
    if h.get('pre_rotate') is not None:
        rx, ry, rz = h['pre_rotate']; Rp = rot([0, 0, 1], rz) @ rot([0, 1, 0], ry) @ rot([1, 0, 0], rx); note = 'catalog pre_rotate'
    else:
        yaw, note = facing(V0, kind); Rp = rot([0, 0, 1], yaw)
    if lua and not h.get('autofit'):
        # the lua's own turns decide, unless it has no yaw and the model plainly faces sideways (GMod Tower's glasses: the
        # Pointshop items left them sideways)
        if h.get('pre_rotate') is None and any(op == 'rot' and ax == 'up' for op, ax, _ in lua['ops']): Rp, note = np.eye(3), 'lua'
        P, Rn = lua_place(heads, lua, V0 @ Rp.T)
        N = (N0 @ Rp.T) @ Rn.T
        rep['placement'] = 'pointshop lua (%s, item %s)' % (lua['file'], lua['from_item'])
        rep['lua'] = {k: lua[k] for k in ('attach', 'ops', 'scale')}
    else:
        P, s = autofit(heads, V0 @ Rp.T, kind)
        N = N0 @ Rp.T
        rep['placement'] = 'autofit %s (scale %.2f)' % (kind, s)
    rep['facing'] = note
    P, N = apply_overrides(P, N, h)
    N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    rep['bounds'] = [P.min(0).round(2).tolist(), P.max(0).round(2).tolist()]
    # materials
    gmod2cs2.MAT_DIR = MAT_DIR
    skin = h.get('skin', 0)
    fam = m.skins[skin] if skin < len(m.skins) else m.skins[0]
    by_mat, infos, texs = {}, {}, {}
    for me in meshes:
        if not len(me['tris']): continue
        ti = fam[me['material']] if me['material'] < len(fam) else me['material']
        tex = m.textures[ti]
        if tex not in by_mat:
            mat, rgb, info = gmod2cs2.write_material(tex, m.cdtextures, roots, p['out'], hid, 2048, log)
            by_mat[tex] = (mat, []); infos[tex] = info; texs[tex] = rgb
        if infos[tex].get('additive'): continue
        if HIDER.search(os.path.basename(tex)): infos[tex]['hider'] = True; continue   # Splatoon: hides Inkling hair, not drawn
        by_mat[tex][1].append(remap[me['tris']])
    by_mat = {k: v for k, v in by_mat.items() if v[1]}
    if not by_mat: raise ValueError('no drawable mesh (every material additive?)')
    names = list(by_mat)
    mats = [by_mat[k][0] for k in names]; sets = [np.vstack(by_mat[k][1]) for k in names]
    rep['materials'] = [infos[k] for k in names]
    flat = [i['source'] for i in rep['materials'] if i.get('flat')]
    if flat: rep.setdefault('warnings', []).append('no texture for %s (flat grey)' % ', '.join(flat))
    # skinned to head_0: written in the bind pose, once per fit variant
    d = os.path.join(p['out'], MODEL_DIR, hid); os.makedirs(d, exist_ok=True)
    weights = [[('head_0', 1.0)]] * len(P)
    dmx_names = []
    for k, (dx, dz) in enumerate(FIT_SHIFTS):
        Pk = P + [dx, 0, dz]
        fn = '%s_fit%d.dmx' % (hid, k)
        sets_w, flipped = gmod2cs2.write_dmx(tpl.body, os.path.join(d, fn), 'hat_%s_fit%d' % (hid, k), Pk, N, UV, mats, sets, weights)
        dmx_names.append(fn)
    write_vmdl(os.path.join(d, hid + '.vmdl'), hid, dmx_names)
    rep['vmdl'] = '%s/%s/%s.vmdl' % (MODEL_DIR, hid, hid)
    rep['fit_shifts'] = FIT_SHIFTS
    if do_preview:
        groups = [(sets[i], texs[names[i]]) for i in range(len(names))]
        render_preview(p, heads, h, P, UV, groups, rep)
    return rep


def write_vmdl(path, hid, dmx_names):
    rel = '%s/%s/' % (MODEL_DIR, hid)
    meshes = ''.join('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "RenderMeshFile"\n\t\t\t\t\t\tname = "fit%d"\n\t\t\t\t\t\tfilename = "%s%s"\n'
                     '\t\t\t\t\t\timport_scale = 1.0\n\t\t\t\t\t},\n' % (k, rel, fn) for k, fn in enumerate(dmx_names))
    choices = ''.join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\t_class = "BodyGroupChoice"\n\t\t\t\t\t\t\t\tname = "fit%d"\n'
                      '\t\t\t\t\t\t\t\tmeshes = [ "fit%d" ]\n\t\t\t\t\t\t\t},\n' % (k, k) for k in range(len(dmx_names)))
    txt = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc28:version{fb63b6ca-f435-4aa0-a2c7-c66ddc651dca} -->\n'
           '// hat %s (create/hats/hat2cs2.py): skinned to the agent skeleton, every vertex on head_0; bone-merged onto a pawn\n'
           '{\n\trootNode = \n\t{\n\t\t_class = "RootNode"\n\t\tchildren = \n\t\t[\n'
           '\t\t\t{\n\t\t\t\t_class = "BoneMarkupList"\n\t\t\t\tchildren = [  ]\n\t\t\t\tbone_cull_type = "None"\n\t\t\t},\n'
           '\t\t\t{\n\t\t\t\t_class = "RenderMeshList"\n\t\t\t\tchildren = \n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t},\n'
           '\t\t\t{\n\t\t\t\t_class = "BodyGroupList"\n\t\t\t\tchildren = \n\t\t\t\t[\n\t\t\t\t\t{\n\t\t\t\t\t\t_class = "BodyGroup"\n'
           '\t\t\t\t\t\tname = "fit"\n\t\t\t\t\t\tchildren = \n\t\t\t\t\t\t[\n%s\t\t\t\t\t\t]\n\t\t\t\t\t\thidden_in_tools = false\n\t\t\t\t\t},\n\t\t\t\t]\n\t\t\t},\n'
           '\t\t]\n\t\tmodel_archetype = ""\n\t\tprimary_associated_entity = ""\n\t\tanim_graph_name = ""\n\t\tbase_model_name = ""\n\t}\n}\n') % (hid, meshes, choices)
    open(path, 'w', newline='\n').write(txt)


# ---------------------------------------------------------------- previews
SKIN = np.full((4, 4, 3), (176, 150, 132), np.uint8)


def agent_groups(a):
    Ps, UVs, groups, off = [], [], [], 0
    for me in a.body_meshes():
        Ps.append(me['P']); UVs.append(me['UV']); groups.append((me['I'] + off, SKIN)); off += len(me['P'])
    return np.vstack(Ps), np.vstack(UVs), groups


def pm_body(p, slug):
    """a converted GMod player model (gmod_playermodels content addon): bind-pose body, its colour textures, head shift"""
    pm_out = os.path.join(os.path.dirname(p['out']), 'gmod_playermodels')
    f = os.path.join(pm_out, 'models', 'player', 'gmod', slug, slug + '_body.dmx')
    if not os.path.exists(f): return None
    dm = dmx9.DMX.load(f)
    me = [e for e in dm.elements if e.type == 'DmeMesh'][0]; vd = me['currentState']
    P = np.array(vd['position$0']); UV = np.array(vd['texcoord$0'])
    if vd.get('flipVCoordinates'): UV[:, 1] = 1 - UV[:, 1]
    groups = []
    from PIL import Image
    for fs in me['faceSets']:
        mat = fs['material']['mtlName'].replace('\\', '/')
        png = os.path.join(pm_out, mat[:-5] + '_color.png') if mat.endswith('.vmat') else ''
        tex = np.array(Image.open(png).convert('RGB')) if os.path.exists(png) else SKIN
        fl = np.array(fs['faces']); idx = np.split(fl, np.where(fl == -1)[0])
        tris = [t[t >= 0] if t[0] >= 0 else t[1:] for t in idx]
        tris = np.array([t[:3] for t in tris if len(t) >= 3], int)
        if len(tris): groups.append((tris, tex))
    shift = [0, 0, 0]
    rp = os.path.join(os.path.dirname(p['work']), 'playermodels', 'reports', slug + '.json')
    if os.path.exists(rp):
        shift = json.load(open(rp, encoding='utf-8')).get('head_hitbox_shift') or shift
    return P, UV, groups, shift


def fit_choice(shift):
    """the fit variant nearest a model's head shift (dx, dz)"""
    dx, dz = shift[0], shift[2]
    return int(np.argmin([(dx - a) ** 2 + (dz - b) ** 2 for a, b in FIT_SHIFTS]))


def render_preview(p, heads, h, P, UV, hat_groups, rep):
    from PIL import Image, ImageDraw
    tiles = []
    AP, AUV, AG = agent_groups(heads.agent)
    c = heads.c_eye
    lo = np.minimum(P.min(0), c + [-9, -9, -7]); hi = np.maximum(P.max(0), c + [9, 9, 9])
    side = max(hi[2] - lo[2], 18)
    box = (np.array([c[0] - side / 2, c[1] - side / 2, lo[2]]), np.array([c[0] + side / 2, c[1] + side / 2, lo[2] + side]))
    def scene(BP, BUV, BG, HP):
        zmin = box[0][2] - 2 + (HP[:, 2].min() - P[:, 2].min())          # only the triangles in the picture (speed)
        BG = [(f[(BP[f][:, :, 2] > zmin).all(1)], t) for f, t in BG]
        n = len(BP)
        return np.vstack([BP, HP]), np.vstack([BUV, UV]), BG + [(f + n, t) for f, t in hat_groups]
    tmp = os.path.join(p['work'], 'preview', '_tmp_%s.png' % h['id'])
    SP, SUV, SG = scene(AP, AUV, AG, P)
    preview.render(SP, SUV, SG, tmp, views=('three', 'front', 'side'), H=360, box=box)
    tiles.append(Image.open(tmp).copy())
    for slug in PREVIEW_MODELS:
        b = pm_body(p, slug)
        if b is None: continue
        BP, BUV, BG, shift = b
        k = fit_choice(shift); dx, dz = FIT_SHIFTS[k]
        SP, SUV, SG = scene(BP, BUV, BG, P + [dx, 0, dz])
        b2 = (box[0] + [dx, 0, dz], box[1] + [dx, 0, dz])
        preview.render(SP, SUV, SG, tmp, views=('three',), H=360, box=b2)
        tiles.append(Image.open(tmp).copy())
    os.remove(tmp)
    W = sum(t.width for t in tiles); H = tiles[0].height + 22
    out = Image.new('RGB', (W, H), preview.BG); x = 0
    for t in tiles: out.paste(t, (x, 22)); x += t.width
    label = '%s  %s  [%s, %s]' % (h['id'], h.get('name', ''), rep['placement'], rep.get('facing', ''))
    ImageDraw.Draw(out).text((6, 4), label, fill=(235, 235, 235))
    out.save(os.path.join(p['work'], 'preview', h['id'] + '.png'))
    # contact-sheet tile: the agent three-quarter and side, the first player model
    a = tiles[0]; w3 = a.width // 3
    parts = [a.crop((0, 0, w3, a.height)), a.crop((2 * w3, 0, 3 * w3, a.height))] + tiles[1:2]
    tile = Image.new('RGB', (sum(t.width for t in parts), a.height + 18), preview.BG); x = 0
    for t in parts: tile.paste(t, (x, 18)); x += t.width
    ImageDraw.Draw(tile).text((4, 3), '%s  [%s]' % (h['id'], rep['placement'].split(' (')[0] + (' ' + rep['placement'].split(' (')[1].rstrip(')') if 'autofit' in rep['placement'] else '')), fill=(235, 235, 235))
    tile.save(os.path.join(p['work'], 'preview', h['id'] + '_tile.png'))


def contact_sheet(p, ids, name, cols=3):
    from PIL import Image
    tiles = [Image.open(os.path.join(p['work'], 'preview', i + '_tile.png')) for i in ids if os.path.exists(os.path.join(p['work'], 'preview', i + '_tile.png'))]
    if not tiles: return None
    tw, th = tiles[0].size
    sheet = Image.new('RGB', (cols * tw, ((len(tiles) + cols - 1) // cols) * th), preview.BG)
    for k, t in enumerate(tiles): sheet.paste(t.resize((tw, th)), ((k % cols) * tw, (k // cols) * th))
    out = os.path.join(p['work'], 'preview', name + '.jpg'); sheet.save(out, quality=82)
    return out


# ---------------------------------------------------------------- batch
def compile_vmdl(rc, path, log_path):
    t = time.time()
    r = subprocess.run([rc, '-i', path, '-nop4'], capture_output=True, text=True, errors='replace')
    open(log_path, 'w', encoding='utf-8').write(r.stdout + r.stderr)
    bad = [l.strip() for l in (r.stdout + r.stderr).splitlines() if re.search(r'(?i)^\s*(error|warning)|error:|failed to|cannot ', l) and ' 0 failed' not in l]
    return {'ok': ' 1 compiled, 0 failed' in r.stdout, 'seconds': round(time.time() - t, 1), 'problems': bad[:20]}


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    p = hatpaths.paths(cat)
    only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
    hats = [h for h in cat['hats'] if h.get('chosen', True) and (only is None or h['id'] in only)]
    heads = Heads(p)
    print('head map GMod citizen -> %s: scale %.3f, eye %s -> %s' % (REF_AGENT, heads.s, heads.g_eye.round(2), heads.c_eye.round(2)))
    tpl = gmod2cs2.Template(p['template'])
    os.makedirs(os.path.join(p['work'], 'reports'), exist_ok=True)
    rc = RC_DEFAULT if '--compile' in sys.argv else None
    done, failed = [], []
    for k, h in enumerate(hats):
        t0 = time.time()
        try:
            rep = convert(p, cat, h, heads, tpl, do_preview='--no-preview' not in sys.argv)
            if rc:
                rep['compile'] = compile_vmdl(rc, os.path.join(p['out'], rep['vmdl']), os.path.join(p['work'], 'reports', h['id'] + '_compile.log'))
            status = 'OK' if not rc or rep['compile']['ok'] else 'COMPILE FAILED'
            if rep.get('warnings'): status += ' WARN'
            done.append(h['id'])
        except Exception as e:
            import traceback
            rep = {'id': h['id'], 'error': '%s: %s' % (type(e).__name__, e), 'trace': traceback.format_exc()[-1500:]}
            status = 'FAILED ' + rep['error'][:120]; failed.append(h['id'])
        rep['seconds'] = round(time.time() - t0, 1)
        json.dump(rep, open(os.path.join(p['work'], 'reports', h['id'] + '.json'), 'w', encoding='utf-8'), indent=1, default=float)
        print('[%d/%d] %-28s %-14s %s (%.0f s)' % (k + 1, len(hats), h['id'], status, rep.get('placement', ''), rep['seconds']), flush=True)
    if '--sheet' in sys.argv and done:
        for b in range(0, len(done), 18):
            print('sheet:', contact_sheet(p, done[b:b + 18], 'sheet_%d' % (b // 18 + 1)))
    print('%d converted, %d failed %s' % (len(done), len(failed), failed))


if __name__ == '__main__':
    main()
