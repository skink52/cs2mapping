"""Reproduce what opening + saving a BSPSource VMF in CS:GO Hammer changes.

Found by diffing an untouched BSPSource VMF (.vmx) against the same file after a
Hammer save: Hammer adds versioninfo / viewsettings / cordons blocks, resets
mapversion, puts id/mapversion/classname first on worldspawn, adds the full
editor block (color, visgroupshown, visgroupautoshown, logicalpos) to entities
and solids, adds "rotation" "0" to every side, rewrites plane points and
texture axes with %g precision (no -0), and upper-cases side materials.
"""
import re, sys
import vmf

def _g(x):
    v = float(x)
    if v == 0: v = 0.0
    s = '%g' % v
    return '0' if s == '-0' else s

_num = re.compile(r'-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')

def _plane(s):
    pts = re.findall(r'\(([^)]*)\)', s)
    return ' '.join('(' + ' '.join(_g(n) for n in p.split()) + ')' for p in pts)

def _axis(s):
    m = re.match(r'\s*\[([^\]]*)\]\s*(\S+)', s)
    if not m: return s
    return '[' + ' '.join(_g(n) for n in m.group(1).split()) + '] ' + _g(m.group(2))

def _editor(node, color, logical=None):
    ed = next((c for c in node.ch if c.name == 'editor'), None)
    if ed is None:
        ed = vmf.Node('editor'); node.ch.append(ed)
    if ed.get('color') is None: ed.set('color', color)
    if ed.get('visgroupshown') is None: ed.set('visgroupshown', '1')
    if ed.get('visgroupautoshown') is None: ed.set('visgroupautoshown', '1')
    if logical is not None and ed.get('logicalpos') is None: ed.set('logicalpos', logical)

def _fix_solid(solid, color):
    for side in solid.ch:
        if side.name != 'side': continue
        if side.get('plane'): side.set('plane', _plane(side.get('plane')))
        for k in ('uaxis', 'vaxis'):
            if side.get(k): side.set(k, _axis(side.get(k)))
        if side.get('material'): side.set('material', side.get('material').upper())
        if side.get('rotation') is None:
            kv = side.kv; idx = next((i for i, (k, _) in enumerate(kv) if k.lower() == 'vaxis'), len(kv) - 1)
            kv.insert(idx + 1, ('rotation', '0'))
    _editor(solid, color)

ILLUSIONARY_TO_BRUSH = {'Solidity': '1', 'StartDisabled': '0', 'solidbsp': '0', 'InputFilter': '0', 'invert_exclusion': '0', 'excludednpc': ''}

def entity_fixes(root, notes):
    """entities Valve's importer would drop (they're on its exclusion list) but that carry visible geometry"""
    n = 0
    for e in root.ch:
        if e.name == 'entity' and (e.get('classname') or '').lower() == 'func_illusionary':
            e.set('classname', 'func_brush')
            for k, v in ILLUSIONARY_TO_BRUSH.items():
                if e.get(k) is None: e.set(k, v)
            sf = int(e.get('spawnflags') or 0); e.set('spawnflags', str(sf | 2))
            n += 1
    if n: notes.append('%d func_illusionary -> func_brush (Solidity Never) so the importer keeps them' % n)

def resave(text, notes=None):
    root = vmf.parse(text)
    entity_fixes(root, notes if notes is not None else [])
    top = {c.name.lower(): c for c in root.ch}
    world = top.get('world')
    vi = top.get('versioninfo') or vmf.Node('versioninfo')
    for k, v in (('editorversion', '400'), ('editorbuild', '9324'), ('mapversion', '0'), ('formatversion', '100'), ('prefab', '0')):
        if vi.get(k) is None: vi.set(k, v)
    vg = top.get('visgroups') or vmf.Node('visgroups')
    vs = top.get('viewsettings') or vmf.Node('viewsettings')
    for k, v in (('bSnapToGrid', '1'), ('bShowGrid', '1'), ('bShowLogicalGrid', '0'), ('nGridSpacing', '64'), ('bShow3DGrid', '0')):
        if vs.get(k) is None: vs.set(k, v)
    cams = top.get('cameras') or vmf.Node('cameras')
    if not cams.kv: cams.set('activecamera', '-1')
    cords = top.get('cordons') or vmf.Node('cordons')
    if cords.get('active') is None: cords.set('active', '0')

    if world is not None:
        d = {k.lower(): (k, v) for k, v in world.kv}
        first = [('id', d.pop('id', ('id', '1'))[1]), ('mapversion', '0'), ('classname', d.pop('classname', ('classname', 'worldspawn'))[1])]
        d.pop('mapversion', None)
        world.kv = first + sorted(d.values(), key=lambda kv: kv[0].lower())
        for c in world.ch:
            if c.name == 'solid': _fix_solid(c, '0 %d %d' % (100 + (int(c.get('id', '0')) * 37) % 155, 100 + (int(c.get('id', '0')) * 91) % 155))

    ents = [c for c in root.ch if c.name == 'entity']
    for i, e in enumerate(ents):
        brush = any(c.name == 'solid' for c in e.ch)
        for c in e.ch:
            if c.name == 'solid': _fix_solid(c, '220 30 220')
        _editor(e, '220 30 220' if brush else '220 30 220', '[0 %d]' % (i * 500 % 30000))
        # editor block goes last, after connections/solids, like Hammer writes it
        ed = [c for c in e.ch if c.name == 'editor']; rest = [c for c in e.ch if c.name != 'editor']
        e.ch = rest + ed

    others = [c for c in root.ch if c.name.lower() not in ('versioninfo', 'visgroups', 'viewsettings', 'world', 'entity', 'cameras', 'cordons')]
    new = vmf.Node('root')
    new.ch = [vi, vg, vs] + ([world] if world is not None else []) + ents + others + [cams, cords]
    return vmf.dump(new)

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    out = resave(open(src, encoding='utf-8', errors='surrogateescape').read())
    open(dst, 'w', encoding='utf-8', errors='surrogateescape', newline='\r\n').write(out)
