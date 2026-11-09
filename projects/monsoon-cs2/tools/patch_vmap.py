"""Delta patch: small changes applied straight onto the user's latest vmap, with no regeneration (nothing the generator places
randomly moves, and every Hammer edit stays). Re-runnable: entities already present (same targetname, or same class+model at
the same rounded origin) are not added twice. Rewrites map_asset_references and the per-class entity counts at the end.

usage: patch_vmap.py <user's latest .vmap> <out .vmap> [addon_out] [patch.json]

Edit the PATCH section below for one-off changes, or pass a JSON file:
  {"group": "gen",                                  vis group for added entities
   "drop_classes": ["cs_minimap_boundary"],         remove every entity of these classes
   "drop_names": ["old_relay"],                     remove entities by targetname (a trailing * matches a prefix)
   "set": {"sun": {"brightness": "2.0"}},           change keys of named entities
   "add": [{"classname": "prop_dynamic", "origin": [0, 0, 64], "angles": [0, 90, 0],
            "targetname": "spinner", "model": "models/props/spinner.vmdl", "solid": "0"}]}
Back up the .vmap first, close Hammer, then copy the output over the map.

From trenchwarfare-cs2/tools/patch_vmap.py (MIT), made project-neutral.
"""
import os, sys, json, fnmatch
import dmx
from dmx import T_STRING
import vmaplib, vmapgen

# ---------------------------------------------------------------- PATCH (used when no patch.json is given)
PATCH = dict(
    group='gen',
    drop_classes=[],          # e.g. ['cs_minimap_boundary']: CS2 drew its own minimap from them instead of the radar
    drop_names=[],
    set={},
    add=[],
)


def key_of(c):
    ep = c.get('entity_properties')
    return ep.get('targetname') or (ep.get('classname'), ep.get('model') or '', tuple(round(v) for v in c.get('origin')))


def patch(src, out_path, addon_out='', p=PATCH):
    d = vmapgen.open_map(src, addon_out)
    world = d.root.get('world')
    kids = world.attr('children')
    drop_names = list(p.get('drop_names', []))
    kept, have, dropped, changed = [], set(), 0, 0
    for c in kids[2]:
        if c.type == 'CMapEntity':
            ep = c.get('entity_properties'); nm = ep.get('targetname') or ''
            if ep.get('classname') in p.get('drop_classes', ()) or any(fnmatch.fnmatchcase(nm, pat) for pat in drop_names if nm):
                dropped += 1; continue
            if nm in p.get('set', {}):
                for k, v in p['set'][nm].items(): ep.set(k, T_STRING, str(v))
                changed += 1
            have.add(key_of(c))
        kept.append(c)
    kids[2] = kept
    added = 0
    for a in p.get('add', []):
        a = dict(a); cls = a.pop('classname'); o = tuple(a.pop('origin', (0, 0, 0))); an = tuple(a.pop('angles', (0, 0, 0)))
        k = a.get('targetname') or (cls, a.get('model', ''), tuple(round(v) for v in o))
        if k in have: continue                      # already there from an earlier run
        vmaplib.ent(cls, o, an, group=p.get('group', ''), **a); have.add(k); added += 1
    # group=None: nothing is replaced by vis group; finish() adds the new nodes and recounts everything
    vmapgen.finish(d, out_path, group=None, first_run_cleanup=False)
    print('patched: %d added, %d removed, %d changed' % (added, dropped, changed))
    return added, dropped, changed


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    p = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else PATCH
    patch(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '', p)
