"""removes material files under materials/models/tw/<prop>/ that no prop vmdl references any more (left behind when a chart moves to a stock material)"""
import os, re, sys, json
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'addon')
props = json.load(open(os.path.join(OUT, '..', 'props.json')))
removed = 0
for name in props:
    vmdl = os.path.join(OUT, 'models/tw/%s/%s.vmdl' % (name, name))
    mdir = os.path.join(OUT, 'materials/models/tw', name)
    if not (os.path.exists(vmdl) and os.path.isdir(mdir)): continue
    refs = set(re.findall(r'materials/models/tw/%s/([\w]+)\.vmat' % name, open(vmdl).read()))
    keep = set()
    for v in refs:
        p = os.path.join(mdir, v + '.vmat')
        if os.path.exists(p): keep.add(v + '.vmat'); keep |= {os.path.basename(t) for t in re.findall(r'"(materials/[^"]+\.png)"', open(p).read())}
    for f in os.listdir(mdir):
        if f not in keep:
            os.remove(os.path.join(mdir, f)); removed += 1
    if not os.listdir(mdir): os.rmdir(mdir)
print('stale material files removed:', removed)
