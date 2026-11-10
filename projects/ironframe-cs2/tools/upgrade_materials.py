"""Hard-surface material upgrade for frames already converted (no mesh reconversion): rewrites every base vmat in
out/addon/materials/ifr/frames/<key>/ with per-pixel roughness / metalness / AO / tint mask and edge-wear + grime baked into the colour
map (create/hardsurface_mat.py), then re-derives the _scorched / _wrecked vmats and their colour maps (create/damage_tex.py).

usage: python -I tools/upgrade_materials.py [--only key,key] [--restore] [--size-cap 2048]
  Originals are backed up once to <work>/mat_orig/<key>/ (vmats + every png they use) and are always the input, so re-runs are
  idempotent; --restore copies them back (undo). Source gloss masks (phong exponent maps, normal-alpha / separate env-map masks)
  are read from the frame's extracted GMod item when its VMT is found; else from the converted roughness map.
  Mesh masks (feature edges, AO, object-space noise) come from the frame's LOD0 legs/upper SMDs.
Prints one line per material; writes <work>/reports/materials.json."""
import glob, json, os, re, shutil, sys, time
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.join(os.path.dirname(os.path.dirname(PROJ)), 'create')
sys.path.insert(0, CREATE); sys.path.insert(0, os.path.join(CREATE, 'playermodels'))
import hardsurface_mat as HS, damage_tex, vtf                       # noqa: E402
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUT = os.path.join(PROJ, 'out', 'addon')
CAT = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))
WORK = os.environ.get('IF_WORK', CAT['paths']['work'])
BACK = os.path.join(WORK, 'mat_orig')
BASEGAME = r'C:\source1\playermodels\basegame'


def log(*a): print(*a, flush=True)


def read_smd(path):
    """-> P (n,3), N (n,3), UV (n,2) image convention (v from the top), mats [face] (one vertex per corner, unwelded)"""
    L = open(path, encoding='utf-8', errors='replace').read().split('\n')
    i = L.index('triangles') + 1
    end = len(L) - 1
    while end > i and L[end].strip() != 'end': end -= 1
    blk = L[i:end]; nf = len(blk) // 4
    mats = blk[0::4][:nf]
    rows = [blk[4 * f + k] for f in range(nf) for k in (1, 2, 3)]
    A = np.array([r.split()[1:9] for r in rows], np.float64)
    UV = np.stack([A[:, 6], 1.0 - A[:, 7]], 1)
    return A[:, 0:3], A[:, 3:6], UV, [m.strip() for m in mats]


def frame_mesh(key):
    d = os.path.join(OUT, 'models', 'ifr', 'frames', key)
    Ps, Ns, UVs, M = [], [], [], []
    for g in ('legs', 'upper'):
        p = os.path.join(d, '%s_%s.smd' % (key, g))
        if not os.path.exists(p): continue
        P, N, UV, mats = read_smd(p); Ps.append(P); Ns.append(N); UVs.append(UV); M += mats
    if not Ps: return None
    P = np.vstack(Ps); return P, np.arange(len(P)).reshape(-1, 3), np.vstack(UVs), np.vstack(Ns), M


def backup(key):
    """keeps the frame's plain (converter-made) vmats and their pngs in <work>/mat_orig/<key>/: a vmat that is not upgraded is a fresh
    conversion and replaces the backup copy; an upgraded one keeps the backup (the originals stay the input, so re-runs are idempotent)"""
    src = os.path.join(OUT, 'materials', 'ifr', 'frames', key); dst = os.path.join(BACK, key); os.makedirs(dst, exist_ok=True)
    n = 0
    for v in glob.glob(os.path.join(src, '*.vmat')):
        if re.search(r'_(scorched|wrecked)\.vmat$', v): continue        # damage skins are re-derived from the base vmat
        b = os.path.join(dst, os.path.basename(v)); txt = open(v, encoding='utf-8').read()
        fresh = not HS.is_upgraded(txt)
        if fresh or not os.path.exists(b):
            if not fresh and not os.path.exists(b): log('  ! %s upgraded but no backup: skipped' % os.path.basename(v)); continue
            shutil.copy2(v, b); n += 1
            for rel in re.findall(r'"(materials/[^"]+\.png)"', txt):
                f = os.path.join(OUT, rel.replace('/', os.sep))
                if os.path.exists(f): shutil.copy2(f, os.path.join(dst, os.path.basename(rel))); n += 1
    return n


def restore(key):
    src = os.path.join(BACK, key); dst = os.path.join(OUT, 'materials', 'ifr', 'frames', key)
    if not os.path.isdir(src): return 0
    for f in glob.glob(os.path.join(src, '*')): shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
    for f in glob.glob(os.path.join(dst, '*_ao.png')) + glob.glob(os.path.join(dst, '*_tint.png')) + glob.glob(os.path.join(dst, '*_nrmd.png')):
        if not os.path.exists(os.path.join(src, os.path.basename(f))): os.remove(f)
    return len(os.listdir(src))


def vmt_index(key):
    st = json.load(open(os.path.join(WORK, 'state.json'), encoding='utf-8')).get('frames', {}).get(key, {})
    roots = [os.path.join(WORK, 'extract', str(x)) for x in {st.get('source_item'), CAT['frames'].get(key, {}).get('item')} if x]
    roots = [r for r in roots if os.path.isdir(r)] + ([BASEGAME] if os.path.isdir(BASEGAME) else [])
    idx = {}
    for r in roots:
        for p in glob.glob(os.path.join(r, 'materials', '**', '*.vmt'), recursive=True):
            idx.setdefault(os.path.basename(p)[:-4].lower(), (p, r))
    return idx, roots


def source_gloss(vmt, roots, shape):
    try: shader, prm = vtf.load_vmt(vmt, roots)
    except Exception: return None, 'vmt unreadable'
    def tex(k):
        v = prm.get(k)
        if not v: return None
        v = re.sub(r'\.vtf$', '', v.strip('"').replace(chr(92), '/'), flags=re.I)
        p = vtf.find_file('materials/%s.vtf' % v, roots)
        try: return vtf.load_vtf(p) if p else None
        except Exception: return None
    return HS.gloss_from_vmt(prm, tex, shape)


def png_of(txt, key, back):
    m = re.search(r'^\s*%s\s+"([^"]+)"' % key, txt, re.M)
    if not m or not m.group(1).endswith('.png'): return None
    p = os.path.join(back, os.path.basename(m.group(1)))
    return p if os.path.exists(p) else None


def upgrade_frame(key, cap, opts=None):
    t0 = time.time()
    src = os.path.join(OUT, 'materials', 'ifr', 'frames', key); back = os.path.join(BACK, key)
    nb = backup(key)
    mesh = frame_mesh(key)
    fm = np.array(mesh[4]) if mesh else None
    idx, roots = vmt_index(key)
    items, rel = [], 'materials/ifr/frames/%s' % key
    for bv in sorted(glob.glob(os.path.join(back, '*.vmat'))):
        name = os.path.basename(bv)
        if re.search(r'_(scorched|wrecked)\.vmat$', name) or not os.path.exists(os.path.join(src, name)): continue
        txt = open(bv, encoding='utf-8').read(); stem = name[:-5]
        cp = png_of(txt, 'TextureColor', back)
        if not cp: continue
        open(os.path.join(src, name), 'w', newline='\n').write(txt)            # start from the plain vmat
        col = np.asarray(Image.open(cp).convert('RGB'))
        npth = png_of(txt, 'TextureNormal', back)
        ip = png_of(txt, 'TextureSelfIllumMask', back)
        m0 = re.match(r'// (\S+)', txt); src_tex = os.path.basename(m0.group(1)).lower() if m0 else stem
        gloss, ghow = (source_gloss(idx[src_tex][0], roots, col.shape[:2]) if src_tex in idx else (None, 'no vmt'))
        if gloss is None:
            rp = png_of(txt, 'TextureRoughness', back)
            if rp:
                r = np.asarray(Image.open(rp).convert('L').resize((col.shape[1], col.shape[0])), np.float32)
                if r.std() > 3: gloss = np.clip((235 - r) / 185.0, 0, 1); ghow = 'from converted roughness'
        items.append(dict(vmat='%s/%s' % (rel, name), col=col, nrm=np.asarray(Image.open(npth).convert('RGB')) if npth else None,
                          gloss=gloss, gloss_how=ghow, illum=np.asarray(Image.open(ip).convert('L'), np.float32) / 255.0 if ip else None,
                          faces=np.nonzero(fm == name)[0] if fm is not None else None, seed=key + '/' + stem))
    rep = HS.upgrade_set(OUT, items, mesh[:4] if mesh else None, opts, cap, log)
    for it in items:      # damage skins: colour variants from the new colour map, vmats re-derived from the new base vmat
        vs = it['vmat']; stem = os.path.basename(vs)[:-5]
        if os.path.exists(os.path.join(src, stem + '_scorched.vmat')):
            damage_tex.variants(os.path.join(src, stem + '_color.png'), force=True)
            damage_tex.material_variants(OUT, vs)
    log('%s: %d materials in %.0f s (%d files backed up)' % (key, len(rep), time.time() - t0, nb))
    return rep


def main():
    a = sys.argv[1:]
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    cap = int(a[a.index('--size-cap') + 1]) if '--size-cap' in a else 2048
    keys = sorted(os.listdir(os.path.join(OUT, 'materials', 'ifr', 'frames')))
    if only: keys = [k for k in keys if k in only]
    if '--restore' in a:
        for k in keys: log('%s: restored %d files' % (k, restore(k)))
        return 0
    rp = os.path.join(WORK, 'reports', 'materials.json')
    allrep = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
    for i, k in enumerate(keys):
        log('[%d/%d] %s' % (i + 1, len(keys), k))
        fr = CAT['frames'].get(k, {}); opts = dict(fr.get('mat_opts') or {})
        if fr.get('retint'): opts['retint'] = fr['retint']
        if fr.get('source') == 'tripo': opts['auto_glow'] = True           # colour-only maps: painted sensor lights become self-lit          # Tripo colour maps: pull toward the roster palette
        allrep[k] = upgrade_frame(k, cap, opts or None)
        json.dump(allrep, open(rp, 'w', encoding='utf-8'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
