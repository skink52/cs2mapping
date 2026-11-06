"""Download (SteamCMD anonymous, app 4000) and extract hat items, then scan what's in them.

usage: python3 -I fetch.py <catalog.json> [--only id,..] [--no-download] [--scan]

Downloads and extracts every catalog item (`items`) into <work>/extract/<id>/ (playermodels/fetch.py's download + gma.py, given
our own paths), unless --no-download. --scan lists per item every .mdl with its bone count, vertex count, size (u), the VMTs/VTFs
missing, and the hat placement found in the item's lua (luahats.py, Pointshop 1 items), into <work>/logs/scan.json.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PM = os.path.join(os.path.dirname(HERE), 'playermodels')
sys.path.insert(0, HERE); sys.path.insert(0, PM)
import hatpaths, luahats
import fetch as pmfetch                    # download(), extract(), item_dir(): only given our own paths
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def roots_for(p, it):
    r = [os.path.join(p['work'], 'extract', str(it['id']))]
    r += [os.path.join(p['work'], 'extract', str(d)) for d in it.get('depends', [])]
    if os.path.isdir(os.path.join(p['basegame'], 'materials')): r.append(p['basegame'])
    return r


def missing_materials(m, roots):
    import vtf
    miss_vmt, miss_vtf = [], []
    for t in m.textures:
        vmt = None
        for c in m.cdtextures + ['']:
            vmt = vtf.find_file('materials/%s%s.vmt' % (c, t), roots)
            if vmt: break
        if not vmt: miss_vmt.append(t); continue
        sh, prm = vtf.load_vmt(vmt, roots)
        bt = prm.get('$basetexture')
        if bt and not vtf.find_file('materials/%s.vtf' % bt.replace('.vtf', ''), roots): miss_vtf.append(bt)
    return miss_vmt, miss_vtf


def scan_item(p, it):
    from srcmdl import SrcModel
    root = os.path.join(p['work'], 'extract', str(it['id']))
    lua = luahats.parse_dir(root)
    roots = roots_for(p, it)
    out = []
    for dp, _, fs in os.walk(os.path.join(root, 'models')):
        for f in sorted(fs):
            if not f.lower().endswith('.mdl'): continue
            full = os.path.join(dp, f); rel = os.path.relpath(full, root).replace('\\', '/').lower()
            rec = {'mdl': rel}
            try:
                m = SrcModel(full)
                lo, hi = m.V.min(0), m.V.max(0)
                rec.update(bones=len(m.bones), bone0=m.bones[0]['name'] if m.bones else '', verts=len(m.V),
                           size=[round(float(x), 1) for x in hi - lo], lo=[round(float(x), 1) for x in lo], hi=[round(float(x), 1) for x in hi])
                rec['missing_vmt'], rec['missing_vtf'] = missing_materials(m, roots)
            except Exception as e:
                rec['error'] = str(e)[:200]
            if rel in lua: rec['lua'] = lua[rel]
            out.append(rec)
    return out


def main():
    cat = json.load(open(sys.argv[1], encoding='utf-8'))
    p = hatpaths.paths(cat)
    only = set(int(x) for x in sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
    items = [it for it in cat['items'] if only is None or it['id'] in only]
    for k, it in enumerate(items):
        if '--no-download' in sys.argv or os.path.isdir(os.path.join(p['work'], 'extract', str(it['id']))): continue
        print('[%d/%d] %s %s' % (k + 1, len(items), it['id'], it['title']), flush=True)
        for attempt in range(3):          # SteamCMD sometimes answers "Busy" (another session may be using it)
            d = pmfetch.download(p, it['id'])
            if d and os.path.isdir(d) and os.listdir(d): break
            time.sleep(10)
        try: pmfetch.extract(p, it['id'])
        except Exception as e: print('  !', e, flush=True)
    if '--scan' not in sys.argv: return
    scan_path = os.path.join(p['work'], 'logs', 'scan.json')
    res = json.load(open(scan_path, encoding='utf-8')) if os.path.exists(scan_path) else {}
    for it in items:
        if not os.path.isdir(os.path.join(p['work'], 'extract', str(it['id']))): continue
        res[str(it['id'])] = recs = scan_item(p, it)
        print('== %s %s: %d models, %d with lua placement' % (it['id'], it['title'], len(recs), sum('lua' in r for r in recs)))
        for r in recs:
            if 'error' in r: print('   %-60s ERROR %s' % (r['mdl'], r['error'])); continue
            print('   %-60s %3d bones %6d v  %s%s%s' % (r['mdl'], r['bones'], r['verts'], 'x'.join('%.0f' % s for s in r['size']),
                  '  MISSING %s' % (r['missing_vmt'] + r['missing_vtf']) if r['missing_vmt'] or r['missing_vtf'] else '',
                  '  lua %s %s' % (r['lua']['attach'], r['lua']['name']) if 'lua' in r else ''))
    json.dump(res, open(scan_path, 'w', encoding='utf-8'), indent=1)
    print('scan written to', scan_path)


if __name__ == '__main__':
    main()
