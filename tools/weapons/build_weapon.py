"""Build a CS2 weapon model (vmdl + DMX mesh/hull/mag + stock anims + materials) from an FBX, rigged to a stock weapon skeleton."""
import os, re, shutil, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbxmesh, dmxmodel, dmx, hull, scope, scope2, glbmesh

STOCK = os.environ.get("WW1_STOCK", "C:/source2/trenchwarfare assets/stock")
ANIMS = ['dropped', 'reload', 'shoot', 'inventory_inspect', 'inventory_icon']

def parse_skeleton(vmdl_text):
    """returns list of (name, origin, parent_name) from the Skeleton block"""
    i = vmdl_text.index('_class = "Skeleton"')
    bones = []; stack = []; depth = 0; j = i
    cur = None
    for m in re.finditer(r'\{|\}|_class = "Bone"|name = "([^"]*)"|origin = \[ ([^\]]*) \]', vmdl_text[i:]):
        tok = m.group(0)
        if tok == '{': depth += 1
        elif tok == '}':
            if stack and stack[-1][1] == depth: stack.pop()
            depth -= 1
            if depth < 0: break
        elif tok == '_class = "Bone"': cur = {'depth': depth}
        elif tok.startswith('name') and cur is not None and 'name' not in cur: cur['name'] = m.group(1)
        elif tok.startswith('origin') and cur is not None:
            cur['origin'] = tuple(float(x) for x in m.group(2).split(','))
            parent = stack[-1][0] if stack else None
            bones.append((cur['name'], cur['origin'], parent)); stack.append((cur['name'], cur['depth'])); cur = None
    return bones

def joint_tree(bones):
    els = {}; roots = []
    for name, origin, parent in bones:
        j = dmxmodel.joint(name, origin); els[name] = j
        if parent is None: roots.append(j)
        else: els[parent]['children'].items.append(j)
    order = []
    for r in roots: dmxmodel.flatten(r, order)
    return roots, [j.name for j in order]

def build(cfg):
    name, sub, out = cfg['name'], cfg['sub'], cfg['out']
    stock = cfg['stock']
    prefix = cfg.get('stock_prefix', 'weapon_snip')
    tmpl = open(f'{STOCK}/{prefix}_{stock}.vmdl').read()
    magtmpl = open(f'{STOCK}/{prefix}_{stock}_mag.vmdl').read()
    mag_has_skel = '_class = "Skeleton"' in magtmpl
    bones = parse_skeleton(tmpl)
    wo = np.array([b[1] for b in bones if b[0] == 'weapon'][0])   # weapon bone = weapon_offset origin in model space
    roots, jnames = joint_tree(bones)
    jidx = {n: i for i, n in enumerate(jnames)}
    magbone = 'clip' if 'clip' in jidx else 'magazine'
    print('skeleton', jnames, 'weapon origin', wo)

    if 'glb' in cfg:
        g, gb, parts = glbmesh.load(cfg['glb'], cfg.get('scale', 1.0), cfg.get('axes'))
        for i, p in enumerate(parts): p.index = i
    else:
        parts = fbxmesh.load(cfg['fbx'], cfg.get('axes', 'zxy'), cfg.get('scale', 1.0), cfg.get('flipv', False))
        for i, p in enumerate(parts): p.index = i
    for p in parts: p.T[:, 1] = 1 - p.T[:, 1]   # FBX/OBJ UVs are bottom-left; DMX texcoords are top-left
    drop = set(cfg.get('drop_parts', [])); parts = [p for p in parts if p.index not in drop]
    for idx, mv in cfg.get('part_moves', {}).items():
        for p in parts:
            if p.index == int(idx): p.V = p.V + np.array(mv)
    shift = np.array(cfg['shift_wo']) + wo   # mesh coords -> model space
    V=[]; N=[]; T=[]; F=[]; B=[]; base = 0; magmask = []; pmat = []
    pb_idx = {int(k): v for k, v in cfg.get('part_bone_idx', {}).items()}
    for p in parts:
        bone = pb_idx.get(p.index, cfg.get('part_bone', {}).get(p.name, 'weapon_offset'))
        fb = np.full(len(p.F), jidx[bone.replace('mag', magbone) if bone == 'mag' else bone], np.int32)
        fm = np.zeros(len(p.F), bool)
        if p.index in cfg.get('mag_parts', []): fm[:] = True; fb[:] = jidx[magbone]
        comp = None; keepf = np.ones(len(p.F), bool)
        for rule in cfg.get('rules', []):
            if rule.get('part') not in (None, p.name, p.index): continue
            x0,x1,y0,y1,z0,z1 = rule['box']
            if rule.get('mode', 'faces') == 'faces':
                P = p.V[p.F]
                inb = ((P[:,:,0]>x0)&(P[:,:,0]<x1)&(P[:,:,1]>y0)&(P[:,:,1]<y1)&(P[:,:,2]>z0)&(P[:,:,2]<z1)).all(1)
            else:
                if comp is None: comp = fbxmesh.components(p.V, p.F)
                inb = np.zeros(len(p.F), bool)
                for c in np.unique(comp):
                    m = comp == c; vb = p.V[np.unique(p.F[m])]
                    if vb[:,0].min()>x0 and vb[:,0].max()<x1 and vb[:,1].min()>y0 and vb[:,1].max()<y1 and vb[:,2].min()>z0 and vb[:,2].max()<z1: inb[m] = True
            if rule.get('drop'): keepf[inb] = False; print(f"  rule drop         {p.name:<10} faces {inb.sum()}"); continue
            if rule.get('move'):   # translate/rotate the selected faces' vertices (vertices unique to them)
                vs = np.unique(p.F[inb]); mv = rule['move']
                if rule.get('rot180z'):   # rotate 180 deg about a vertical axis at (cx, cy) first
                    cx, cy = rule['rot180z']; p.V[vs, 0] = 2*cx - p.V[vs, 0]; p.V[vs, 1] = 2*cy - p.V[vs, 1]; p.N[vs, 0] *= -1; p.N[vs, 1] *= -1
                p.V[vs] = p.V[vs] + np.array(mv)
            b = rule.get('bone')
            if b: fb[inb] = jidx[magbone if b == 'mag' else b]
            if rule.get('mag'): fm[inb] = True
            print(f"  rule {str(b):<12} {p.name:<10} faces {inb.sum()}")
        V.append(p.V + shift); N.append(p.N); T.append(p.T); F.append(p.F[keepf] + base); B.append(fb[keepf]); magmask.append(fm[keepf]); base += len(p.V)
        pmat.append(np.full(int(keepf.sum()), 10 + (p.material or 0) if 'glb' in cfg and getattr(p, 'material', None) is not None else 0, np.int32))
    scopemask = pmat   # 0 = main material, 1 = scope steel, 2 = scope brass, 10+k = glTF material k
    for bx in cfg.get('boxes', []):   # extra generated boxes (e.g. a magazine body hidden in the grip), steel material
        bV, bN, bT, bF, bM = scope2.box(*bx['box'], mat=bx.get('mat', 0))
        b = bx.get('bone', 'weapon_offset'); b = magbone if b == 'mag' else b
        V.append(bV + shift); N.append(bN); T.append(bT); F.append(bF + base); B.append(np.full(len(bF), jidx[b], np.int32)); magmask.append(np.full(len(bF), bool(bx.get('mag')))); scopemask.append(bM.astype(np.int32) + 1); base += len(bV)
    if cfg.get('scope'):
        sc = cfg['scope']
        gen = {'allied': scope2.allied, 'axis': scope2.axis}[sc['style']]
        # auto-seat: receiver top under each mount -> its base; tube bottom clears everything under its span,
        # including the bolt handle at full lift (rotated about the bore axis)
        Vall = np.vstack(V) - wo; Ball = np.concatenate(B); yc = sc['y']; L = 11.5; r = 0.5
        bolt_bones = [jidx[n] for n in ('bolt', 'bolt_action') if n in jidx]
        vb0 = np.concatenate([np.full(len(f), bb) for f, bb in zip(F, B)]) if False else None
        lifted = []
        for f, bb in zip(F, B):
            m = np.isin(bb, bolt_bones)
            if m.any(): lifted.append(np.unique(f[m]))
        if lifted:
            idx = np.unique(np.concatenate(lifted)); Pb = Vall[idx]; ay, az = cfg['bore_wo']
            ang = np.radians(-40.0); dy, dz = Pb[:,1]-ay, Pb[:,2]-az
            rot = Pb.copy(); rot[:,1] = ay + dy*np.cos(ang) - dz*np.sin(ang); rot[:,2] = az + dy*np.sin(ang) + dz*np.cos(ang)
            Vall = np.vstack([Vall, rot])
        under = Vall[(np.abs(Vall[:,1]-yc) < r + 0.05)]
        yp = sc.get('y_post', yc)
        wide = Vall[(np.abs(Vall[:,1]-yp) < 0.35)]
        base_z = [float(wide[np.abs(wide[:,0]-mx) < 0.45, 2].max()) - 0.05 for mx in sc['mounts']]
        span = under[(under[:,0] > sc['x0']) & (under[:,0] < sc['x0'] + L)]
        hi = span[span[:,2] > span[:,2].max() - 0.3]; print('  scope clearance driven by verts near', hi.mean(0).round(2), 'n', len(hi))
        z = float(span[:,2].max()) + r + sc.get('clear', 0.12)
        print(f"  scope seat: bases {np.round(base_z,2)}, axis z {z:.2f}")
        sV, sN, sT, sF, sM = gen(sc['x0'], yc, z, base_z, sc['mounts'], **({'y_post': sc['y_post']} if 'y_post' in sc else {}))
        V.append(sV + wo); N.append(sN); T.append(sT); F.append(sF + base); B.append(np.full(len(sF), jidx['weapon_offset'], np.int32)); magmask.append(np.zeros(len(sF), bool)); scopemask.append(np.where(sM == 3, 3, sM + 1).astype(np.int32)); base += len(sV)
        print('  scope faces', len(sF))
    V=np.vstack(V); N=np.vstack(N); T=np.vstack(T); F=np.vstack(F); B=np.concatenate(B); magmask=np.concatenate(magmask); scopemask=np.concatenate(scopemask)
    # per-vertex bone = bone of first face using it (faces split by part so consistent)
    vb = np.full(len(V), -1, np.int32)
    for f, b in zip(F, B): vb[f] = np.where(vb[f] < 0, b, vb[f])
    # split vertices shared between faces of different bones
    conflict = np.zeros(len(F), bool)
    for k, (f, b) in enumerate(zip(F, B)):
        if (vb[f] != b).any(): conflict[k] = True
    if conflict.any():
        addV=[]; addN=[]; addT=[]; addB=[]; nxt = len(V)
        for k in np.where(conflict)[0]:
            f = F[k].copy()
            for q in range(3):
                if vb[f[q]] != B[k]:
                    addV.append(V[f[q]]); addN.append(N[f[q]]); addT.append(T[f[q]]); addB.append(B[k]); f[q] = nxt; nxt += 1
            F[k] = f
        V = np.vstack([V, addV]); N = np.vstack([N, addN]); T = np.vstack([T, addT]); vb = np.concatenate([vb, addB])
    Vw, Nw, Tw, Fw = fbxmesh.weld(np.hstack([V, vb[:,None]]), N, T, F)   # weld keeps bone as 4th coord (face order preserved)
    vbw = Vw[:,3].astype(np.int32); Vw = Vw[:,:3]
    TAN = fbxmesh.tangents(Vw, Nw, Tw, Fw)
    mtl = f'materials/{sub}/{name}.vmat'
    mdir = os.path.join(out, sub); os.makedirs(mdir, exist_ok=True)
    gl_mtl = {}
    if 'glb' in cfg:   # one material per glTF material actually used, textures exported from the GLB
        from material import make_material
        for k in np.unique(scopemask[scopemask >= 10]) - 10:
            mname = re.sub(r'[^a-z0-9]+', '_', (g['materials'][k].get('name') or f'mat{k}').lower())
            tex = glbmesh.export_textures(g, gb, int(k), f'/tmp/gltex_{name}', mname)
            make_material(out, sub, f'{name}_{mname}', tex, size=cfg.get('texsize', 2048), flip_green=cfg.get('flip_green', False))
            gl_mtl[10 + k] = f'materials/{sub}/{name}_{mname}.vmat'; print('  material', k, mname, list(tex))

    # body mesh (includes mag faces bound to clip); scope faces get their own material
    MATS = {0: mtl, 1: 'materials/models/weapons/ww1/scope/scope.vmat', 2: 'materials/models/weapons/ww1/scope/brass.vmat', 3: 'materials/models/weapons/ww1/scope/glass.vmat', **gl_mtl}
    def mtl_groups(mask):
        ids = np.unique(mask); return MATS[int(ids[0])] if len(ids) == 1 else [(mask == i, MATS[int(i)]) for i in ids]
    body_mtl = mtl_groups(scopemask)
    root = dmxmodel.build_model(f'{name}_body', roots, f'{name}_body', Vw, Nw, Tw, TAN, Fw, vbw, body_mtl)
    dmxmodel.write_model(os.path.join(mdir, f'{name}_body.dmx'), root)
    # hull: body without mag, positions only
    keep = ~magmask & ~np.isin(scopemask, [1, 2, 3])
    Vh, Fh = hull.convex_hull(hull.support_points(V[np.unique(F[keep])]))
    hullroot = dmxmodel.build_model(f'{name}_hull', [], '', Vh, None, None, None, Fh, None, '$WeaponSniper', hull=True)
    dmxmodel.write_model(os.path.join(mdir, f'{name}_hull.dmx'), hullroot)
    print('hull verts', len(Vh), 'polys', len(Fh))
    # mag model: mag faces, relative to clip bone (model space position)
    clip_pos = wo + np.array([b[1] for b in bones if b[0] == magbone][0])
    if magmask.any():
        Fm = F[magmask]; used = np.unique(Fm); remap = {o: i for i, o in enumerate(used)}
        Vm = V[used] - clip_pos; Nm = N[used]; Tm = T[used]; Fm2 = np.vectorize(remap.get)(Fm); Mm = scopemask[magmask]
        Vm, Nm, Tm, Fm2 = fbxmesh.weld(Vm, Nm, Tm, Fm2); TANm = fbxmesh.tangents(Vm, Nm, Tm, Fm2)
        mag_mtl = mtl_groups(Mm)
    else:   # tiny cube stub (effectively invisible, still a valid mesh/hull)
        s = 0.05; Vm = np.array([[x,y,z] for x in (-s,s) for y in (-s,s) for z in (-s,s)], float)
        Fm2 = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],[2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]])
        Nm = Vm / np.linalg.norm(Vm, axis=1, keepdims=True); Tm = np.zeros((8,2)); TANm = np.array([[1,0,0,1.0]]*8); mag_mtl = mtl
    if mag_has_skel:
        magroot = dmxmodel.build_model(f'{name}_mag', [dmxmodel.joint(magbone, (0,0,0))], f'{name}_mag', Vm, Nm, Tm, TANm, Fm2, np.zeros(len(Vm), np.int32), mag_mtl)
    else:
        magroot = dmxmodel.build_model(f'{name}_mag', [], f'{name}_mag', Vm, Nm, Tm, TANm, Fm2, None, mag_mtl)
    dmxmodel.write_model(os.path.join(mdir, f'{name}_mag_mesh.dmx'), magroot)
    Vmh, Fmh = hull.convex_hull(hull.support_points(Vm)) if len(Vm) > 4 else (Vm, [[0, 1, 2]])
    maghull = dmxmodel.build_model(f'{name}_mag_hull', [], '', Vmh, None, None, None, Fmh, None, '$WeaponMagazine', hull=True)
    dmxmodel.write_model(os.path.join(mdir, f'{name}_mag_hull.dmx'), maghull)
    # anims
    anims = [m[len(f'weapons/models/{stock}/{prefix}_{stock}_'):-4] for m in re.findall(r'source_filename = "([^"]*)"', tmpl)]
    for a in anims: shutil.copy(f'{STOCK}/{prefix}_{stock}_{a}.dmx', os.path.join(mdir, f'{name}_anim_{a}.dmx'))
    # vmdl from template
    Vwo = Vw - wo
    t = tmpl
    t = re.sub(rf'weapons/models/{stock}/{prefix}_{stock}_body_\w+\.dmx', f'{sub}/{name}_body.dmx', t)
    for a in anims: t = t.replace(f'weapons/models/{stock}/{prefix}_{stock}_{a}.dmx', f'{sub}/{name}_anim_{a}.dmx')
    t = t.replace(f'weapons/models/{stock}/{prefix}_{stock}_mag.vmdl', f'{sub}/{name}_mag.vmdl')
    t = t.replace(f'weapons/models/{stock}/{prefix}_{stock}_hull.dmx', f'{sub}/{name}_hull.dmx')
    bore = cfg['bore_wo']   # (y, z) of the bore axis in weapon_offset space
    muzzle = (float(Vwo[:,0].max()) - 0.2, bore[0], bore[1])
    t = re.sub(r'(name = "muzzle_flash"\n(?:.*\n){2}\s*relative_origin = )\[[^\]]*\]', lambda m: m.group(1) + '[ %.4f, %.4f, %.4f ]' % muzzle, t)
    lo, hi = Vwo.min(0), Vwo.max(0)
    t = re.sub(r'hitbox_mins = \[[^\]]*\]', 'hitbox_mins = [ %.4f, %.4f, %.4f ]' % tuple(lo), t)
    t = re.sub(r'hitbox_maxs = \[[^\]]*\]', 'hitbox_maxs = [ %.4f, %.4f, %.4f ]' % tuple(hi), t)
    open(os.path.join(mdir, f'{name}.vmdl'), 'w', newline='\n').write(t)
    mt = magtmpl
    mt = mt.replace(f'weapons/models/{stock}/{prefix}_{stock}_mag_mag.dmx', f'{sub}/{name}_mag_mesh.dmx').replace(f'weapons/models/{stock}/{prefix}_{stock}_mag_hull.dmx', f'{sub}/{name}_mag_hull.dmx')
    open(os.path.join(mdir, f'{name}_mag.vmdl'), 'w', newline='\n').write(mt)
    print('body verts', len(Vw), 'tris', len(Fw), 'mag tris', len(Fm2), 'bounds(wo)', lo.round(2), hi.round(2), 'muzzle', np.round(muzzle, 2))

    # debug overlay vs stock mesh (weapon_offset space), side + top
    h, els = dmx.read(f'{STOCK}/{prefix}_{stock}_body_hd1.dmx')
    mesh = [e for e in els if e.type == 'DmeMesh'][0]; sv = mesh['currentState']['position$0'].items - wo
    sf = mesh['currentState']['faceSets'].items[0]['faces'].items if False else None
    def view(ax, ay, fn, scale=14):
        allp = np.vstack([Vwo[:, [ax, ay]], sv[:, [ax, ay]]]); lo2 = allp.min(0) - 1; hi2 = allp.max(0) + 1
        w = int((hi2[0]-lo2[0])*scale); hh = int((hi2[1]-lo2[1])*scale)
        im = Image.new('RGB', (w, hh), (20,20,20)); d = ImageDraw.Draw(im)
        for gx in range(int(lo2[0]), int(hi2[0])+1, 5): d.line([((gx-lo2[0])*scale, 0), ((gx-lo2[0])*scale, hh)], fill=(50,50,50))
        for gy in range(int(lo2[1]), int(hi2[1])+1, 5): d.line([(0, hh-(gy-lo2[1])*scale), (w, hh-(gy-lo2[1])*scale)], fill=(50,50,50))
        P = np.stack([(sv[:,ax]-lo2[0])*scale, hh-(sv[:,ay]-lo2[1])*scale], 1)
        d.point([tuple(p) for p in P[::2]], fill=(90,90,200))
        P = np.stack([(Vwo[:,ax]-lo2[0])*scale, hh-(Vwo[:,ay]-lo2[1])*scale], 1)
        cols = {jidx['weapon_offset']: (230,230,230), jidx[magbone]: (255,80,80), jidx['trigger']: (80,255,80)}
        for a, b, c in Fw:
            col = cols.get(vbw[a], (255,200,0))
            d.polygon([tuple(P[a]), tuple(P[b]), tuple(P[c])], outline=col)
        for nme, org, par in bones:
            pos = np.array(org);
            if par and par != 'weapon':
                pp = {b[0]: np.array(b[1]) for b in bones}; q = par;
                while q and q != 'weapon_offset': pos = pos + pp[q]; q = [b[2] for b in bones if b[0] == q][0]
            if nme in ('weapon',): continue
            x, y = (pos[ax]-lo2[0])*scale, hh-(pos[ay]-lo2[1])*scale
            d.ellipse([x-4, y-4, x+4, y+4], fill=(255,0,255)); d.text((x+5, y-5), nme, fill=(255,0,255))
        im.save(fn)
    view(0, 2, os.path.join(out, f'{name}_debug_side.png')); view(0, 1, os.path.join(out, f'{name}_debug_top.png'), scale=20)
    return Vwo

if __name__ == '__main__':
    import json
    cfg = json.load(open(sys.argv[1]))
    build(cfg)
