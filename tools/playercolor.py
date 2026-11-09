"""!activator Color outputs -> io script SetColor (stage D `playercolor` pass).

CS:GO maps tint players with `OnStartTouch !activator Color "255 0 0"` (team-colour spawn triggers). The importer drops these
outputs (mg_color_multigames, 9 Nov 2026: 3 SPECIAL lines in the dropped I/O report). Each one is read back from the VMF, its owner
found in the vmap by class (droppedio.ALIAS covers converted classes) and name, or bounds / origin for unnamed ones, and re-added as
RunScriptInput Color_<r>_<g>_<b>, which calls pawn.SetColor on the activator (cs_script-notes: SetColor replaces Color on players).
"""
import math, os, re
import dmx, droppedio

HEAD_LINE = '//   Color_<r>_<g>_<b> replaces !activator Color (player tint)'
JS = r'''// ---------------------------------------------------------------- !activator Color replacement (output dropped by the importer)
for (const c of __COLORS__) {
    const [r, g, b] = c.split('_').map(Number);
    Instance.OnScriptInput("Color_" + c, ({ activator }) => {
        const pawn = activator instanceof CSPlayerPawn ? activator : activator instanceof CSPlayerController ? activator.GetPlayerPawn() : undefined;
        if (pawn && pawn.IsValid()) pawn.SetColor({ r, g, b, a: 255 });
    });
}'''


def run(m, c, vmfpath):
    c.colors = set()
    if not vmfpath or not os.path.exists(vmfpath): return
    owners = [v for v in droppedio.vmf_entities(vmfpath) if any(t[1].lower() == '!activator' and t[2].lower() == 'color' for t in v['conns'])]
    if not owners: return
    # only outputs the importer dropped are re-added: most !activator Color outputs survive the import (mg_color_multigames: 20 of 23)
    ents = m.entities(); used = set(); n = 0; lost = []; removed_dups = 0
    for v in owners:
        classes = (v['cls'],) + droppedio.ALIAS.get(v['cls'], ())
        pool = [e for e in ents if m.cls(e).lower() in classes and e not in used]
        if v['name']: cand = [e for e in pool if m.name(e).lower() == v['name'].lower()]
        else: cand = [e for e in pool if not m.name(e)]
        def dist(e):
            if v['bbox']:
                b = m.bounds(e)
                if b: return math.dist([(v['bbox'][0][i] + v['bbox'][1][i]) / 2 for i in range(3)], [(b[0][i] + b[1][i]) / 2 for i in range(3)])
            return math.dist(v['origin'], m.origin(e)) if v['origin'] else 1e9
        best = min(cand, key=dist, default=None)
        if best is None or (not v['name'] and dist(best) > 3.0):
            lost.append(droppedio._who(v)); continue
        used.add(best)
        have = set(m.conn_tuple(cc)[:4] for cc in m.conns(best))
        kept = set((o.lower(), p.strip()) for o, tg, i, p in have if tg.lower() == '!activator' and i.lower() == 'color')
        # rerun-safe: drop script Color_ outputs an earlier run added next to a kept native one
        keyed = set((o, '%d_%d_%d' % tuple(int(float(x)) for x in re.findall(r'-?[\d.]+', p)[:3])) for o, p in kept if len(re.findall(r'-?[\d.]+', p)) >= 3)
        arr = dmx.geta(m.E[best], b'connectionsData')[2]
        dup = [ci for ci in arr if m.conn_tuple(m.E[ci])[1] == c.script and m.conn_tuple(m.E[ci])[3].startswith('Color_')
               and (m.conn_tuple(m.E[ci])[0].lower(), m.conn_tuple(m.E[ci])[3][6:]) in keyed]
        if dup: arr[:] = [ci for ci in arr if ci not in dup]; removed_dups += len(dup)
        have = set(m.conn_tuple(cc)[:4] for cc in m.conns(best))
        for t in v['conns']:
            if t[1].lower() != '!activator' or t[2].lower() != 'color': continue
            if (t[0].lower(), t[3].strip()) in kept: continue          # the importer kept this one
            rgb = [int(float(x)) for x in re.findall(r'-?[\d.]+', t[3])[:3]]
            if len(rgb) != 3: continue
            key = '%d_%d_%d' % tuple(max(0, min(255, x)) for x in rgb)
            if (t[0], c.script, 'RunScriptInput', 'Color_' + key) in have: continue
            m.add_conn(best, t[0], c.script, 'RunScriptInput', 'Color_' + key, t[4], t[5]); c.colors.add(key); n += 1
    if removed_dups: c.log.append('playercolor: removed %d script Color_ outputs an earlier run added next to outputs the importer kept' % removed_dups)
    if n: c.log.append('playercolor: %d !activator Color outputs (dropped by the importer) -> script Color_<r>_<g>_<b> (SetColor on the activator)' % n)
    if lost: c.todo.append('playercolor: owner not found in the vmap for %s: re-add its !activator Color output by hand' % ', '.join(lost))


def patch_script(js, colors):
    mt = re.match(r'import \{([^}]*)\} from "cs_script/point_script";', js)
    if mt:
        names = [x.strip() for x in mt.group(1).split(',') if x.strip()]
        names += [x for x in ('CSPlayerPawn', 'CSPlayerController') if x not in names]
        js = js[:mt.start()] + 'import { %s } from "cs_script/point_script";' % ', '.join(names) + js[mt.end():]
    else:
        js = 'import { Instance, CSPlayerPawn, CSPlayerController } from "cs_script/point_script";\n\n' + js
    js = re.sub(r'\n// -{10,} !activator Color replacement.*?\n\}(?=\n|$)', '', js, flags=re.S)
    lines = js.rstrip('\n').split('\n')
    last_head = max((i for i, l in enumerate(lines[:40]) if l.startswith('//   ')), default=None)
    if HEAD_LINE not in lines and last_head is not None: lines.insert(last_head + 1, HEAD_LINE)
    return '\n'.join(lines) + '\n\n' + JS.replace('__COLORS__', '[%s]' % ', '.join('"%s"' % k for k in sorted(colors))) + '\n'
