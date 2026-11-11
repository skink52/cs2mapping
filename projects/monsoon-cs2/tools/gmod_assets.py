"""mg_monsoon: Garry's Mod Workshop models -> CS2 props under models/mv/ext/<name>/ (catalog: tools/gmod_assets.json).

usage (always with -I: the downloads are untrusted data and nothing in them is ever run or imported):
  python -I tools/gmod_assets.py fetch   [--only id,id]        SteamCMD (anonymous) -> out/gmod/<id>/<id>.gma -> out/gmod/<id>/x/ (models/, materials/)
  python -I tools/gmod_assets.py list    <id> [--grep rx] [--stats]   every .mdl of an extracted item (--stats: triangles, size, body parts, skins, bones)
  python -I tools/gmod_assets.py convert [--only name,name] [--force] catalog items -> out/addon/models/mv/ext/<name>/ (+ materials/models/mv/ext/<name>/)
  python -I tools/gmod_assets.py view    [--only name,name]             out/gmod/view/<name>.png: the written model from 4 sides (front-left, rear-right, side, top)
  python -I tools/gmod_assets.py report                         out/gmod_models.json from the per-model reports
  python -I tools/gmod_assets.py prune   [--gma]                delete extracted files no catalog item uses (--gma: the archives too)

Catalog (tools/gmod_assets.json): {"addons": [{id, title, author, license_note, rip, status, roots: [other ids whose materials it needs],
  items: [{name, mdl (path inside the addon; several sharing a skeleton joined by commas), role (the procedural prop it replaces, or "new"),
           length | height | scale, yaw (deg | auto | long), origin (feet | center | keep), skin, bodygroups {part: i}, only_parts, drop_parts,
           only_bones, drop_bones, drop_materials, origin_xy_bone (bone regex: origin moved under it, e.g. the rotor mast), split "a=<bone rx>;b=<rx>;upper=.*" (one model per bone group: <name>_<a> ...),
           pivot {group: "<bone regex>" | [x, y, z]} (moves that group's origin onto the bone, e.g. a rotor hub, and records where it sat),
           parts [{mdl, pos [x, y, z]}] (more MDLs of the same object welded on at the offsets the addon's lua gives), ground true (origin kept
           in x/y, lowest point dropped onto z 0), attach {model: [x, y, z]} (where a separate moving part goes, in this model's space),
           matsub_of <name> (a variant of another item: its vmats and PNGs are shared, not written twice),
           hulls N (N convex hulls, slabs along the longest side, instead of one), dynamic true (a prop the script moves), surface, maxtex,
           plain_mat (default true: source colour/normal/gloss kept; false runs create/hardsurface_mat.py), extra [raw mdl2cs2 arguments]}]}]}

The conversion itself is create/mdl2cs2.py (bind pose, csgo_complex vmats, one convex hull, LOD1-4 from lod_decimate.py, 4-view preview,
JSON report). This script adds the download/extract step, the pivot move, the multi-hull physics and the summary the map build reads:
out/gmod_models.json {name: {model, bounds, tris, replaces, credit, ...}}. Units: 40 per metre (DESIGN.md); +X is the nose/muzzle/front.
"""
import glob, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PROJ))
CREATE = os.path.join(REPO, 'create')
sys.path.insert(0, CREATE); sys.path.insert(0, os.path.join(CREATE, 'playermodels'))
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CATALOG = os.path.join(HERE, 'gmod_assets.json')
OUT = os.path.join(PROJ, 'out')
GM = os.path.join(OUT, 'gmod')
ADDON = os.path.join(OUT, 'addon')
SUB = 'models/mv/ext'
MATSUB = 'materials/models/mv/ext'
STEAMCMD = os.environ.get('STEAMCMD', r'C:\steamcmd\steamcmd.exe')
DL = os.path.join(GM, '_steam')                    # SteamCMD's install dir for these downloads (own appworkshop acf, not the playermodels one)


def log(*a):
    print(*a, flush=True)


def catalog():
    return json.load(open(CATALOG, encoding='utf-8'))


def xdir(wid):
    return os.path.join(GM, str(wid), 'x')


# ---------------------------------------------------------------- download + extract
def download(wid):
    d = os.path.join(GM, str(wid)); os.makedirs(d, exist_ok=True)
    have = [f for f in os.listdir(d) if f.endswith(('.gma', '.bin'))]
    if have: return os.path.join(d, have[0])
    src = os.path.join(DL, 'steamapps', 'workshop', 'content', '4000', str(wid))
    acf = os.path.join(DL, 'steamapps', 'workshop', 'appworkshop_4000.acf')
    for attempt in range(3):
        if os.path.exists(acf): os.remove(acf)     # else SteamCMD thinks a moved item is still installed and deletes the new copy on exit
        t = time.time()
        r = subprocess.run([STEAMCMD, '+force_install_dir', DL, '+login', 'anonymous', '+workshop_download_item', '4000', str(wid), '+quit'],
                           capture_output=True, text=True, errors='replace', timeout=3600)
        res = [l for l in r.stdout.splitlines() if 'Success' in l or 'ERROR' in l or 'Failed' in l]
        log('  %s: %s (%.0f s)' % (wid, res[-1].strip()[:160] if res else 'no result line', time.time() - t))
        arch = [f for f in glob.glob(os.path.join(src, '*')) if f.endswith(('.gma', '.bin'))] if os.path.isdir(src) else []
        if arch:
            dst = os.path.join(d, '%s%s' % (wid, os.path.splitext(arch[0])[1]))
            shutil.move(arch[0], dst); shutil.rmtree(src, ignore_errors=True)
            return dst
        time.sleep(5)
    return None


def extract(wid, arch):
    import gma
    out = xdir(wid)
    if os.path.isdir(out): return out
    info, files = gma.extract(arch, out, only=('models/', 'materials/'))
    log('  %s: %d files from "%s"' % (wid, len(files), info.get('name', '')[:60]))
    return out


def cmd_fetch(only):
    for ad in catalog()['addons']:
        wid = str(ad['id'])
        if only and wid not in only: continue
        if ad.get('status') == 'candidate' and not only: continue          # listed for the record, not downloaded
        if os.path.isdir(xdir(wid)): log('  %s: extracted already' % wid); continue
        arch = download(wid)
        if not arch: log('  %s: DOWNLOAD FAILED' % wid); continue
        try: extract(wid, arch)
        except Exception as ex: log('  %s: EXTRACT FAILED %s' % (wid, ex))
    log('fetch done; out/gmod is %.0f MB' % (du(GM) / 1e6))


def du(path):
    n = 0
    for r, _, fs in os.walk(path):
        for f in fs:
            try: n += os.path.getsize(os.path.join(r, f))
            except OSError: pass
    return n


# ---------------------------------------------------------------- listing
def cmd_list(wid, grep, stats, bones=False):
    root = xdir(wid)
    mdls = sorted(glob.glob(os.path.join(root, 'models', '**', '*.mdl'), recursive=True))
    pat = re.compile(grep, re.I) if grep else None
    if stats:
        from srcmdl import SrcModel
        import numpy as np
    for m in mdls:
        rel = os.path.relpath(m, root).replace('\\', '/')
        if pat and not pat.search(rel): continue
        if not stats: log(rel); continue
        try:
            s = SrcModel(m)
            meshes = [me for me in s.default_meshes() if len(me['tris'])]
            idx = np.unique(np.concatenate([np.asarray(me['tris']).ravel() for me in meshes])) if meshes else np.zeros(0, int)
            tris = sum(len(me['tris']) for me in meshes)
            ext = (s.V[idx].max(0) - s.V[idx].min(0)).round(0).tolist() if len(idx) else '?'
            pd = '; '.join('%s[%s]' % (p['name'], ','.join(str(sum(len(x['tris']) for x in mo['meshes'])) for mo in p['models'])) for p in s.parts)
            log('%-62s %6d tris  size %s  bones %d  skins %d  parts %s' % (rel, tris, ext, len(s.bones), len(s.skins), pd))
            if bones: log('      bones: ' + ', '.join(b['name'] for b in s.bones)[:1500])
        except Exception as ex:
            log('%-70s  unreadable: %s' % (rel, str(ex)[:80]))


# ---------------------------------------------------------------- SMD helpers (the pivot move and the hull slabs)
def smd_shift(path, d):
    """model-space shift d subtracted from every vertex of an SMD written by mdl2cs2 / lod_decimate (positions stored as (y, -x, z))"""
    sx, sy, sz = d[1], -d[0], d[2]
    out, intri = [], False
    for line in open(path).read().split('\n'):
        if line == 'triangles': intri = True
        elif intri:
            p = line.split()
            if len(p) >= 9 and p[0].lstrip('-').isdigit():
                p[1] = '%.4f' % (float(p[1]) - sx); p[2] = '%.4f' % (float(p[2]) - sy); p[3] = '%.4f' % (float(p[3]) - sz)
                line = ' '.join(p)
        out.append(line)
    open(path, 'w', newline='\n').write('\n'.join(out))


def smd_points(path):
    import numpy as np
    pts, intri = [], False
    for line in open(path):
        if line.strip() == 'triangles': intri = True
        elif intri:
            p = line.split()
            if len(p) >= 9: pts.append((-float(p[2]), float(p[1]), float(p[3])))       # back to model space
    return np.array(pts)


def write_hulls(vdir, mname, n):
    """n convex hulls: slabs along the model's longest horizontal side (a fuselage, a truck, a hut row), each the hull of its slab"""
    import numpy as np, modelio
    P = smd_points(os.path.join(vdir, mname + '.smd'))
    if len(P) < 16: return 1
    ax = int(np.argmax((P.max(0) - P.min(0))[:2]))
    edges = np.linspace(P[:, ax].min(), P[:, ax].max(), n + 1)
    sets = []
    for i in range(n):
        m = (P[:, ax] >= edges[i] - 1.0) & (P[:, ax] <= edges[i + 1] + 1.0)
        pts = np.unique(P[m].round(2), axis=0)
        if len(pts) < 8: continue
        if len(pts) > 3000: pts = pts[np.random.RandomState(i).choice(len(pts), 3000, replace=False)]
        if (pts.max(0) - pts.min(0)).min() < 0.5: continue
        sets.append(pts)
    if len(sets) < 2: return 1
    modelio.write_hull_smd(os.path.join(vdir, mname + '_hull.smd'), sets)
    return len(sets)


def smd_tris(path):
    """the triangle lines of an SMD (between 'triangles' and the last 'end')"""
    L = open(path).read().split('\n')
    i = L.index('triangles') + 1
    j = max(k for k, l in enumerate(L) if l.strip() == 'end')
    return L[:i], [l for l in L[i:j] if l.strip()]


def vmdl_remaps(path):
    return re.findall(r'from = "([^"]+)"\s*to = "([^"]+)"', open(path).read())


def merge_parts(ad, it, vdir, rep, roots):
    """item 'parts': other MDLs of the same object that the game assembles in lua (a gun carriage, its wheels, its traverse ring), each
    converted on its own and its triangles appended at pos (the lua's Vector, source units; scaled here) -> one model, hull and LODs redone"""
    import numpy as np, modelio, mdl2cs2
    name = it['name']; sub = '%s/%s' % (SUB, name); sc = float(it.get('scale', 1.0))
    head, tris = smd_tris(os.path.join(vdir, name + '.smd'))
    remaps = dict(vmdl_remaps(os.path.join(vdir, name + '.vmdl')))
    for k, part in enumerate(it['parts']):
        tmp = '%s__p%d' % (name, k)
        pit = dict(it, name=tmp, mdl=part['mdl'], origin='keep', matsub_of=it.get('matsub_of', name)); pit.pop('parts', None)
        for key in ('bodygroups', 'skin', 'drop_bones', 'only_bones'):
            if key in part: pit[key] = part[key]
        mdls = [os.path.join(xdir(ad['id']), *m.split('/')) for m in part['mdl'].split(',')]
        cmd = item_cmd(ad, pit, mdls, roots, os.path.join(GM, 'preview', tmp + '.png'), os.path.join(GM, 'reports', tmp + '.json')) + ['--no-lods']
        i = cmd.index('--sub'); cmd[i + 1] = sub
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
        if r.returncode != 0: raise RuntimeError('part %s: %s' % (part['mdl'], (r.stdout + r.stderr)[-300:]))
        f = os.path.join(vdir, tmp + '.smd')
        smd_shift(f, -np.array(part.get('pos', [0, 0, 0]), float) * sc)
        tris += smd_tris(f)[1]
        remaps.update(dict(vmdl_remaps(os.path.join(vdir, tmp + '.vmdl'))))
        for g in glob.glob(os.path.join(vdir, tmp + '*')) + [os.path.join(GM, 'preview', tmp + '.png'), os.path.join(GM, 'reports', tmp + '.json')]:
            if os.path.exists(g): os.remove(g)
    open(os.path.join(vdir, name + '.smd'), 'w', newline='\n').write('\n'.join(head + tris + ['end']) + '\n')
    P = smd_points(os.path.join(vdir, name + '.smd'))
    U = np.unique(P.round(2), axis=0)
    modelio.write_hull_smd(os.path.join(vdir, name + '_hull.smd'), [mdl2cs2.hull_points(U)])
    for g in glob.glob(os.path.join(vdir, name + '_lod*d.smd')): os.remove(g)
    txt = modelio.vmdl_text(name, sub, [name], sorted(remaps.items()), [name + '_hull'], surface=it.get('surface', 'metal'),
                            entity='prop_dynamic' if it.get('dynamic') else 'prop_static', archetype='' if it.get('dynamic') else 'static_prop_model')
    open(os.path.join(vdir, name + '.vmdl'), 'w', newline='\n').write(txt)
    counts, notes = mdl2cs2.make_lods(ADDON, sub, name, float((P.max(0) - P.min(0)).max()))
    e = rep['models']['model']
    e.update(bounds=[P.min(0).round(1).tolist(), P.max(0).round(1).tolist()], tris=counts, lod_notes=notes)
    log('    merged %d parts: %d tris %s  bounds %s .. %s' % (len(it['parts']), counts[0], counts[1:], e['bounds'][0], e['bounds'][1]))


def ground(it, vdir, rep):
    """item 'ground': the origin stays where the source has it in x/y (the pivot the addon's lua uses) and the lowest point goes to z 0;
    the lift is recorded so parts placed by lua offsets can follow"""
    import numpy as np
    name = it['name']; e = rep['models']['model']
    dz = float(e['bounds'][0][2])
    for f in glob.glob(os.path.join(vdir, name + '.smd')) + glob.glob(os.path.join(vdir, name + '_lod*d.smd')) + glob.glob(os.path.join(vdir, name + '_hull.smd')):
        smd_shift(f, (0, 0, dz))
    e['bounds'][0][2] = 0.0; e['bounds'][1][2] = round(e['bounds'][1][2] - dz, 1)
    e['origin_was_at_z'] = round(-dz, 2)
    log('    ground: lifted %.1f (the source origin is now at z %.1f)' % (-dz, -dz))


# ---------------------------------------------------------------- convert
def item_cmd(ad, it, mdls, roots, preview, report):
    name = it['name']
    cmd = [sys.executable, '-X', 'utf8', '-I', os.path.join(CREATE, 'mdl2cs2.py'), ','.join(mdls), ADDON, name,
           '--sub', '%s/%s' % (SUB, name), '--matsub', '%s/%s' % (MATSUB, it.get('matsub_of', name)),
           '--origin', it.get('origin', 'feet'), '--yaw', str(it.get('yaw', 0)), '--surface', it.get('surface', 'metal'),
           '--maxtex', str(it.get('maxtex', 2048)), '--report', report, '--preview', preview,
           '--credit', '%s by %s (GMod Workshop %s)' % (ad['title'], ad['author'], ad['id'])]
    for k in ('length', 'height', 'scale'):
        if it.get(k): cmd += ['--' + k, str(it[k])]; break
    if it.get('skin'): cmd += ['--skin', str(it['skin'])]
    for k, v in (it.get('bodygroups') or {}).items(): cmd += ['--bodygroup', '%s=%d' % (k, v)]
    for k in ('only_parts', 'drop_parts', 'only_bones', 'drop_bones', 'drop_materials', 'split'):
        if it.get(k): cmd += ['--' + k.replace('_', '-'), it[k]]
    if it.get('dynamic'): cmd.append('--dynamic')
    if it.get('plain_mat', True): cmd.append('--plain-mat')
    if roots: cmd += ['--roots', ';'.join(roots)]
    return cmd + list(it.get('extra', []))


def convert_item(ad, it, force):
    import numpy as np
    name = it['name']
    report = os.path.join(GM, 'reports', name + '.json'); preview = os.path.join(GM, 'preview', name + '.png')
    vdir = os.path.join(ADDON, SUB, name)
    if os.path.exists(report) and os.path.isdir(vdir) and not force:
        log('  %s: converted already (--force to redo)' % name); return True
    root = xdir(ad['id'])
    mdls = [os.path.join(root, *m.split('/')) for m in it['mdl'].split(',')]
    miss = [m for m in mdls if not os.path.exists(m)]
    if miss: log('  %s: MISSING %s' % (name, miss[0])); return False
    for d in (vdir,) + (() if it.get('matsub_of') else (os.path.join(ADDON, MATSUB, name),)): shutil.rmtree(d, ignore_errors=True)
    roots = [xdir(r) for r in ad.get('roots', []) if os.path.isdir(xdir(r))]
    t = time.time()
    r = subprocess.run(item_cmd(ad, it, mdls, roots, preview, report) + (['--no-lods'] if it.get('parts') else []), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
    tail = '\n'.join((r.stdout + r.stderr).strip().splitlines()[-12:])
    log('  %s: mdl2cs2 rc %d in %.0f s\n    %s' % (name, r.returncode, time.time() - t, tail.replace('\n', '\n    ')))
    if r.returncode != 0 or not os.path.exists(report): return False
    rep = json.load(open(report, encoding='utf-8'))
    skel_path = os.path.join(vdir, name + '_skeleton.json')
    skel = json.load(open(skel_path, encoding='utf-8')) if os.path.exists(skel_path) else {'bones': []}
    post = {}
    if it.get('parts'): merge_parts(ad, it, vdir, rep, roots)
    if it.get('ground'): ground(it, vdir, rep)
    # origin_xy_bone: the whole model's origin moved under a bone (the rotor mast), z stays on the ground
    if it.get('origin_xy_bone'):
        hit = [b for b in skel['bones'] if re.search(it['origin_xy_bone'], b['name'], re.I)]
        if hit:
            o = np.array([hit[0]['pos'][0], hit[0]['pos'][1], 0.0])
            for f in glob.glob(os.path.join(vdir, '*.smd')): smd_shift(f, o)
            for e in rep['models'].values():
                e['bounds'] = [(np.array(e['bounds'][0]) - o).round(1).tolist(), (np.array(e['bounds'][1]) - o).round(1).tolist()]
            for b in skel['bones']:
                b['pos'] = (np.array(b['pos']) - o).round(2).tolist()
                if b.get('centroid'): b['centroid'] = (np.array(b['centroid']) - o).round(1).tolist()
            json.dump(skel, open(skel_path, 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
            rep['bounds'] = [(np.array(rep['bounds'][0]) - o).round(1).tolist(), (np.array(rep['bounds'][1]) - o).round(1).tolist()]
            log('    origin under bone %s: moved by %s' % (hit[0]['name'], o.round(1).tolist()))
        else: log('    origin_xy_bone: no bone matches')
    # pivots: a group's origin moved onto a bone (rotor hub, trunnion) so the script can spin / elevate it about its own origin
    for g, spec in (it.get('pivot') or {}).items():
        key = g or 'model'
        if key not in rep['models']: log('    pivot: no group %s' % g); continue
        if isinstance(spec, str):
            hit = [b for b in skel['bones'] if re.search(spec, b['name'], re.I)]
            if not hit: log('    pivot %s: no bone matches %s' % (g, spec)); continue
            b = hit[0]
            # bone joints of static rigs often sit at the model origin: fall back on the centroid of what the bone owns
            p = np.array(b['pos'], float)
            if b.get('centroid') and np.abs(p).max() < 1e-3: p = np.array(b['centroid'], float)
            how = 'bone %s' % b['name']
        else:
            p = np.array(spec, float); how = 'given'
        mname = name + ('_' + g if g else '')
        for f in glob.glob(os.path.join(vdir, mname + '.smd')) + glob.glob(os.path.join(vdir, mname + '_lod*d.smd')) + glob.glob(os.path.join(vdir, mname + '_hull.smd')):
            smd_shift(f, p)
        e = rep['models'][key]
        e['bounds'] = [(np.array(e['bounds'][0]) - p).round(1).tolist(), (np.array(e['bounds'][1]) - p).round(1).tolist()]
        e['pivot'] = p.round(2).tolist(); e['pivot_how'] = how
        post[key] = p
        log('    pivot %s -> %s (%s)' % (mname, e['pivot'], how))
    # several convex hulls for long bodies
    n = int(it.get('hulls', 1))
    hull_groups = it.get('hull_groups', ['upper', 'model', 'body'])
    if n > 1:
        for key, e in rep['models'].items():
            if key not in hull_groups: continue
            mname = name + ('' if key == 'model' else '_' + key)
            try: e['hulls'] = write_hulls(vdir, mname, n)
            except Exception as ex: log('    hulls %s failed: %s' % (mname, ex))
    rep['item'] = {k: it[k] for k in it}
    rep['addon'] = {k: ad.get(k) for k in ('id', 'title', 'author', 'license_note', 'rip')}
    json.dump(rep, open(report, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    return True


def cmd_convert(only, force):
    ok, bad = [], []
    for ad in catalog()['addons']:
        for it in ad.get('items', []):
            if only and it['name'] not in only: continue
            if it.get('rejected') and not only: continue
            if not os.path.isdir(xdir(ad['id'])): log('  %s: addon %s not fetched' % (it['name'], ad['id'])); bad.append(it['name']); continue
            try: good = convert_item(ad, it, force)
            except Exception as ex: log('  %s: FAILED %s' % (it['name'], ex)); good = False
            (ok if good else bad).append(it['name'])
    log('converted %d, failed %d %s' % (len(ok), len(bad), bad or ''))
    cmd_report()


def cmd_report():
    out = {}
    for ad in catalog()['addons']:
        for it in ad.get('items', []):
            if it.get('rejected'): continue
            rp = os.path.join(GM, 'reports', it['name'] + '.json')
            if not os.path.exists(rp): continue
            rep = json.load(open(rp, encoding='utf-8'))
            for key, e in rep['models'].items():
                mname = it['name'] + ('' if key == 'model' else '_' + key)
                if not os.path.exists(os.path.join(ADDON, *e['vmdl'].split('/'))): continue
                role = it.get('role', 'new')
                if isinstance(role, dict): role = role.get(key, 'new')
                d = {'model': e['vmdl'], 'bounds': e['bounds'], 'tris': e['tris'], 'replaces': role,
                     'credit': '%s by %s (GMod Workshop %s)' % (ad['title'], ad['author'], ad['id']),
                     'workshop_id': str(ad['id']), 'rip': ad.get('rip', ''), 'scale': rep.get('scale'), 'yaw': rep.get('yaw'),
                     'dynamic': bool(it.get('dynamic')), 'hulls': e.get('hulls', 1), 'front': '+X', 'note': it.get('note', '')}
                if 'origin_was_at_z' in e: d['source_origin_z'] = e['origin_was_at_z']   # height of the addon's own origin (lua offsets start there)
                if it.get('attach'): d['attach'] = it['attach']
                if 'pivot' in e: d['pivot'] = e['pivot']          # where this part's origin sits in the parent model's space
                out[mname] = d
    json.dump(out, open(os.path.join(OUT, 'gmod_models.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    log('out/gmod_models.json: %d models' % len(out))


# ---------------------------------------------------------------- look at the result (create/smd_view.py: the written SMDs + vmats, not the source)
def cmd_view(only):
    import numpy as np, smd_view
    from PIL import Image
    os.makedirs(os.path.join(GM, 'view'), exist_ok=True)
    for ad in catalog()['addons']:
        for it in ad.get('items', []):
            if only and it['name'] not in only: continue
            rp = os.path.join(GM, 'reports', it['name'] + '.json')
            if not os.path.exists(rp): continue
            rep = json.load(open(rp, encoding='utf-8'))
            sc = smd_view.Scene(ADDON); lo, hi = [], []
            todo = [(e, np.array(e.get('pivot', [0, 0, 0]), float)) for e in rep['models'].values()]
            for other, pos in (it.get('attach') or {}).items():          # the moving part shown where the catalog says it goes
                op = os.path.join(GM, 'reports', other + '.json')
                if os.path.exists(op): todo += [(e, np.array(pos, float)) for e in json.load(open(op, encoding='utf-8'))['models'].values()]
            for e, off in todo:
                try:                                   # mdl2cs2 names SMD materials "<x>.vmat"; smd_view's table drops the extension
                    txt = open(os.path.join(ADDON, *e['vmdl'].split('/'))).read()
                    mats = smd_view.load_vmdl_mats(txt); mats.update({k + '.vmat': v for k, v in list(mats.items())})
                    sc.tris += smd_view.load_smd(os.path.join(ADDON, smd_view.vmdl_smd(txt)), mats, tuple(off))
                except Exception as ex: log('  %s: %s' % (it['name'], ex)); continue
                lo.append(np.array(e['bounds'][0]) + off); hi.append(np.array(e['bounds'][1]) + off)
            if not lo: continue
            lo, hi = np.min(lo, 0), np.max(hi, 0); c = (lo + hi) / 2; r = float(np.linalg.norm(hi - lo)) / 2
            ims = []
            for az, el in ((35, 18), (-145, 30), (90, 4), (0, 80)):       # front-left 3/4, rear-right from above, side, top (+X = front)
                a, b = np.radians(az), np.radians(el)
                eye = c + 2.4 * r * np.array([np.cos(a) * np.cos(b), np.sin(a) * np.cos(b), np.sin(b)])
                ims.append(sc.render(eye=tuple(eye), at=tuple(c), size=(800, 520), fov=42, bg=(70, 78, 92)))
            W = Image.new('RGB', (1600, 1040))
            for i, im in enumerate(ims): W.paste(im.convert('RGB') if hasattr(im, 'convert') else Image.fromarray(np.asarray(im)[..., :3]), ((i % 2) * 800, (i // 2) * 520))
            W.save(os.path.join(GM, 'view', it['name'] + '.png'))
            log('  view/%s.png  bounds %s .. %s' % (it['name'], lo.round(0).tolist(), hi.round(0).tolist()))


# ---------------------------------------------------------------- prune
def cmd_prune(gma_too):
    """keeps the catalog items' .mdl/.vvd/.vtx/.phy files; everything else extracted goes (the converted textures live in out/addon)"""
    freed = 0
    cat = catalog()
    for d in sorted(glob.glob(os.path.join(GM, '*'))):
        wid = os.path.basename(d)
        if not wid.isdigit(): continue
        ad = next((a for a in cat['addons'] if str(a['id']) == wid), None)
        keep = set()
        for it in (ad or {}).get('items', []):
            for m in it['mdl'].split(','): keep.add(os.path.splitext(m.lower())[0])
        x = os.path.join(d, 'x')
        for r, _, fs in os.walk(x):
            for f in fs:
                p = os.path.join(r, f); rel = os.path.relpath(p, x).replace('\\', '/').lower()
                stem = re.sub(r'\.(dx80|dx90|sw)$', '', os.path.splitext(rel)[0])
                if stem in keep: continue
                freed += os.path.getsize(p); os.remove(p)
        if gma_too:
            for f in glob.glob(os.path.join(d, '*.gma')) + glob.glob(os.path.join(d, '*.bin')): freed += os.path.getsize(f); os.remove(f)
    shutil.rmtree(DL, ignore_errors=True)
    log('prune: %.0f MB freed; out/gmod is now %.0f MB' % (freed / 1e6, du(GM) / 1e6))


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return

    def opt(name):
        return a[a.index(name) + 1] if name in a else None
    only = set((opt('--only') or '').split(',')) - {''}
    if a[0] == 'fetch': cmd_fetch(only)
    elif a[0] == 'list': cmd_list(a[1], opt('--grep'), '--stats' in a or '--bones' in a, '--bones' in a)
    elif a[0] == 'convert': cmd_convert(only, '--force' in a)
    elif a[0] == 'report': cmd_report()
    elif a[0] == 'view': cmd_view(only)
    elif a[0] == 'prune': cmd_prune('--gma' in a)
    else: print(__doc__)


if __name__ == '__main__':
    main()
