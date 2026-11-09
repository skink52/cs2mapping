"""CS:GO weapon world models on props -> CS2's own weapon models (stage D `weaponmodels` pass).

cs_mdl_import can't compile CS:GO's stock weapon models (models/weapons/w_snip_awp.mdl and the like: "Models failed to compile"
in the import report, which holds the map in autoport; mg_minecraft_multigames, 9 Nov 2026). CS2 ships every weapon as
weapons/models/<dir>/weapon_<name>.vmdl, so a prop using models/weapons/w_<name>[_dropped|_dropped_placed].vmdl is pointed at
CS2's weapon_<name>.vmdl when CS2's pak01 has it. Models CS2 doesn't have are listed and left alone.
"""
import re

# CS:GO world-model names that CS2 renamed (CS:GO w_rif_m4a1 is the M4A4, w_pist_223 the USP-S, w_rif_m4a1_s the M4A1-S)
RENAMED = {'pist_223': 'pist_usp_silencer', 'rif_m4a1': 'rif_m4a4', 'rif_m4a1_s': 'rif_m4a1_silencer', 'pist_hkp2000': 'pist_hkp2000'}
W_RE = re.compile(r'^models/weapons/w_([a-z0-9_]+?)(?:_dropped(?:_placed)?)?\.(?:vmdl|mdl)$', re.I)


def cs2_weapons(cs2v):
    """weapon_<name> -> weapons/models/<dir>/weapon_<name>.vmdl, from CS2's pak01 directory."""
    out = {}
    for p in (cs2v.files if cs2v else {}):
        mt = re.match(r'^weapons/models/[^/]+/(weapon_[a-z0-9_]+)\.vmdl_c$', p)
        if mt: out.setdefault(mt.group(1), p[:-2])
    return out


def run(m, c):
    have = cs2_weapons(c.cs2v)
    if not have:
        c.todo.append('weaponmodels: CS2 pak01 not staged (<root>/vpk/cs2_pak01_dir.vpk), no weapon models repointed'); return
    done = {}; missing = set()
    for e in m.entities():
        md = (m.P(e, 'model', '') or '').replace('\\', '/')
        mt = W_RE.match(md)
        if not mt: continue
        nm = mt.group(1).lower(); nm = RENAMED.get(nm, nm)
        new = have.get('weapon_' + nm)
        if not new: missing.add(md); continue
        m.setp(e, 'model', new); done[md] = done.get(md, 0) + 1
    if done:   # Hammer's asset list too: the build's asset pre-compile reads it
        swap = {k.encode(): have['weapon_' + RENAMED.get(W_RE.match(k).group(1).lower(), W_RE.match(k).group(1).lower())].encode() for k in done}
        targets = ([m.doc.prefix[0]] if m.doc.prefix else []) + [el['attrs'] for el in m.E if el['type'] == b'$prefix_element$']
        for attrs in targets:
            for pa in attrs:
                if pa[0] == b'map_asset_references':
                    new = []
                    for x in pa[2]:
                        y = swap.get(x, x)
                        if y not in new: new.append(y)
                    pa[2] = new
        c.log.append('weaponmodels: %d props on CS:GO weapon models -> CS2 weapon models (%s)' %
                     (sum(done.values()), ', '.join('%s x%d -> %s' % (k, v, have['weapon_' + RENAMED.get(W_RE.match(k).group(1).lower(), W_RE.match(k).group(1).lower())]) for k, v in sorted(done.items()))))
        c.todo.append('weaponmodels: CS2 weapon models are a different size/pivot from CS:GO\'s: check the repointed display props sit right')
    if missing: c.todo.append('weaponmodels: no CS2 weapon model for %s' % ', '.join(sorted(missing)))
