"""mg_monsoon: a converted weapon prop (SMD + its csgo_complex PNGs, from gmod_assets.py / create/mdl2cs2.py) -> a GLB the repo's weapon
builder (tools/weapons/build_weapon.py) takes, already placed in the stock skeleton's weapon_offset space (batch G, docs/WEAPONS.md).

usage:
  python mv_weapon_glb.py <prop.smd> <out.glb> --forward=-y --length <in> [--anchor <sx,sz,tx,tz>] [--drop mat,mat] [--components]

  --forward    which SMD axis the muzzle points along (x, -x, y, -y); +z stays up
  --length     overall length in weapon units (the stock skeleton's scale: CS2's SCAR-20 body is 42.55 for a ~1.04 m rifle)
  --anchor     after scaling, move point (sx, sz) of the turned mesh (x forward, z up) to (tx, tz): e.g. the trigger onto the stock
               trigger bone, so the builder's shift_wo stays [0, 0, 0]; y is centred on the bore (mesh bounds centre)
  --yshift     added to y after centring (put the bore on the stock bone's y)
  --drop       SMD materials to leave out (e.g. a sling)
  --components print every connected component (faces, material, bounds in the turned + anchored frame) to pick the rules from

The GLB is in glTF's frame (Y up) and metres, so build_weapon.py (39.37 x scale) gives the weapon units back with scale 1.0 and no axes.
Textures: <material>_color / _normal / _rough / _metal PNGs beside the vmat (materials/<vmat dir>); rough + metal are packed into a glTF
metallicRoughness image. Reads only files already in the addon; writes one GLB. AI-generated (Claude) for skink52.
"""
import io, json, os, re, struct, sys
import numpy as np
from PIL import Image

INCH = 39.3701


def read_smd(path):
    L = open(path, encoding='utf-8', errors='replace').read().split('\n')
    i = next(k for k, l in enumerate(L) if l.strip() == 'triangles') + 1
    P, N, T, M = [], [], [], []
    while i + 3 < len(L) and L[i].strip() != 'end':
        m = L[i].strip()
        for k in (1, 2, 3):
            f = L[i + k].split()
            P.append([float(x) for x in f[1:4]]); N.append([float(x) for x in f[4:7]]); T.append([float(x) for x in f[7:9]])
        M.append(m); i += 4
    return np.array(P), np.array(N), np.array(T), M


def turn(V, fwd):
    """SMD axes -> x forward (muzzle), y left, z up"""
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    if fwd == 'x': return np.stack([x, y, z], 1)
    if fwd == '-x': return np.stack([-x, -y, z], 1)
    if fwd == 'y': return np.stack([y, -x, z], 1)
    if fwd == '-y': return np.stack([-y, x, z], 1)
    raise SystemExit('--forward must be x, -x, y or -y')


def components(F):
    parent = list(range(F.max() + 1))
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for a, b, c in F:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra; parent[find(rc)] = ra
    return np.array([find(f[0]) for f in F])


def weld(P, N, T, M):
    """indexed mesh from the SMD's corner list (corners equal in position, normal, uv and material merge)"""
    key = np.round(np.hstack([P, N * 100, T * 1000]), 3)
    mats = sorted(set(M)); mi = np.repeat([mats.index(m) for m in M], 3)
    key = np.hstack([key, mi[:, None]])
    u, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    V = np.zeros((len(u), 3)); Nn = np.zeros((len(u), 3)); Tt = np.zeros((len(u), 2))
    V[inv] = P; Nn[inv] = N; Tt[inv] = T
    return V, Nn, Tt, inv.reshape(-1, 3), mats, mi.reshape(-1, 3)[:, 0]


def png_bytes(im):
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()


def write_glb(path, prims, images):
    """prims: [(V metres in glTF frame, N, T (uv, top-left), F, material index)], images: [(color, normal|None, mr|None) PIL]"""
    bin_ = bytearray(); views = []; accs = []
    def view(data, target=None):
        while len(bin_) % 4: bin_.append(0)
        off = len(bin_); bin_.extend(data)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target: v['target'] = target
        views.append(v); return len(views) - 1
    def acc(arr, ctype, typ, target, minmax=False):
        a = {'bufferView': view(arr.tobytes(), target), 'componentType': ctype, 'count': len(arr), 'type': typ}
        if minmax: a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
        accs.append(a); return len(accs) - 1
    gl_prims = []
    for V, N, T, F, mat in prims:
        gl_prims.append({'attributes': {'POSITION': acc(V.astype(np.float32), 5126, 'VEC3', 34962, True),
                                        'NORMAL': acc(N.astype(np.float32), 5126, 'VEC3', 34962),
                                        'TEXCOORD_0': acc(T.astype(np.float32), 5126, 'VEC2', 34962)},
                         'indices': acc(F.astype(np.uint32).reshape(-1), 5125, 'SCALAR', 34963), 'material': mat, 'mode': 4})
    imgs, texs, mats = [], [], []
    def tex(im):
        imgs.append({'bufferView': view(png_bytes(im)), 'mimeType': 'image/png'}); texs.append({'source': len(imgs) - 1}); return len(texs) - 1
    for name, col, nrm, mr in images:
        m = {'name': name, 'pbrMetallicRoughness': {'baseColorTexture': {'index': tex(col)}}}
        if mr is not None: m['pbrMetallicRoughness']['metallicRoughnessTexture'] = {'index': tex(mr)}
        else: m['pbrMetallicRoughness'].update(metallicFactor=0.0, roughnessFactor=0.8)
        if nrm is not None: m['normalTexture'] = {'index': tex(nrm)}
        mats.append(m)
    g = {'asset': {'version': '2.0', 'generator': 'mg_monsoon tools/mv_weapon_glb.py'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
         'nodes': [{'mesh': 0, 'name': 'weapon'}], 'meshes': [{'primitives': gl_prims}], 'accessors': accs, 'bufferViews': views,
         'buffers': [{'byteLength': len(bin_)}], 'materials': mats, 'images': imgs, 'textures': texs}
    js = json.dumps(g).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    while len(bin_) % 4: bin_.append(0)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack('<II', len(bin_), 0x004E4942)); f.write(bin_)


def material_pngs(smd, mat):
    """the PNGs a converted vmat names (materials/<dir>/<mat>_color.png ...), found from the vmat beside the model's materials"""
    addon = smd.replace('\\', '/').split('/models/')[0]
    name = os.path.splitext(mat)[0]
    sub = os.path.dirname(smd.replace('\\', '/').split('/models/', 1)[1])
    d = os.path.join(addon, 'materials', 'models', sub)
    get = lambda k: os.path.join(d, '%s_%s.png' % (name, k))
    col = Image.open(get('color')).convert('RGB') if os.path.exists(get('color')) else Image.new('RGB', (8, 8), (90, 80, 70))
    nrm = Image.open(get('normal')).convert('RGB') if os.path.exists(get('normal')) else None
    rough = next((get(k) for k in ('rough', 'rough45') if os.path.exists(get(k))), None)
    rp = next((p for p in [os.path.join(d, f) for f in os.listdir(d)] if re.match(re.escape(name) + r'_rough\d*\.png$', os.path.basename(p))), rough) if os.path.isdir(d) else rough
    mr = None
    if rp:
        r = Image.open(rp).convert('L').resize(col.size)
        mp = get('metal'); m = Image.open(mp).convert('L').resize(col.size) if os.path.exists(mp) else Image.new('L', col.size, 0)
        mr = Image.merge('RGB', (Image.new('L', col.size, 255), r, m))
    return col, nrm, mr


def main(argv):
    opt = {a.split('=')[0]: (a.split('=', 1)[1] if '=' in a else True) for a in argv if a.startswith('--')}
    args = [a for a in argv if not a.startswith('--')]
    for k in ('--length', '--anchor', '--drop', '--yshift'):          # "--length 45.7" form
        if k in argv and opt.get(k) is True: opt[k] = argv[argv.index(k) + 1]; args.remove(opt[k])
    smd, out = args[0], args[1]
    P, N, T, M = read_smd(smd)
    drop = set((opt.get('--drop') or '').split(',')) - {''}
    keep = np.array([m.split('.')[0] not in drop and m not in drop for m in M]).repeat(3)
    P, N, T = P[keep], N[keep], T[keep]; M = [m for m in M if m.split('.')[0] not in drop and m not in drop]
    fwd = opt.get('--forward', '-y'); P = turn(P, fwd); N = turn(N, fwd)
    s = float(opt['--length']) / (P[:, 0].max() - P[:, 0].min()); P = P * s
    P[:, 1] -= (P[:, 1].max() + P[:, 1].min()) / 2
    P[:, 1] += float(opt.get('--yshift') or 0)
    if opt.get('--anchor'):
        sx, sz, tx, tz = [float(v) for v in opt['--anchor'].split(',')]
        P[:, 0] += tx - sx; P[:, 2] += tz - sz
    V, Nn, Tt, F, mats, fmat = weld(P, N, T, M)
    print('%s: %d tris, materials %s, scale %.4f, bounds %s .. %s' % (os.path.basename(smd), len(F), mats, s, V.min(0).round(2), V.max(0).round(2)))
    if opt.get('--components'):
        comp = components(F)
        rows = []
        for c in np.unique(comp):
            fm = comp == c; vb = V[np.unique(F[fm])]
            rows.append((vb[:, 0].min(), fm.sum(), mats[fmat[fm][0]], vb.min(0), vb.max(0)))
        for x0, n, m, lo, hi in sorted(rows, key=lambda r: r[0]):
            print('  %5d faces %-22s x %6.2f..%6.2f  y %5.2f..%5.2f  z %6.2f..%6.2f' % (n, m, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    prims, images = [], []
    for k, m in enumerate(mats):
        sel = fmat == k; Fk = F[sel]; used = np.unique(Fk); remap = np.full(len(V), -1); remap[used] = np.arange(len(used))
        Vk = V[used] / INCH; Nk = Nn[used]; Tk = Tt[used].copy(); Tk[:, 1] = 1 - Tk[:, 1]       # SMD uv bottom-left -> glTF top-left
        g = np.stack([Vk[:, 0], Vk[:, 2], -Vk[:, 1]], 1); gn = np.stack([Nk[:, 0], Nk[:, 2], -Nk[:, 1]], 1)   # Source -> glTF (Y up)
        prims.append((g, gn, Tk, remap[Fk], k))
        col, nrm, mr = material_pngs(smd, m)
        images.append((os.path.splitext(m)[0], col, nrm, mr))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    write_glb(out, prims, images)
    print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1:])
