"""Garry's Mod Workshop models -> CS2 props for any project: search, download, extract, convert, look at, report.
The project passes its own catalog (JSON); this file holds no project names or paths.
From projects/monsoon-cs2/tools/gmod_assets.py (12 Nov 2026), made project-neutral; `search` and `details` added.

usage (always with -I: the downloads are untrusted data and nothing in them is ever run or imported):
  python -I create/gmod_assets.py <catalog.json> search  <words,words> [--pages N] [--tag T]   Workshop text search -> <work>/search.json
  python -I create/gmod_assets.py <catalog.json> details [--only id,id]   GetPublishedFileDetails of every catalog id -> <work>/details.json
  python -I create/gmod_assets.py <catalog.json> fetch   [--only id,id]   SteamCMD (anonymous) -> <work>/<id>/<id>.gma -> <work>/<id>/x/
  python -I create/gmod_assets.py <catalog.json> list    <id> [--grep rx] [--stats | --bones]   every .mdl of an extracted item
  python -I create/gmod_assets.py <catalog.json> convert [--only name,name] [--force]   items -> <addon>/<model_sub>/<name>/
  python -I create/gmod_assets.py <catalog.json> view    [--only name,name]   <work>/view/<name>.png: the written model from 4 sides
  python -I create/gmod_assets.py <catalog.json> report                    <report>: {name: {model, bounds, tris, replaces, credit, ...}}
  python -I create/gmod_assets.py <catalog.json> prune   [--gma]           delete extracts of addons with no items, unused model files,
                                                                             rejected outputs (--gma: archives too)
  python -I create/gmod_assets.py <catalog.json> normals [--only name,name]   vertex normals turned to agree with the winding, LODs
                                                                             decimated again (convert does it too)
  common options: --work DIR  --addon DIR  --prefix P (model_sub = models/P/ext, mat_sub = materials/models/P/ext)  --report FILE

Catalog: {"config": {...}, "addons": [...]}
  config (paths relative to the catalog file; command-line options and the env GMOD_WORK win):
    work       downloads, extracts, previews, per-model reports and search results. Keep it OUTSIDE the repo (untrusted, large).
    addon      the staging content tree the converted models are written to (e.g. <project>/out/addon); never the live addon
    model_sub  e.g. "models/tw/ext"      mat_sub  e.g. "materials/models/tw/ext"      report  e.g. "../out/gmod_models.json"
  addons: [{id, title, author, license_note, rip, rip_risk (high|medium|low|unknown), quality, status, roots: [other ids whose materials
    it needs], items: [{name, mdl (path inside the addon; several sharing a skeleton joined by commas), role (the prop it would replace, or
    "new"), length | height | scale, yaw (deg | auto | long), origin (feet | center | keep), skin, bodygroups {part: i}, only_parts,
    drop_parts, only_bones, drop_bones, drop_materials, origin_xy_bone (bone regex: origin moved under it, e.g. a rotor mast),
    split "a=<bone rx>;b=<rx>;upper=.*" (one model per bone group: <name>_<a> ...), pivot {group: "<bone regex>" | [x, y, z]} (moves that
    group's origin onto the bone and records where it sat), parts [{mdl, pos [x, y, z]}] (more MDLs of the same object welded on at the
    offsets the addon's lua gives), ground true (origin kept in x/y, lowest point dropped onto z 0), attach {model: [x, y, z]} (where a
    separate moving part goes, in this model's space), matsub_of <name> (a variant of another item: its vmats and PNGs are shared),
    hulls N (N convex hulls, slabs along the longest side), dynamic true (prop_dynamic: model_archetype ""), surface, maxtex,
    plain_mat (default true: source colour/normal/gloss kept; false runs create/hardsurface_mat.py), rejected (reason),
    extra [raw mdl2cs2 arguments]}]}]
  status: candidate (Workshop page only, never downloaded unless named with --only) | fetched ... | converted ...

The conversion itself is create/mdl2cs2.py (bind pose, csgo_complex vmats, one convex hull, LOD1-4 from lod_decimate.py, 4-view preview,
JSON report). This script adds search, the download/extract step, the pivot move, the multi-hull physics and the summary a map build
reads. Units: 40 per metre unless the item says otherwise; +X is the nose/muzzle/front.
"""
import glob, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = HERE
sys.path.insert(0, CREATE); sys.path.insert(0, os.path.join(CREATE, 'playermodels'))
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STEAMCMD = os.environ.get('STEAMCMD', r'C:\steamcmd\steamcmd.exe')
BS = chr(92)
C = {}          # resolved config: catalog, work, addon, sub, matsub, report


def log(*a):
    print(*a, flush=True)


def setup(catalog_path, opts):
    cp = os.path.abspath(catalog_path)
    cfg = json.load(open(cp, encoding='utf-8')).get('config', {})
    base = os.path.dirname(cp)
    rel = lambda p: p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    C['catalog'] = cp
    C['work'] = rel(opts.get('--work') or os.environ.get('GMOD_WORK') or cfg.get('work') or 'gmod_work')
    C['addon'] = rel(opts.get('--addon') or cfg.get('addon') or 'out/addon')
    pre = opts.get('--prefix')
    C['sub'] = ('models/%s/ext' % pre) if pre else cfg.get('model_sub', 'models/props/ext')
    C['matsub'] = ('materials/models/%s/ext' % pre) if pre else cfg.get('mat_sub', 'materials/' + C['sub'])
    C['report'] = rel(opts.get('--report') or cfg.get('report') or os.path.join(C['work'], 'gmod_models.json'))
    C['dl'] = os.path.join(C['work'], '_steam')     # SteamCMD's install dir for these downloads (own appworkshop acf)
    if any(w in os.path.normcase(C['addon']).replace('\\', '/') for w in ('csgo_addons', 'links/content_addons', 'links/game_addons')):
        sys.exit('gmod_assets: addon %s is a live addon folder; write to a staging tree and deploy from there' % C['addon'])


def catalog():
    return json.load(open(C['catalog'], encoding='utf-8'))


def xdir(wid):
    return os.path.join(C['work'], str(wid), 'x')


# ---------------------------------------------------------------- search (the Workshop browse pages, as create/playermodels/browse.py reads them)
SEARCH_URL = ('https://steamcommunity.com/workshop/browse/?appid=4000&browsesort={sort}&section=readytouseitems&p={p}&num_per_page=30'
              '&searchtext={q}{tag}')


def unesc(s):
    """a value from the page's embedded JSON (a JS string literal holding JSON: one extra level of escaping)"""
    s = s.replace(BS + BS, BS)
    try: return ' '.join(json.loads('"' + s + '"').split())
    except ValueError: return ' '.join(s.split())


def page_items(text):
    text = text.replace(BS + '"', '"')
    names = dict(re.findall(r'"steamid":"(\d+)".{0,300}?"persona_name":"(.*?)"', text, re.S))
    for blk in text.split('{"publishedfileid":"')[1:]:
        def g(k, d=''):
            m = re.search(r'"%s":"?(.*?)"?[,}]' % k, blk, re.S)
            return m[1] if m else d
        creator = g('creator')
        yield {'id': int(blk[:blk.index('"')]), 'title': unesc(g('title')), 'author': unesc(names.get(creator, creator)),
               'mb': round(int(g('file_size', '0') or 0) / 1e6, 1), 'subscribers': int(g('subscriptions', '0') or 0),
               'description': unesc(g('short_description'))[:300]}


def cmd_search(words, pages, tag):
    have = {int(a['id']) for a in catalog()['addons']}
    found = {}
    tq = '&requiredtags%%5B%%5D=%s' % urllib.parse.quote(tag) if tag else ''
    for w in [w.strip() for w in words.split(',') if w.strip()]:
        n0 = len(found)
        for sort in ('textsearch', 'totaluniquesubscribers'):
            for p in range(1, pages + 1):
                url = SEARCH_URL.format(sort=sort, p=p, q=urllib.parse.quote_plus(w), tag=tq)
                try: text = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read().decode('utf-8', 'replace')
                except OSError as x: log('  %s p%d: %s' % (w, p, x)); continue
                got = list(page_items(text))
                for it in got:
                    e = found.setdefault(it['id'], dict(it, queries=[]))
                    if w not in e['queries']: e['queries'].append(w)
                time.sleep(0.5)
                if len(got) < 30: break
        log('  %-28s %d new items' % (w, len(found) - n0))
    path = os.path.join(C['work'], 'search.json')
    os.makedirs(C['work'], exist_ok=True)
    old = {it['id']: it for it in json.load(open(path, encoding='utf-8'))} if os.path.exists(path) else {}
    for k, v in found.items():
        if k in old: v['queries'] = sorted(set(old[k].get('queries', [])) | set(v['queries']))
        old[k] = v
    json.dump(sorted(old.values(), key=lambda e: -e['subscribers']), open(path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for it in sorted(found.values(), key=lambda e: -e['subscribers']):
        if it['mb'] <= 0: continue                    # 0 MB = dupes / saves (contraptions of stock parts), no models
        log('%11d %s %7.1f MB %7d subs  %-70s (%s)' % (it['id'], '*' if it['id'] in have else ' ', it['mb'], it['subscribers'], it['title'][:70], it['author'][:24]))
    log('%d items (0 MB dupes not shown; * = in the catalog); all in %s' % (len(found), path))


def cmd_details(only):
    """title, size, tags, update time and the description (author's statements about sources and permissions) of each catalog id"""
    ids = [str(a['id']) for a in catalog()['addons'] if not only or str(a['id']) in only]
    out = {}
    for k in range(0, len(ids), 100):
        chunk = ids[k:k + 100]
        data = {'itemcount': len(chunk)}
        for i, x in enumerate(chunk): data['publishedfileids[%d]' % i] = x
        req = urllib.request.Request('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/',
                                     data=urllib.parse.urlencode(data).encode(), headers={'User-Agent': 'Mozilla/5.0'})
        try: res = json.load(urllib.request.urlopen(req, timeout=30))
        except OSError as x: log('  details: %s' % x); continue
        for d in res.get('response', {}).get('publishedfiledetails', []):
            out[d['publishedfileid']] = {'title': d.get('title', ''), 'mb': round(int(d.get('file_size', 0) or 0) / 1e6, 1),
                                         'tags': [t.get('tag') for t in d.get('tags', [])], 'creator': d.get('creator'),
                                         'updated': time.strftime('%Y-%m-%d', time.gmtime(int(d.get('time_updated', 0) or 0))),
                                         'subscriptions': d.get('lifetime_subscriptions', d.get('subscriptions')),
                                         'description': d.get('description', '')}
    os.makedirs(C['work'], exist_ok=True)
    path = os.path.join(C['work'], 'details.json')
    old = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    old.update(out)
    json.dump(old, open(path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    rx = re.compile(r'(?i)(rip|ripped|port(ed)?|from|credit|original|made by|permission|battlefield|bf1|verdun|tannenberg|isonzo|day of infamy|'
                    r'call of duty|red orchestra|rising storm|arma|world of tanks|war thunder|il-2|rise of flight|insurgency|dod|day of defeat|'
                    r'heroes|company of heroes|men of war|sketchfab|licen[cs]e|cc[- ]by|turbosquid|cgtrader)')
    for k, d in out.items():
        hits = sorted({m.group(0).lower() for m in rx.finditer(d['description'])})
        log('%11s %7.1f MB  %s  %-60s  source words: %s' % (k, d['mb'], d['updated'], d['title'][:60], ', '.join(hits)[:120]))
    log('%d items; descriptions in %s' % (len(out), path))


# ---------------------------------------------------------------- download + extract
def download(wid):
    d = os.path.join(C['work'], str(wid)); os.makedirs(d, exist_ok=True)
    have = [f for f in os.listdir(d) if f.endswith(('.gma', '.bin'))]
    if have: return os.path.join(d, have[0])
    src = os.path.join(C['dl'], 'steamapps', 'workshop', 'content', '4000', str(wid))
    acf = os.path.join(C['dl'], 'steamapps', 'workshop', 'appworkshop_4000.acf')
    for attempt in range(3):
        if os.path.exists(acf): os.remove(acf)     # else SteamCMD thinks a moved item is still installed and deletes the new copy on exit
        t = time.time()
        r = subprocess.run([STEAMCMD, '+force_install_dir', C['dl'], '+login', 'anonymous', '+workshop_download_item', '4000', str(wid), '+quit'],
                           capture_output=True, text=True, errors='replace', timeout=3600)
        res = [l for l in r.stdout.splitlines() if 'Success' in l or 'ERROR' in l or 'Failed' in l]
        log('  %s: %s (%.0f s)' % (wid, res[-1].strip()[:160] if res else 'no result line', time.time() - t))
        arch = [f for f in glob.glob(os.path.join(src, '*')) if f.endswith(('.gma', '.bin'))] if os.path.isdir(src) else []
        if arch:
            dst = os.path.join(d, '%s%s' % (wid, os.path.splitext(arch[0])[1]))
            shutil.move(arch[0], dst); shutil.rmtree(src, ignore_errors=True)
            return dst
        if os.path.isdir(src) and os.path.isdir(os.path.join(src, 'models')):          # an unpacked legacy item: copy the folders
            for sub in ('models', 'materials'):
                if os.path.isdir(os.path.join(src, sub)): shutil.copytree(os.path.join(src, sub), os.path.join(d, 'x', sub), dirs_exist_ok=True)
            shutil.rmtree(src, ignore_errors=True)
            return os.path.join(d, 'x')
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
        if ad.get('status', '').startswith('candidate') and not only: continue    # listed for the record, not downloaded
        if os.path.isdir(xdir(wid)): log('  %s: extracted already' % wid); continue
        if not ad.get('items') and not only: continue                       # nothing converted from it: fetched only when named with --only
        arch = download(wid)
        if not arch: log('  %s: DOWNLOAD FAILED' % wid); continue
        try: extract(wid, arch)
        except Exception as ex: log('  %s: EXTRACT FAILED %s' % (wid, ex))
    log('fetch done; %s is %.0f MB' % (C['work'], du(C['work']) / 1e6))


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


def orient_normals(path):
    """make every triangle's vertex normals agree with its winding (the side CS2 draws; it culls the other). Found on mg_monsoon's Mi-8
    (a GMod MDL whose triangles carried normals pointing INTO the hull for 63-80 % of them while the winding faced out): CS2 lit those
    faces from inside (dark), and lod_decimate, which keeps the normal-consistent faces, built LOD1-4 out of the rest, so panels went
    missing from LOD1 on ("see-through parts"). Per triangle: when the corners' mean normal points against the face normal it is flipped.
    The source smoothing mixed in- and outward faces, so a mesh that needed any flip gets its normals rebuilt from the geometry
    (area-weighted, faces more than CREASE degrees apart not smoothed together). A double-sided sheet keeps one normal per side.
    Returns (triangles, flipped); the file is rewritten only when something flipped."""
    import numpy as np
    head, rows = smd_tris(path)
    mats, V = [], []
    for k in range(0, len(rows) - 3, 4):
        mats.append(rows[k]); V.append([rows[k + 1 + j].split() for j in range(3)])
    P = np.array([[[float(x) for x in c[1:4]] for c in t] for t in V]); N = np.array([[[float(x) for x in c[4:7]] for c in t] for t in V])
    G = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    bad = (np.linalg.norm(G, axis=1) > 1e-12) & ((G * N.mean(1)).sum(1) < 0)
    flipped = int(bad.sum())
    if not flipped: return len(V), 0
    Ns = smooth_normals(P, G)
    out = []
    for t in range(len(V)):
        out.append(mats[t])
        for j, c in enumerate(V[t]):
            c[4:7] = ['%.4f' % x for x in Ns[t, j]]
            out.append(' '.join(c))
    open(path, 'w', newline='\n').write('\n'.join(head + out + ['end']) + '\n')
    return len(V), flipped


CREASE = 50.0


def smooth_normals(P, G):
    """corner normals from the geometry: P (n, 3 corners, 3), G (n, 3) unnormalised face normals by winding -> (n, 3, 3). A corner takes
    the area-weighted mean of the faces that share its position and lie within CREASE degrees of its own face."""
    import numpy as np
    n = len(P)
    Fn = G / np.maximum(np.linalg.norm(G, axis=1, keepdims=True), 1e-12)
    key = np.round(P.reshape(-1, 3) / 0.01).astype(np.int64)
    _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.ravel()
    order = np.argsort(vid, kind='stable'); starts = np.r_[0, np.nonzero(np.diff(vid[order]))[0] + 1, len(order)]
    out = np.repeat(Fn[:, None, :], 3, axis=1).reshape(-1, 3).copy()
    cosc = np.cos(np.radians(CREASE))
    for s, e in zip(starts[:-1], starts[1:]):
        if e - s < 2: continue
        corners = order[s:e]; faces = corners // 3
        fn = Fn[faces]; w = G[faces]                      # area-weighted (|G| = 2 x area)
        sim = fn @ fn.T >= cosc
        acc = sim.astype(float) @ w
        out[corners] = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    return out.reshape(n, 3, 3)


def fix_normals(name, rep, vdir):
    """orient_normals on every LOD0 mesh of a converted item; a mesh that changed gets its LOD1-4 decimated again (they were built from
    the bad normals). -> {mesh: (tris, flipped)}"""
    import mdl2cs2
    res = {}
    for key, e in rep['models'].items():
        mname = name + ('' if key == 'model' else '_' + key)
        f = os.path.join(vdir, mname + '.smd')
        if not os.path.exists(f): continue
        n, fl = orient_normals(f)
        res[mname] = (n, fl)
        if fl:
            for g in glob.glob(os.path.join(vdir, mname + '_lod*d.smd')): os.remove(g)
            P = smd_points(f)
            counts, notes = mdl2cs2.make_lods(C['addon'], '%s/%s' % (C['sub'], name), mname, float((P.max(0) - P.min(0)).max()))
            e['tris'] = counts; e['lod_notes'] = notes
            log('    normals %s: %d of %d triangles faced into the mesh, turned; LODs again %s' % (mname, fl, n, counts))
    return res


def cmd_normals(only):
    """orient_normals over converted items already in the addon tree (the conversion now does it itself)"""
    for ad in catalog()['addons']:
        for it in ad.get('items', []):
            if only and it['name'] not in only: continue
            rp = os.path.join(C['work'], 'reports', it['name'] + '.json'); vdir = os.path.join(C['addon'], C['sub'], it['name'])
            if not os.path.exists(rp) or not os.path.isdir(vdir): continue
            rep = json.load(open(rp, encoding='utf-8'))
            res = fix_normals(it['name'], rep, vdir)
            if any(fl for _, fl in res.values()):
                json.dump(rep, open(rp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
            else: log('  %s: normals agree with the winding' % it['name'])
    cmd_report()


def merge_parts(ad, it, vdir, rep, roots):
    """item 'parts': other MDLs of the same object that the game assembles in lua (a gun carriage, its wheels, its traverse ring), each
    converted on its own and its triangles appended at pos (the lua's Vector, source units; scaled here) -> one model, hull and LODs redone"""
    import numpy as np, modelio, mdl2cs2
    name = it['name']; sub = '%s/%s' % (C['sub'], name); sc = float(it.get('scale', 1.0))
    head, tris = smd_tris(os.path.join(vdir, name + '.smd'))
    remaps = dict(vmdl_remaps(os.path.join(vdir, name + '.vmdl')))
    for k, part in enumerate(it['parts']):
        tmp = '%s__p%d' % (name, k)
        pit = dict(it, name=tmp, mdl=part['mdl'], origin='keep', matsub_of=it.get('matsub_of', name)); pit.pop('parts', None)
        for key in ('bodygroups', 'skin', 'drop_bones', 'only_bones'):
            if key in part: pit[key] = part[key]
        mdls = [os.path.join(xdir(ad['id']), *m.split('/')) for m in part['mdl'].split(',')]
        cmd = item_cmd(ad, pit, mdls, roots, os.path.join(C['work'], 'preview', tmp + '.png'), os.path.join(C['work'], 'reports', tmp + '.json')) + ['--no-lods']
        i = cmd.index('--sub'); cmd[i + 1] = sub
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
        if r.returncode != 0: raise RuntimeError('part %s: %s' % (part['mdl'], (r.stdout + r.stderr)[-300:]))
        f = os.path.join(vdir, tmp + '.smd')
        smd_shift(f, -np.array(part.get('pos', [0, 0, 0]), float) * sc)
        tris += smd_tris(f)[1]
        remaps.update(dict(vmdl_remaps(os.path.join(vdir, tmp + '.vmdl'))))
        for g in glob.glob(os.path.join(vdir, tmp + '*')) + [os.path.join(C['work'], 'preview', tmp + '.png'), os.path.join(C['work'], 'reports', tmp + '.json')]:
            if os.path.exists(g): os.remove(g)
    open(os.path.join(vdir, name + '.smd'), 'w', newline='\n').write('\n'.join(head + tris + ['end']) + '\n')
    P = smd_points(os.path.join(vdir, name + '.smd'))
    U = np.unique(P.round(2), axis=0)
    modelio.write_hull_smd(os.path.join(vdir, name + '_hull.smd'), [mdl2cs2.hull_points(U)])
    for g in glob.glob(os.path.join(vdir, name + '_lod*d.smd')): os.remove(g)
    txt = modelio.vmdl_text(name, sub, [name], sorted(remaps.items()), [name + '_hull'], surface=it.get('surface', 'metal'),
                            entity='prop_dynamic' if it.get('dynamic') else 'prop_static', archetype='' if it.get('dynamic') else 'static_prop_model')
    open(os.path.join(vdir, name + '.vmdl'), 'w', newline='\n').write(txt)
    counts, notes = mdl2cs2.make_lods(C['addon'], sub, name, float((P.max(0) - P.min(0)).max()))
    e = rep['models']['model']
    e.update(bounds=[P.min(0).round(1).tolist(), P.max(0).round(1).tolist()], tris=counts, lod_notes=notes)
    log('    merged %d parts: %d tris %s  bounds %s .. %s' % (len(it['parts']), counts[0], counts[1:], e['bounds'][0], e['bounds'][1]))


def ground(it, vdir, rep):
    """item 'ground': the origin stays where the source has it in x/y (the pivot the addon's lua uses) and the lowest point goes to z 0;
    the lift is recorded so parts placed by lua offsets can follow"""
    name = it['name']; e = rep['models']['model']
    dz = float(e['bounds'][0][2])
    for f in glob.glob(os.path.join(vdir, name + '.smd')) + glob.glob(os.path.join(vdir, name + '_lod*d.smd')) + glob.glob(os.path.join(vdir, name + '_hull.smd')):
        smd_shift(f, (0, 0, dz))
    e['bounds'][0][2] = 0.0; e['bounds'][1][2] = round(e['bounds'][1][2] - dz, 1)
    e['origin_was_at_z'] = round(-dz, 2)
    log('    ground: lifted %.1f (the source origin is now at z %.1f)' % (-dz, -dz))


# ---------------------------------------------------------------- convert
def credit(ad):
    return '%s by %s (GMod Workshop %s)' % (ad['title'], ad['author'], ad['id'])


def item_cmd(ad, it, mdls, roots, preview, report):
    name = it['name']
    cmd = [sys.executable, '-X', 'utf8', '-I', os.path.join(CREATE, 'mdl2cs2.py'), ','.join(mdls), C['addon'], name,
           '--sub', '%s/%s' % (C['sub'], name), '--matsub', '%s/%s' % (C['matsub'], it.get('matsub_of', name)),
           '--origin', it.get('origin', 'feet'), '--yaw', str(it.get('yaw', 0)), '--surface', it.get('surface', 'metal'),
           '--maxtex', str(it.get('maxtex', 2048)), '--report', report, '--preview', preview, '--credit', credit(ad)]
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
    report = os.path.join(C['work'], 'reports', name + '.json'); preview = os.path.join(C['work'], 'preview', name + '.png')
    for d in (os.path.dirname(report), os.path.dirname(preview)): os.makedirs(d, exist_ok=True)
    vdir = os.path.join(C['addon'], C['sub'], name)
    if os.path.exists(report) and os.path.isdir(vdir) and not force:
        log('  %s: converted already (--force to redo)' % name); return True
    root = xdir(ad['id'])
    mdls = [os.path.join(root, *m.split('/')) for m in it['mdl'].split(',')]
    miss = [m for m in mdls if not os.path.exists(m)]
    if miss: log('  %s: MISSING %s' % (name, miss[0])); return False
    for d in (vdir,) + (() if it.get('matsub_of') else (os.path.join(C['addon'], C['matsub'], name),)): shutil.rmtree(d, ignore_errors=True)
    roots = [xdir(r) for r in ad.get('roots', []) if os.path.isdir(xdir(r))]
    t = time.time()
    r = subprocess.run(item_cmd(ad, it, mdls, roots, preview, report) + (['--no-lods'] if it.get('parts') else []), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
    tail = '\n'.join((r.stdout + r.stderr).strip().splitlines()[-12:])
    log('  %s: mdl2cs2 rc %d in %.0f s\n    %s' % (name, r.returncode, time.time() - t, tail.replace('\n', '\n    ')))
    if r.returncode != 0 or not os.path.exists(report): return False
    rep = json.load(open(report, encoding='utf-8'))
    skel_path = os.path.join(vdir, name + '_skeleton.json')
    skel = json.load(open(skel_path, encoding='utf-8')) if os.path.exists(skel_path) else {'bones': []}
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
    # pivots: a group's origin moved onto a bone (rotor hub, trunnion) so a script can spin / elevate it about its own origin
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
    fix_normals(name, rep, vdir)                   # normals that face into the mesh, and the LODs built on them
    rep['item'] = {k: it[k] for k in it}
    rep['addon'] = {k: ad.get(k) for k in ('id', 'title', 'author', 'license_note', 'rip', 'rip_risk')}
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
            rp = os.path.join(C['work'], 'reports', it['name'] + '.json')
            if not os.path.exists(rp): continue
            rep = json.load(open(rp, encoding='utf-8'))
            for key, e in rep['models'].items():
                mname = it['name'] + ('' if key == 'model' else '_' + key)
                if not os.path.exists(os.path.join(C['addon'], *e['vmdl'].split('/'))): continue
                role = it.get('role', 'new')
                if isinstance(role, dict): role = role.get(key, 'new')
                d = {'model': e['vmdl'], 'bounds': e['bounds'], 'tris': e['tris'], 'replaces': role, 'credit': credit(ad),
                     'workshop_id': str(ad['id']), 'rip': ad.get('rip', ''), 'rip_risk': ad.get('rip_risk', ''), 'scale': rep.get('scale'),
                     'yaw': rep.get('yaw'), 'dynamic': bool(it.get('dynamic')), 'hulls': e.get('hulls', 1), 'front': '+X', 'note': it.get('note', '')}
                if 'origin_was_at_z' in e: d['source_origin_z'] = e['origin_was_at_z']   # height of the addon's own origin (lua offsets start there)
                if it.get('attach'): d['attach'] = it['attach']
                if 'pivot' in e: d['pivot'] = e['pivot']          # where this part's origin sits in the parent model's space
                out[mname] = d
    os.makedirs(os.path.dirname(C['report']), exist_ok=True)
    json.dump(out, open(C['report'], 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    log('%s: %d models' % (C['report'], len(out)))


# ---------------------------------------------------------------- look at the result (create/smd_view.py: the written SMDs + vmats, not the source)
def cmd_view(only):
    import numpy as np, smd_view
    from PIL import Image
    os.makedirs(os.path.join(C['work'], 'view'), exist_ok=True)
    for ad in catalog()['addons']:
        for it in ad.get('items', []):
            if only and it['name'] not in only: continue
            rp = os.path.join(C['work'], 'reports', it['name'] + '.json')
            if not os.path.exists(rp): continue
            rep = json.load(open(rp, encoding='utf-8'))
            sc = smd_view.Scene(C['addon']); lo, hi = [], []
            todo = [(e, np.array(e.get('pivot', [0, 0, 0]), float)) for e in rep['models'].values()]
            for other, pos in (it.get('attach') or {}).items():          # the moving part shown where the catalog says it goes
                op = os.path.join(C['work'], 'reports', other + '.json')
                if os.path.exists(op): todo += [(e, np.array(pos, float)) for e in json.load(open(op, encoding='utf-8'))['models'].values()]
            for e, off in todo:
                try:                                   # mdl2cs2 names SMD materials "<x>.vmat"; smd_view's table drops the extension
                    txt = open(os.path.join(C['addon'], *e['vmdl'].split('/'))).read()
                    mats = smd_view.load_vmdl_mats(txt); mats.update({k + '.vmat': v for k, v in list(mats.items())})
                    sc.tris += smd_view.load_smd(os.path.join(C['addon'], smd_view.vmdl_smd(txt)), mats, tuple(off))
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
            W.save(os.path.join(C['work'], 'view', it['name'] + '.png'))
            log('  view/%s.png  bounds %s .. %s' % (it['name'], lo.round(0).tolist(), hi.round(0).tolist()))


# ---------------------------------------------------------------- prune
def cmd_prune(gma_too):
    """frees disk: addons with no catalog items lose their whole extract; the others keep their materials (a re-convert still works) and
    the model files catalog items name, nothing else. SteamCMD's folder and rejected items' outputs go too.
    --gma: also any archive still lying there (fetch moves on without them once x/ exists)"""
    freed = 0
    cat = catalog()
    for ad in cat['addons']:
        for it in ad.get('items', []):
            if not it.get('rejected'): continue
            for d in (os.path.join(C['addon'], C['sub'], it['name']), os.path.join(C['addon'], C['matsub'], it['name'])):
                if os.path.isdir(d): freed += du(d); shutil.rmtree(d, ignore_errors=True)
    for d in sorted(glob.glob(os.path.join(C['work'], '*'))):
        wid = os.path.basename(d)
        if not wid.isdigit(): continue
        ad = next((a for a in cat['addons'] if str(a['id']) == wid), None)
        items = [it for it in (ad or {}).get('items', []) if not it.get('rejected')]
        x = os.path.join(d, 'x')
        lt = os.path.join(d, 'lua_txt')
        if os.path.isdir(lt): freed += du(lt); shutil.rmtree(lt, ignore_errors=True)
        if not items:
            if os.path.isdir(x): freed += du(x); shutil.rmtree(x, ignore_errors=True)
        else:
            keep = set()
            for it in items:
                for m in it['mdl'].split(',') + [m for pt in it.get('parts', []) for m in pt['mdl'].split(',')]:
                    keep.add(os.path.splitext(m.lower())[0])
            for r, _, fs in os.walk(os.path.join(x, 'models')):
                for f in fs:
                    pth = os.path.join(r, f); rel = os.path.relpath(pth, x).replace('\\', '/').lower()
                    stem = re.sub(r'\.(dx80|dx90|sw)$', '', os.path.splitext(rel)[0])
                    if stem in keep: continue
                    freed += os.path.getsize(pth); os.remove(pth)
        if gma_too:
            for f in glob.glob(os.path.join(d, '*.gma')) + glob.glob(os.path.join(d, '*.bin')): freed += os.path.getsize(f); os.remove(f)
    if os.path.isdir(C['dl']): shutil.rmtree(C['dl'], ignore_errors=True)
    log('prune: %.0f MB freed; %s is now %.0f MB' % (freed / 1e6, C['work'], du(C['work']) / 1e6))


def main():
    a = sys.argv[1:]
    if len(a) < 2 or not a[0].endswith('.json'): print(__doc__); return

    def opt(name):
        return a[a.index(name) + 1] if name in a else None
    setup(a[0], {k: opt(k) for k in ('--work', '--addon', '--prefix', '--report')})
    cmd = a[1]
    only = set((opt('--only') or '').split(',')) - {''}
    if cmd == 'search': cmd_search(a[2], int(opt('--pages') or 2), opt('--tag'))
    elif cmd == 'details': cmd_details(only)
    elif cmd == 'fetch': cmd_fetch(only)
    elif cmd == 'list': cmd_list(a[2], opt('--grep'), '--stats' in a or '--bones' in a, '--bones' in a)
    elif cmd == 'convert': cmd_convert(only, '--force' in a)
    elif cmd == 'report': cmd_report()
    elif cmd == 'view': cmd_view(only)
    elif cmd == 'prune': cmd_prune('--gma' in a)
    elif cmd == 'normals': cmd_normals(only)
    else: print(__doc__)


if __name__ == '__main__':
    main()
