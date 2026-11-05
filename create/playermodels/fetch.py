"""Download GMod workshop items with SteamCMD (anonymous) and extract their models/materials/lua, then list the player
models each item registers (player_manager.AddValidModel lines, read as text, never run) with a quick size check.

usage: python3 -I fetch.py <catalog.json> [--only id,id] [--no-download] [--scan] [--suggest [--scale lo,hi]]

Paths come from the catalog's "paths" block (env overrides: STEAMCMD, PM_WORK). Downloads land in
<steamcmd>/steamapps/workshop/content/4000/<id>/ (a .gma, or a legacy LZMA .bin); extraction goes to <work>/extract/<id>/.
--scan writes <work>/logs/scan.json: per item, every .mdl with its registered name, ValveBiped yes/no, height, head-joint
height, the scale the converter will apply, vertices and missing materials, so the catalog's choices are made from data.
"""
import glob, json, os, re, subprocess, sys, time
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Workshop titles: any script, any console

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gma

CS2_HEAD = 70.8        # head_0 height of the CS2 agent skeleton in its bind pose


def paths(cat):
    p = dict(cat.get('paths', {}))
    p['steamcmd'] = os.environ.get('STEAMCMD', p.get('steamcmd', r'C:\steamcmd\steamcmd.exe'))
    p['work'] = os.environ.get('PM_WORK', p.get('work', r'C:\source1\playermodels'))
    # base-game materials (HL2 + CS:S, extracted from the GMod dedicated server's sourceengine VPKs with vpk.py): searched last
    p['basegame'] = os.environ.get('PM_BASEGAME', p.get('basegame', os.path.join(p['work'], 'basegame')))
    return p


def base_roots(p):
    return [p['basegame']] if os.path.isdir(os.path.join(p['basegame'], 'materials')) else []


def item_dir(p, wid):
    return os.path.join(os.path.dirname(p['steamcmd']), 'steamapps', 'workshop', 'content', '4000', str(wid))


def download(p, wid, log=print):
    d = item_dir(p, wid)
    if os.path.isdir(d) and any(f.endswith(('.gma', '.bin')) for f in os.listdir(d)): return d
    t = time.time()
    r = subprocess.run([p['steamcmd'], '+login', 'anonymous', '+workshop_download_item', '4000', str(wid), '+quit'],
                       capture_output=True, text=True, errors='replace')
    ok = [l for l in r.stdout.splitlines() if 'Success' in l or 'ERROR' in l or 'Failed' in l]
    log('  %s: %s (%.0f s)' % (wid, ok[-1].strip()[:160] if ok else 'no result line', time.time() - t))
    return d if os.path.isdir(d) else None


def extract(p, wid, log=print):
    out = os.path.join(p['work'], 'extract', str(wid))
    if os.path.isdir(out): return out          # extracted before (cleanup.py may have deleted the download since)
    src = item_dir(p, wid)
    arch = [f for f in glob.glob(os.path.join(src, '*')) if f.endswith(('.gma', '.bin'))]
    if not arch: raise FileNotFoundError('%s: nothing downloaded' % wid)
    if True:
        for a in arch:
            info, files = gma.extract(a, out)
            log('  %s: extracted %d files from %s' % (wid, len(files), os.path.basename(a)))
    return out


def registered(root):
    """{mdl path: display name} from player_manager.AddValidModel lines in the item's lua (text only)"""
    out = {}
    for f in glob.glob(os.path.join(root, 'lua', '**', '*.lua'), recursive=True):
        txt = open(f, encoding='latin-1').read()
        for name, mdl in re.findall(r'AddValidModel\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+\.mdl)["\']', txt, re.I):
            out[mdl.replace('\\', '/').lower()] = name
    return out


def scan(root, extra=()):
    from srcmdl import SrcModel
    reg = registered(root)
    res = []
    for f in sorted(glob.glob(os.path.join(root, 'models', '**', '*.mdl'), recursive=True)):
        rel = os.path.relpath(f, root).replace('\\', '/').lower()
        e = {'mdl': rel, 'registered_as': reg.get(rel)}
        try:
            m = SrcModel(f)
            names = [b['name'].lower() for b in m.bones]
            vb = any('bip01_pelvis' in n for n in names) and any('bip01_l_thigh' in n for n in names)
            z = m.V[:, 2]
            e.update(version=m.version, bones=len(names), valvebiped=vb, vertices=int(len(m.V)), height=round(float(z.max() - z.min()), 1),
                     arms='arms' in rel)
            hi = next((i for i, n in enumerate(names) if n.endswith('bip01_head1')), -1)
            if hi >= 0:
                h = float(m.bones[hi]['world'][2, 3] - z.min())
                e['head_joint'] = round(h, 1); e['scale'] = round(CS2_HEAD / h, 3) if h > 1 else None
            # materials present?
            import vtf
            miss, missv = [], []
            for t in m.textures:
                vmt = next((p for p in (vtf.find_file('materials/%s%s.vmt' % (c, t), [root, *extra]) for c in m.cdtextures + ['']) if p), None)
                if not vmt: miss.append(t); continue
                try: shader, prm = vtf.load_vmt(vmt, [root])
                except Exception: missv.append(t + ' (bad vmt)'); continue
                for key in ('$basetexture', '$iris'):     # the colour textures the converter needs
                    v = prm.get(key)
                    if v and not vtf.find_file('materials/%s.vtf' % v.replace('.vtf', ''), [root, *extra]): missv.append(v)
            e['missing_vmt'] = miss; e['missing_vtf'] = missv
        except Exception as ex:
            e['error'] = str(ex)[:200]
        res.append(e)
    return res


SKIP_NAMES = ('_arms', '_hands', '_vm.', '_npc', 'npc_', '_ragdoll', '_corpse', 'zombie', '_enemy', 'hostile')
SKIP_START = ('c_', 'v_', 'arms', 'hands')


def shared_eye_mouth(path):
    """HL2's shared eye/mouth textures: the converter makes stand-ins for these"""
    n = os.path.basename(path.replace(chr(92), '/')).lower()
    return n.startswith(('eyeball', 'mouth', 'teeth')) or n in ('eye_l', 'eye_r', 'eyes', 'eye', 'tongue')


def suggest(models, scale=(1.0, 1.15), max_verts=100000):
    """the scan entries that pass the selection rules (docs/creation/gmod-playermodels.md, step 3), best first:
    registered player model, ValveBiped, CS2-sized, all VMTs and colour textures in the item, not an arms/NPC/ragdoll copy"""
    ok = []
    for e in models:
        base = os.path.basename(e['mdl'])
        why = []
        if not e.get('valvebiped'): why.append('not ValveBiped')
        if not e.get('registered_as'): why.append('not registered as a player model')
        if any(k in base for k in SKIP_NAMES) or base.startswith(SKIP_START): why.append('arms/NPC/ragdoll copy')
        s = e.get('scale') or 0
        if not scale[0] <= s <= scale[1]: why.append('scale %.2f' % s)
        miss = [m for m in (e.get('missing_vmt') or []) + (e.get('missing_vtf') or []) if not any(k in m.lower() for k in ('glass', 'lens')) and not shared_eye_mouth(m)]
        if miss: why.append('missing textures (%s)' % ', '.join(miss[:3]))      # missing lenses become see-through glass
        if e.get('vertices', 0) > max_verts: why.append('%d vertices' % e['vertices'])
        if e.get('error'): why.append('read error')
        e['rejected'] = why
        if not why: ok.append(e)
    return sorted(ok, key=lambda e: -e.get('vertices', 0))


if __name__ == '__main__':
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    p = paths(cat)
    only = None
    for i, a in enumerate(sys.argv[2:], 2):
        if a.startswith('--only='): only = set(a[7:].split(','))
        if a == '--only' and i + 1 < len(sys.argv): only = set(sys.argv[i + 1].split(','))
    items, seen = [], set()
    for it in cat['items']:                 # one entry per item id (an item can supply several catalog models)
        if (not only or str(it['id']) in only) and it['id'] not in seen: items.append(it); seen.add(it['id'])
    report = {}
    for k, it in enumerate(items):
        wid = str(it['id'])
        print('[%d/%d] %s  %s' % (k + 1, len(items), wid, it.get('title', '')), flush=True)
        try:
            if '--no-download' not in sys.argv: download(p, wid)
            root = extract(p, wid)
            if '--scan' in sys.argv:
                report[wid] = {'title': it.get('title'), 'models': scan(root, base_roots(p))}
                for e in report[wid]['models']:
                    print('    %-60s %s' % (e['mdl'], {k2: e.get(k2) for k2 in ('registered_as', 'valvebiped', 'height', 'head_joint', 'scale', 'vertices', 'missing_vmt', 'error') if e.get(k2) not in (None, [])}), flush=True)
        except Exception as ex:
            print('  FAILED: %s' % ex, flush=True); report[wid] = {'error': str(ex)}
    if '--scan' in sys.argv:
        os.makedirs(os.path.join(p['work'], 'logs'), exist_ok=True)
        old = {}
        sp = os.path.join(p['work'], 'logs', 'scan.json')
        if os.path.exists(sp): old = json.load(open(sp, encoding='utf-8'))
        old.update(report)
        json.dump(old, open(sp, 'w'), indent=1)
        print('scan ->', sp)
    if '--suggest' in sys.argv:          # from scan.json: the models that pass the rules, per item
        sp = os.path.join(p['work'], 'logs', 'scan.json')
        sc = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
        print('\nsuggested (passes the rules; first = most detailed):')
        for it in items:
            k = sys.argv.index('--scale') if '--scale' in sys.argv else -1      # --scale lo,hi: stylised / fun skins (default 1.0,1.15)
            rng = tuple(float(x) for x in sys.argv[k + 1].split(',')) if k > 0 else (1.0, 1.15)
            good = suggest(sc.get(str(it['id']), {}).get('models', []), rng)
            print('  %s %-45s %s' % (it['id'], it.get('title', '')[:45], ', '.join('%s (%dk v, x%.2f)' % (e['mdl'], e['vertices'] // 1000, e['scale']) for e in good[:4]) or 'none'))
