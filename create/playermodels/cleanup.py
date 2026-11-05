"""Free disk space after a batch: downloads and extracted files that aren't needed any more.

usage: python3 -I cleanup.py <catalog.json> [--prune] [--dry-run]

  - SteamCMD downloads (<steamcmd>/steamapps/workshop/content/4000/<id>/) of every catalog item: the extract holds what's needed and
    fetch.py downloads again if ever needed. Only ids in the catalog are touched (other GMod downloads, e.g. TTT maps, stay).
  - <work>/extract/<id>/ of items with no chosen model.
  - --prune: in items that are used, delete everything the chosen models don't need (other characters in a pack, props, arms, lua):
    keeps each chosen .mdl with its .vvd/.vtx/.phy and the VMTs/VTFs its materials reference, so it can be reconverted.
The converted addon and the reports are never touched. Prints what it deletes and the space freed.
"""
import json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch, vtf
from srcmdl import SrcModel


def size(p):
    if os.path.isfile(p): return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(r, f)) for r, d, fs in os.walk(p) for f in fs)


def needed(root, mdls):
    """relative paths (lower case, '/') the chosen models need inside an extracted item"""
    keep = set()
    for rel in mdls:
        base = rel[:-4]
        for ext in ('.mdl', '.vvd', '.dx90.vtx', '.dx80.vtx', '.sw.vtx', '.vtx', '.phy'):
            if os.path.exists(os.path.join(root, *(base + ext).split('/'))): keep.add(base + ext)
        m = SrcModel(os.path.join(root, *rel.split('/')))
        for t in m.textures:
            for cd in m.cdtextures + ['']:
                vmt = 'materials/%s%s.vmt' % (cd, t)
                p = vtf.find_file(vmt, [root])
                if not p: continue
                keep.add(os.path.relpath(p, root).replace('\\', '/').lower())
                try: shader, prm = vtf.load_vmt(p, [root])
                except Exception: continue
                inc = prm.get('include')
                if inc: keep.add(inc.replace('\\', '/').lower())
                for k, v in prm.items():
                    if not isinstance(v, str) or not k.startswith('$'): continue
                    q = vtf.find_file('materials/%s.vtf' % v.strip('"').replace('.vtf', ''), [root])
                    if q: keep.add(os.path.relpath(q, root).replace('\\', '/').lower())
    return keep


def main():
    cat = json.load(open(sys.argv[1])); p = fetch.paths(cat)
    dry = '--dry-run' in sys.argv
    used = {}
    for it in cat['items']:
        if it.get('chosen'): used.setdefault(it['id'], []).append(it['mdl'].lower())
    freed = 0
    def rm(path, why):
        nonlocal freed
        if not os.path.exists(path): return
        n = size(path); freed += n
        print('%s %-70s %7.1f MB  (%s)' % ('would delete' if dry else 'delete', path, n / 1e6, why))
        if not dry:
            if os.path.isdir(path): shutil.rmtree(path)
            else: os.remove(path)
    for wid in sorted({it['id'] for it in cat['items']}):
        rm(fetch.item_dir(p, wid), 'download, extracted already')
        ex = os.path.join(p['work'], 'extract', str(wid))
        if wid not in used:
            rm(ex, 'no chosen model')
        elif '--prune' in sys.argv and os.path.isdir(ex):
            keep = needed(ex, used[wid])
            for r, d, fs in os.walk(ex):
                for f in fs:
                    full = os.path.join(r, f); rel = os.path.relpath(full, ex).replace('\\', '/').lower()
                    if rel not in keep:
                        n = os.path.getsize(full); freed += n
                        if not dry: os.remove(full)
            if not dry:
                for r, d, fs in sorted(os.walk(ex), key=lambda x: -len(x[0])):
                    if not os.listdir(r): os.rmdir(r)
            print('%s %-70s kept %d files' % ('would prune' if dry else 'pruned', ex, len(keep)))
    print('%s %.2f GB' % ('would free' if dry else 'freed', freed / 1e9))


if __name__ == '__main__':
    main()
