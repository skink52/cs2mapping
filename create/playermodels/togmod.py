"""Rigged FBX/GLB imports (the npz files fbx_export.py writes: It Takes Two, League of Legends) -> Garry's Mod player models.

    python3 -I togmod.py <gmod_ports.json> [--only slug,..] [--compile] [--studiomdl path] [--no-preview]

The reverse of gmod2cs2's job, with the same posing code: the target skeleton is a stock-shaped Source 1 ValveBiped (an HL2
citizen recompile, male or female; `ref_male` / `ref_female` in the json) instead of CS2's agent. Each limb's piece of the mesh is
turned so its bone points the way the stock bone points (GMod's animations rotate bones, so a bone's mesh must sit in its frame as
the stock model's does), at the model's own lengths ('ownall': every joint the model's own), one uniform scale fitted to the stock
joints. The skeleton keeps the stock bone orientations at the model's own joint positions, and the QC uses the proportion trick:
`reference` = the stock skeleton, `proportions` = the model's, subtracted and played as an autoplay delta over m_anm/f_anm so the
animations keep the model's own proportions.

Writes, per model, under <out>/src/<slug>/: <slug>.qc, body.smd, phys.smd (one box per ragdoll bone), anims/reference.smd and
anims/proportions.smd, and materials as PNG; under <out>/addons/<slug>/: lua/autorun/<slug>_pm.lua, materials (VMT, and VTF when
VTFCmd is found), addon.json, and with --compile the .mdl set from studiomdl (Garry's Mod's bin/studiomdl.exe).
Hit boxes: one box per main bone around the vertices it carries most (groups head/chest/stomach/arms/legs as Valve's).
Ragdoll: the stock citizen's solids and joint limits ($jointconstrain), boxes sized to the model's own limbs.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gmod2cs2 as g
from srcmdl import SrcModel

MAX_VERTS = 60000   # per body part (Source's limit is 65536 vertices per model)
RZ = np.eye(3)      # model space -> SMD space: GMod's studiomdl writes SMD coordinates as they are (checked 8 Nov 2026: a -90 turn here came out -90 in the MDL)
HELPERS = ('ulna', 'wrist', 'elbow', 'shoulder', 'bicep', 'trapezius')   # procedural helpers of the citizen: left out
HITGROUP = {'head1': 1, 'neck1': 1, 'spine2': 2, 'spine4': 2, 'pelvis': 3, 'spine': 3, 'spine1': 3,
            'l_upperarm': 4, 'l_forearm': 4, 'l_hand': 4, 'r_upperarm': 5, 'r_forearm': 5, 'r_hand': 5,
            'l_thigh': 6, 'l_calf': 6, 'l_foot': 6, 'l_toe0': 6, 'r_thigh': 7, 'r_calf': 7, 'r_foot': 7, 'r_toe0': 7}
# ragdoll: the citizen's 19 solids; each takes the vertices of the bones listed (its own and the merged ones)
RAGDOLL = {'pelvis': ('pelvis', 'spine', 'spine1'), 'spine2': ('spine2', 'spine4', 'l_clavicle', 'r_clavicle'), 'head1': ('head1', 'neck1'),
           'l_clavicle': (), 'r_clavicle': (), 'l_upperarm': ('l_upperarm',), 'r_upperarm': ('r_upperarm',),
           'l_forearm': ('l_forearm',), 'r_forearm': ('r_forearm',), 'l_hand': ('l_hand', 'l_finger'), 'r_hand': ('r_hand', 'r_finger'),
           'l_thigh': ('l_thigh',), 'r_thigh': ('r_thigh',), 'l_calf': ('l_calf',), 'r_calf': ('r_calf',),
           'l_foot': ('l_foot',), 'r_foot': ('r_foot',), 'l_toe0': ('l_toe0',), 'r_toe0': ('r_toe0',)}


def short(name):
    s = g.short(name)
    if s: return s
    n = name.lower().replace('valvebiped.', '')
    return {'forward': 'vb_forward', 'anim_attachment_rh': 'vb_att_rh', 'anim_attachment_lh': 'vb_att_lh'}.get(n)


def euler(R):
    """Source RadianEuler (x, y, z) with R = Rz(z) Ry(y) Rx(x)"""
    y = -np.arcsin(np.clip(R[2, 0], -1, 1))
    if abs(R[2, 0]) < 0.99999: x, z = np.arctan2(R[2, 1], R[2, 2]), np.arctan2(R[1, 0], R[0, 0])
    else: x, z = np.arctan2(-R[1, 2], R[1, 1]), 0.0
    return x, y, z


# ---------------------------------------------------------------- the stock ValveBiped skeleton as a gmod2cs2 template
class VBTemplate:
    """A stock GMod player model's skeleton, named like CS2's joints so gmod2cs2.Converter can pose onto it."""
    def __init__(self, mdl):
        m = SrcModel(mdl)
        self.src = m
        self.vb, self.W, self.parent, self.order = {}, {}, {}, []
        kept = {}
        for i, b in enumerate(m.bones):
            s = short(b['name'])
            if s is None or any(s.endswith(h) for h in HELPERS): continue
            cs = g.VB2CS.get(s, s)
            if cs in self.W: continue
            p = b['parent']
            while p >= 0 and p not in kept: p = m.bones[p]['parent']
            kept[i] = cs
            self.vb[cs] = b['name']; self.W[cs] = (b['world'][:, :3].copy(), b['world'][:, 3].copy())
            self.parent[cs] = kept.get(p); self.order.append(cs)
        self.joints = list(self.order)
        self.stock = self
        self.W0 = dict(self.W)          # as stored (the frame the output is written in)
        # the posing code works facing +X (toes ahead); stock MDLs face other ways (the citizen: -Y). Turn about Z.
        f = sum(self.W['ball_' + s][1] - self.W['ankle_' + s][1] for s in 'LR'); f[2] = 0
        a = np.arctan2(f[1], f[0])
        self.Tf = g.rot_axis(np.array([0, 0, 1.]), -a)
        self.W = {c: (self.Tf @ R, self.Tf @ t) for c, (R, t) in self.W.items()}
        # attachments of the citizen (eyes, mouth, chest, hands, head): bone + local 3x4
        self.attachments = m_attachments(mdl, m)

    def J(self, n): return self.W[n][1]


def m_attachments(path, m):
    import struct
    d = open(path, 'rb').read()
    def s(o): e = d.index(b'\0', o); return d[o:e].decode('latin-1')
    na, ai = struct.unpack_from('<ii', d, 240)
    out = []
    for k in range(na):
        o = ai + k * 92
        out.append((s(o + struct.unpack_from('<i', d, o)[0]), m.bones[struct.unpack_from('<i', d, o + 8)[0]]['name'],
                    np.array(struct.unpack_from('<12f', d, o + 12)).reshape(3, 4)))
    return out


def ragdoll_limits(phy):
    """the citizen's ragdoll: {child bone: (parent bone, {axis: (min, max)})} from the .phy's text section"""
    t = open(phy, 'rb').read().decode('latin-1')
    names = dict(re.findall(r'"index" "(\d+)"\s*"name" "([^"]+)"', t))
    out = {}
    for blk in re.findall(r'ragdollconstraint \{(.*?)\}', t, re.S):
        kv = dict(re.findall(r'"(\w+)" "([^"]*)"', blk))
        out[names[kv['child']]] = (names[kv['parent']], {a: (float(kv[a + 'min']), float(kv[a + 'max'])) for a in 'xyz'})
    return out


# ---------------------------------------------------------------- one model
def material_info(root, slug, tex):
    b = tex.split('/')[-1]
    vmt = os.path.join(root, 'materials', 'fbx', slug, b + '.vmt')
    txt = open(vmt).read() if os.path.exists(vmt) else ''
    c = os.path.join(root, 'materials', 'fbx', slug, b + '_c.png'); n = os.path.join(root, 'materials', 'fbx', slug, b + '_n.png')
    return {'name': b, 'color': c if os.path.exists(c) else None, 'normal': n if os.path.exists(n) else None,
            'alphatest': '$alphatest' in txt}


def smd_skeleton(f, names, parents, local):
    f.write('version 1\nnodes\n')
    for i, (n, p) in enumerate(zip(names, parents)): f.write('%d "%s" %d\n' % (i, n, p))
    f.write('end\nskeleton\ntime 0\n')
    for i, (t, R) in enumerate(local):
        x, y, z = euler(R)
        f.write('%d %.6f %.6f %.6f %.6f %.6f %.6f\n' % (i, t[0], t[1], t[2], x, y, z))
    f.write('end\n')


def local_frames(names, parents, world):
    """world [(R, t)] in model space -> SMD local (t, R); root bones go into SMD space"""
    out = []
    for i, p in enumerate(parents):
        R, t = world[i]
        if p < 0: out.append((RZ @ t, RZ @ R))
        else:
            Rp, tp = world[p]; out.append((Rp.T @ (t - tp), Rp.T @ R))
    return out


def convert(it, cfg, out, log=print):
    slug, sex = it['slug'], it.get('sex', 'male')
    work = cfg['work']
    root = os.path.join(work, 'fbx', slug)
    npz = os.path.join(root, slug + '.npz')
    ref = cfg['ref_' + sex]
    t = VBTemplate(ref)
    m = SrcModel(npz)
    conv = g.Converter(m, t, log)
    conv.fixed_scale = it.get('scale')
    conv.transforms('ownall')
    own = conv.own_joints
    if 'spine_1' not in own and 'spine_0' in own and 'spine_2' in own:    # Riot rigs: no Spine1, put it half way
        own['spine_1'] = (np.asarray(own['spine_0']) + np.asarray(own['spine_2'])) / 2
    ot = g.own_template(t, own); conv.t = ot
    meshes = m.default_meshes(None)
    used, remap, V, N, weights = conv.convert_mesh(meshes)
    sc = conv.girth
    # skeleton: stock orientations, the model's own joint positions
    order = t.order
    names = [t.vb[c] for c in order]; idx = {c: i for i, c in enumerate(order)}
    parents = [idx[t.parent[c]] if t.parent[c] is not None else -1 for c in order]
    Tb = t.Tf.T                                       # back into the stock model's own frame
    world_own = [(Tb @ ot.W[c][0], Tb @ ot.W[c][1]) for c in order]; world_ref = [t.W0[c] for c in order]
    src = os.path.join(out, 'src', slug); os.makedirs(os.path.join(src, 'anims'), exist_ok=True)
    for fn, wd in (('anims/reference.smd', world_ref), ('anims/proportions.smd', world_own)):
        with open(os.path.join(src, fn), 'w', newline='\n') as f: smd_skeleton(f, names, parents, local_frames(names, parents, wd))
    # mesh
    UV = m.UV[used]
    mats = {}
    for me in meshes:
        if not len(me['tris']): continue
        tex = m.textures[m.skins[0][me['material']]]
        mats.setdefault(tex, []).append(remap[me['tris']])
    Vs = V @ Tb.T @ RZ.T; Ns = N @ Tb.T @ RZ.T
    vb_of = {c: idx[c] for c in order}
    flipped = 0
    infos = {}
    # Source allows 65536 vertices per model: a bigger mesh is split by material into several body parts (all always on)
    parts, cur, n = [], [], 0
    for tex, tl in sorted(mats.items(), key=lambda kv: -len(np.unique(np.vstack(kv[1])))):
        k = len(np.unique(np.vstack(tl)))
        if cur and n + k > MAX_VERTS: parts.append(cur); cur, n = [], 0
        cur.append(tex); n += k
    if cur: parts.append(cur)
    smds = ['body.smd'] + ['body%d.smd' % (i + 1) for i in range(1, len(parts))]
    for f_ in glob.glob(os.path.join(src, 'body*.smd')): os.remove(f_)
    for smd, part in zip(smds, parts):
        with open(os.path.join(src, smd), 'w', newline='\n') as f:
            smd_skeleton(f, names, parents, local_frames(names, parents, world_own))
            f.write('triangles\n')
            for tex in part:
                info = infos[tex] = material_info(root, slug, tex)
                for tri in np.vstack(mats[tex]):
                    a, b, c = Vs[tri]
                    if np.cross(b - a, c - a) @ Ns[tri].sum(0) < 0: tri = tri[[0, 2, 1]]; flipped += 1
                    f.write(info['name'] + '\n')
                    for v in tri:
                        w = [(vb_of[j], x) for j, x in weights[v] if x > 1e-4]
                        tot = sum(x for _, x in w) or 1.0
                        links = ' '.join('%d %.4f' % (j, x / tot) for j, x in w)
                        p, n = Vs[v], Ns[v]
                        f.write('%d %.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f %d %s\n' % (w[0][0], p[0], p[1], p[2], n[0], n[1], n[2],
                                                                                       UV[v, 0], 1 - UV[v, 1], len(w), links))
            f.write('end\n')
    # per-vertex dominant bone (VB short name), for hit boxes and the ragdoll
    dom = np.array([g.short(t.vb[max(w, key=lambda x: x[1])[0]]) or '' if w else '' for w in weights], dtype=object)
    def bone_box(c, verts, shrink=0.0, pct=(1, 99)):
        R, p = ot.W[c]
        L = (V[verts] - p) @ R            # bone-local coordinates
        lo, hi = np.percentile(L, pct[0], 0), np.percentile(L, pct[1], 0)
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * (1 - shrink)
        return mid - half, mid + half
    hb = []
    for c in order:
        s = g.short(t.vb[c])
        if s not in HITGROUP: continue
        sel = np.where(dom == s)[0]
        if len(sel) < 12: continue
        lo, hi = bone_box(c, sel)
        hb.append('$hbox %d "%s" %s %s' % (HITGROUP[s], t.vb[c], ' '.join('%.2f' % x for x in lo), ' '.join('%.2f' % x for x in hi)))
    # ragdoll: one box per solid (in SMD space, rigid to its bone)
    limits = ragdoll_limits(os.path.splitext(ref)[0] + '.phy')
    solids = []
    with open(os.path.join(src, 'phys.smd'), 'w', newline='\n') as f:
        smd_skeleton(f, names, parents, local_frames(names, parents, world_own))
        f.write('triangles\n')
        for s, carry in RAGDOLL.items():
            c = g.VB2CS[s]
            if c not in ot.W: continue
            sel = np.where(np.array([any(d == k or (k.endswith('_finger') and d.startswith(k)) for k in carry) for d in dom]))[0] if carry else []
            if len(sel) < 12:
                if carry: log('   ragdoll: %s has no mesh, left out' % s)
                continue
            lo, hi = bone_box(c, sel, shrink=0.12, pct=(3, 97))
            R, p = ot.W[c]
            corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            P = (corners @ R.T + p) @ Tb.T @ RZ.T
            bi = idx[c]
            for q in ((0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)):
                f.write('phy\n')
                for k in q: f.write('%d %.4f %.4f %.4f 0 0 1 0 0 1 %d 1\n' % (bi, P[k][0], P[k][1], P[k][2], bi))
            solids.append(t.vb[c])
        f.write('end\n')
    # QC
    mdlname = it['mdl']
    anm = 'f_anm.mdl' if sex == 'female' else 'm_anm.mdl'
    cd = it.get('cdmaterials', 'models/gmport/%s/' % slug)
    q = ['// %s: %s, made by create/playermodels/togmod.py from %s (private testing: %s)' % (slug, it['name'], os.path.basename(it['source']), it.get('note', '')),
         '$modelname "%s"' % mdlname.replace('models/', '', 1)] + ['$model "%s" "%s"' % (x[:-4], x) for x in smds] + [ '$cdmaterials "%s"' % cd,
         '$surfaceprop "flesh"', '$contents "solid"', '$illumposition 0 0 36', '$cbox 0 0 0 0 0 0',
         '$includemodel "%s"' % anm, '']
    for c in order:
        if t.vb[c].startswith('ValveBiped.Bip01_'): q.append('$bonemerge "%s"' % t.vb[c])
    q.append('')
    for nm, bone, M in t.attachments:
        bc = next(c for c in order if t.vb[c] == bone) if bone in t.vb.values() else None
        if bc is None: continue
        off = M[:, 3] * sc if bone.endswith(('Head1', 'Spine2', 'Spine4')) else M[:, 3]   # eyes, mouth, chest: sized with the body
        x, y, z = euler(M[:, :3])
        q.append('$attachment "%s" "%s" %.3f %.3f %.3f rotate %.2f %.2f %.2f' % (nm, bone, off[0], off[1], off[2],
                                                                               np.degrees(y), np.degrees(z), np.degrees(x)))
    q += ['', '$ikchain "rhand" "ValveBiped.Bip01_R_Hand" knee 0.707 0.707 0', '$ikchain "lhand" "ValveBiped.Bip01_L_Hand" knee 0.707 0.707 0',
          '$ikchain "rfoot" "ValveBiped.Bip01_R_Foot" knee 0.707 -0.707 0', '$ikchain "lfoot" "ValveBiped.Bip01_L_Foot" knee 0.707 -0.707 0', '',
          '$hboxset "default"'] + hb + ['',
          '$sequence "reference" "anims/reference.smd" fps 1',
          '$animation "a_proportions" "anims/proportions.smd" subtract "reference" 0',
          '$sequence "proportions" "a_proportions" predelta autoplay',
          '$sequence "ragdoll" "anims/proportions.smd" activity "ACT_DIERAGDOLL" 1 fps 30', '',
          '$collisionjoints "phys.smd" {', '\t$mass 90', '\t$inertia 10', '\t$damping 0.01', '\t$rotdamping 1.5',
          '\t$rootbone "ValveBiped.Bip01_Pelvis"']
    for child, (par, lim) in limits.items():
        if child not in solids: continue
        for a in 'xyz': q.append('\t$jointconstrain "%s" %s limit %.0f %.0f 0' % (child, a, lim[a][0], lim[a][1]))
    q.append('}')
    open(os.path.join(src, slug + '.qc'), 'w', newline='\n').write('\n'.join(q) + '\n')
    # materials: VMT + PNG (VTF by VTFCmd)
    add = os.path.join(out, 'addons', slug)
    md = os.path.join(add, 'materials', cd); os.makedirs(md, exist_ok=True)
    os.makedirs(os.path.join(src, 'materials'), exist_ok=True)
    for info in infos.values():
        lines = ['"VertexLitGeneric"', '{', '\t"$basetexture" "%s%s"' % (cd, info['name'])]
        if info['normal']: lines.append('\t"$bumpmap" "%s%s_n"' % (cd, info['name']))
        if info['alphatest']: lines += ['\t"$alphatest" "1"', '\t"$nocull" "1"']
        lines += ['\t"$halflambert" "1"', '}']
        open(os.path.join(md, info['name'] + '.vmt'), 'w', newline='\n').write('\n'.join(lines) + '\n')
        for k, sfx in (('color', ''), ('normal', '_n')):
            if info[k]: shutil.copy(info[k], os.path.join(src, 'materials', info['name'] + sfx + '.png'))
    # lua + addon.json
    ld = os.path.join(add, 'lua', 'autorun'); os.makedirs(ld, exist_ok=True)
    hands = 'models/weapons/c_arms_chell.mdl' if sex == 'female' else 'models/weapons/c_arms_citizen.mdl'
    open(os.path.join(ld, slug + '_pm.lua'), 'w', newline='\n').write(
        '-- %s (%s): made by togmod.py for private testing\n' % (it['name'], it.get('franchise', '')) +
        'player_manager.AddValidModel("%s", "%s")\n' % (it['name'], mdlname) +
        'player_manager.AddValidHands("%s", "%s", 0, "00000000")\n' % (it['name'], hands) +
        'list.Set("PlayerOptionsModel", "%s", "%s")\n' % (it['name'], mdlname))
    json.dump({'title': it['name'], 'type': 'model', 'tags': ['fun', 'cartoon'], 'ignore': ['*.psd', '*.png', '*.txt']},
              open(os.path.join(add, 'addon.json'), 'w'), indent='\t')
    rep = {'slug': slug, 'name': it['name'], 'mdl': mdlname, 'sex': sex, 'scale': round(sc, 3), 'vertices': int(len(V)),
           'triangles': int(sum(len(np.vstack(x)) for x in mats.values())), 'materials': [i['name'] for i in infos.values()],
           'hitboxes': len(hb), 'body_parts': len(smds), 'ragdoll_solids': len(solids), 'winding_flipped': flipped,
           'height': round(float(V[:, 2].max()), 1), 'bones_following_parent': conv.unknown}
    return rep, (V, UV, mats, infos, weights, ot, order, t)


# ---------------------------------------------------------------- textures and compile
def vtfcmd(cfg):
    for c in (cfg.get('vtfcmd'), r'C:\VTF\VTFEdit\VTFCmd.exe'):
        if c and os.path.exists(c): return c


def make_vtfs(cfg, out, slug, log=print):
    exe = vtfcmd(cfg)
    if not exe: log('   (no VTFCmd: textures left as PNG in src/%s/materials)' % slug); return
    src = os.path.join(out, 'src', slug, 'materials')
    vmts = glob.glob(os.path.join(out, 'addons', slug, 'materials', '**', '*.vmt'), recursive=True)
    if not vmts: return
    dst = os.path.dirname(vmts[0])
    for png in glob.glob(os.path.join(src, '*.png')):
        name = os.path.splitext(os.path.basename(png))[0]
        alpha = not name.endswith('_n') and any('"$alphatest"' in open(v).read() for v in vmts if os.path.basename(v)[:-4] == name)
        fmt = 'DXT5' if alpha else 'DXT1'          # (the PNGs all carry alpha, so -alphaformat decides: DXT1 unless alpha-tested)
        cap = '1024' if name.endswith('_n') else '2048'   # normal maps at 1024: May's 17 textures were 95 MB at 2048 DXT5
        r = subprocess.run([exe, '-file', png, '-output', dst, '-format', fmt, '-alphaformat', fmt, '-resize', '-rclampwidth', cap,
                            '-rclampheight', cap] + (['-flag', 'NORMAL'] if name.endswith('_n') else []), capture_output=True, text=True)
        if r.returncode or not os.path.exists(os.path.join(dst, name + '.vtf')): log('   ! VTFCmd failed on %s: %s' % (png, (r.stdout + r.stderr)[-300:]))


def find_studiomdl(cfg):
    c = [cfg.get('studiomdl')] + [os.path.join(lib, 'steamapps', 'common', 'GarrysMod', 'bin', x, 'studiomdl.exe') for lib in
                                   (r'C:\Program Files (x86)\Steam', r'D:\SteamLibrary', r'E:\SteamLibrary') for x in ('win64', '.')]
    return next((x for x in c if x and os.path.exists(x)), None)


def compile_model(cfg, out, slug, log=print):
    exe = find_studiomdl(cfg)
    if not exe: return 'no studiomdl (install Garry\'s Mod or set "studiomdl")'
    gm = os.path.dirname(os.path.dirname(exe)) if os.path.basename(os.path.dirname(exe)) == 'bin' else os.path.dirname(os.path.dirname(os.path.dirname(exe)))
    game = os.path.join(gm, 'garrysmod')
    src = os.path.join(out, 'src', slug)
    r = subprocess.run([exe, '-game', game, '-nop4', '-verbose', os.path.join(src, slug + '.qc')], capture_output=True, text=True,
                       encoding='latin-1', cwd=src)
    open(os.path.join(src, 'compile.log'), 'w').write(r.stdout + r.stderr)
    # studiomdl writes into <game>/models/...: move the set into the addon
    it_mdl = re.search(r'\$modelname "([^"]+)"', open(os.path.join(src, slug + '.qc')).read()).group(1)
    base = os.path.join(game, 'models', os.path.splitext(it_mdl)[0])
    files = [base + e for e in ('.mdl', '.vvd', '.phy', '.dx90.vtx', '.dx80.vtx', '.sw.vtx', '.vtx') if os.path.exists(base + e)]
    if not any(f.endswith('.mdl') for f in files):
        err = [l for l in (r.stdout + r.stderr).splitlines() if 'ERROR' in l.upper()]
        return 'FAILED: ' + ('; '.join(err[-3:]) or 'see compile.log')
    dst = os.path.join(out, 'addons', slug, 'models', os.path.dirname(it_mdl)); os.makedirs(dst, exist_ok=True)
    for f in files: shutil.move(f, os.path.join(dst, os.path.basename(f)))
    warn = sum(1 for l in r.stdout.splitlines() if l.startswith('WARNING'))
    return 'OK' + (' (%d warnings)' % warn if warn else '')


def preview(out, slug, data):
    from preview import render
    import poses
    V, UV, mats, infos, weights, ot, order, t = data
    from PIL import Image
    groups = []
    for tex, tl in mats.items():
        c = infos[tex]['color']
        groups.append((np.vstack(tl), np.asarray(Image.open(c).convert('RGB')) if c else None))
    pv = os.path.join(out, 'preview'); os.makedirs(pv, exist_ok=True)
    marks = np.array([ot.J(c) for c in order if 'finger' not in c])
    render(V, UV, groups, os.path.join(pv, slug + '_bind.png'), views=('front', 'side', 'back'), H=700, marks=marks,
           label='%s  on the ValveBiped skeleton (dots = its own joints, stock orientations)' % slug)
    render(V, UV, groups, os.path.join(pv, slug + '_front.png'), views=('three',), H=1024)     # clean picture for the Workshop


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('json'); ap.add_argument('--only'); ap.add_argument('--compile', action='store_true')
    ap.add_argument('--studiomdl'); ap.add_argument('--no-preview', action='store_true')
    a = ap.parse_args()
    cfg = json.load(open(a.json, encoding='utf-8'))
    if a.studiomdl: cfg['studiomdl'] = a.studiomdl
    out = cfg['out']; os.makedirs(out, exist_ok=True)
    reps = []
    for it in cfg['models']:
        if a.only and it['slug'] not in a.only.split(','): continue
        print('==', it['slug'], it['name'], flush=True)
        try:
            rep, data = convert(it, cfg, out)
            make_vtfs(cfg, out, it['slug'])
            if not a.no_preview:
                try: preview(out, it['slug'], data)
                except Exception as e: print('   preview failed:', e)
            rep['compile'] = compile_model(cfg, out, it['slug']) if a.compile else 'not compiled'
        except Exception as e:
            import traceback; traceback.print_exc()
            rep = {'slug': it['slug'], 'name': it['name'], 'compile': 'ERROR %s' % e}
        print('  ', json.dumps(rep), flush=True)
        reps.append(rep)
        os.makedirs(os.path.join(out, 'reports'), exist_ok=True)
        json.dump(rep, open(os.path.join(out, 'reports', it['slug'] + '.json'), 'w'), indent=1)
    print('\n%d models: %s' % (len(reps), ', '.join('%s %s' % (r['slug'], r.get('compile')) for r in reps)))


if __name__ == '__main__':
    main()
