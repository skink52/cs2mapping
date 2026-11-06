"""Add the head-worn models of the scanned items to the catalog's `hats` (chosen, batch N), skipping what's there already.

usage: python3 -I suggest.py <catalog.json> --batch N [--only id,..] [--dry-run]

From <work>/logs/scan.json (fetch.py --scan). Rules: a single-skeleton prop (no player models, arms, weapons: <= 8 bones,
under 20k vertices), nothing missing (VMTs / colour VTFs), not a tail / wings / jetpack / cape (hat2cs2.NOT_HEAD), and one copy
of each model: packs share models (GMod Tower's in four Pointshop packs), so a model path seen before (or the same file name with
the same size) is skipped; the copy whose item has Pointshop placement wins. The id is the file name (made unique), the name
the Pointshop item's name or the file name in words. Review the previews afterwards and set `chosen` false on the misses.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hatpaths

NOT_HEAD = re.compile(r'(?i)tail|wing|jetpack|cape|backpack|c_arms|_arms|player|ragdoll|^v_|^w_|duck_tube|_jib|explode|spellbook|loot|ghost|seaweed|weapon')


def words(s):
    s = re.sub(r'[_\-]+', ' ', s)
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', s)
    return ' '.join(w.capitalize() for w in s.split())


def main():
    path = sys.argv[1]
    cat = json.load(open(path, encoding='utf-8'))
    p = hatpaths.paths(cat)
    batch = int(sys.argv[sys.argv.index('--batch') + 1]) if '--batch' in sys.argv else 1
    only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
    scan = json.load(open(os.path.join(p['work'], 'logs', 'scan.json'), encoding='utf-8'))
    have_mdl = {h['mdl'].lower() for h in cat['hats']}
    have_sig = {(os.path.basename(h['mdl']).lower(), h.get('verts')) for h in cat['hats']}
    ids = {h['id'] for h in cat['hats']}
    order = sorted(scan, key=lambda k: -sum('lua' in r for r in scan[k]))       # items with Pointshop data first
    added = []
    for iid in order:
        if only and iid not in only: continue
        for r in scan[iid]:
            mdl = r['mdl']; base = os.path.basename(mdl)[:-4]
            if 'error' in r or r['bones'] > 8 or r['verts'] > 20000 or r['verts'] < 12: continue
            if r['missing_vmt'] or r['missing_vtf'] or NOT_HEAD.search(base): continue
            sig = (base.lower() + '.mdl', r['verts'])
            if mdl in have_mdl or sig in have_sig: continue
            hid = re.sub(r'[^a-z0-9_]', '_', base.lower()); k = 2
            while hid in ids: hid = '%s_%d' % (re.sub(r'[^a-z0-9_]', '_', base.lower()), k); k += 1
            name = r['lua']['name'] if 'lua' in r and r['lua'].get('name') else words(base)
            h = {'id': hid, 'item': int(iid), 'mdl': mdl, 'name': name, 'batch': batch, 'verts': r['verts']}
            cat['hats'].append(h); added.append(h); ids.add(hid); have_mdl.add(mdl); have_sig.add(sig)
    for h in added: print('%-26s %-11s %s  (%s)' % (h['id'], h['item'], h['mdl'], h['name']))
    print('%d added' % len(added))
    if '--dry-run' not in sys.argv:
        json.dump(cat, open(path, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
