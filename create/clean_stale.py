"""Removes material files under materials/models/<prefix>/<prop>/ that the prop's vmdl no longer uses (left behind when a chart
moves to a stock material or an atlas is renamed). Run it before zipping a delivery.

usage: clean_stale.py [props.json] [--dry-run]
Props come from props.json (build_all_props.py); without it, every folder under models/<prefix>/ that has <name>/<name>.vmdl.
Uses $CS2_ADDON_OUT and $CS2_MODEL_PREFIX.

From trenchwarfare-cs2/tools/clean_stale.py (MIT), made project-neutral.
"""
import os, re, sys, json

OUT = os.environ.get('CS2_ADDON_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'addon'))
PREFIX = os.environ.get('CS2_MODEL_PREFIX', 'props')


def clean(names, dry=False):
    removed = []
    for name in names:
        vmdl = os.path.join(OUT, 'models', PREFIX, name, name + '.vmdl')
        mdir = os.path.join(OUT, 'materials', 'models', PREFIX, name)
        if not (os.path.exists(vmdl) and os.path.isdir(mdir)): continue
        rel = 'materials/models/%s/%s/' % (PREFIX, name)
        refs = set(re.findall(re.escape(rel) + r'([\w.-]+)\.vmat', open(vmdl).read()))
        keep = set()
        for v in refs:
            p = os.path.join(mdir, v + '.vmat')
            if os.path.exists(p):
                keep.add(v + '.vmat')
                keep |= {os.path.basename(t) for t in re.findall(r'"(materials/[^"]+\.(?:png|tga|jpg))"', open(p).read()) if t.startswith(rel)}
        for f in sorted(os.listdir(mdir)):
            if f not in keep and os.path.isfile(os.path.join(mdir, f)):
                removed.append(os.path.join(mdir, f))
                if not dry: os.remove(os.path.join(mdir, f))
        if not dry and not os.listdir(mdir): os.rmdir(mdir)
    return removed


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--dry-run']; dry = '--dry-run' in sys.argv
    pj = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(OUT)), 'props.json')
    if os.path.exists(pj):
        names = list(json.load(open(pj)))
    else:
        md = os.path.join(OUT, 'models', PREFIX)
        names = [n for n in (os.listdir(md) if os.path.isdir(md) else []) if os.path.exists(os.path.join(md, n, n + '.vmdl'))]
    r = clean(names, dry)
    for p in r: print(('would remove ' if dry else 'removed ') + os.path.relpath(p, OUT))
    print('stale material files %s: %d' % ('found' if dry else 'removed', len(r)))
