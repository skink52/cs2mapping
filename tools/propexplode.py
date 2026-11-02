"""Explosions that CS:GO models carried in their own prop_data: copied onto the props that use them.

  python propexplode.py <vmap in> <vmap out> <CS:GO content root> [<embedded files root>]

In CS:GO a prop's ExplodeDamage / ExplodeRadius of 0 (or no key) meant "use the model's prop_data": oildrum001_explosive has explosive_damage 120,
explosive_radius 256 in its .mdl. cs_mdl_import keeps the model's health but drops those two, so in CS2 only props whose own keys were set still
explode (ttt_island17: phys26 did, the other four explosive barrels, the gas can and the propane tank didn't). CS2's prop entities still have both
keys, so each prop with 0 / no value gets the model's numbers; props that set their own keep them. The .mdl is read from the addon's embedded files
first (custom models packed in the BSP), then from the CS:GO content. A prop_data "base" class is looked up in scripts/propdata.txt.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V

PROP_CLASSES = ('prop_physics', 'prop_physics_multiplayer', 'prop_physics_override', 'prop_physics_respawnable', 'prop_dynamic', 'prop_dynamic_override')

def kv_block(text, name):
    m = re.search(r'\b%s\s*\{([^{}]*)\}' % re.escape(name), text)
    return dict((k.lower(), v) for k, v in re.findall(r'"([^"]+)"\s+"([^"]*)"', m.group(1))) if m else {}

def model_propdata(mdl, roots, bases, cache={}):
    """(damage, radius) from the .mdl's embedded keyvalues, falling back to its base class in propdata.txt."""
    if mdl in cache: return cache[mdl]
    out = (0.0, 0.0)
    for r in roots:
        p = os.path.join(r, mdl.replace('/', os.sep))
        if not os.path.exists(p): continue
        text = open(p, 'rb').read().decode('latin-1')
        pd = kv_block(text, 'prop_data')
        base = bases.get(pd.get('base', '').lower(), {})
        dmg = float(pd.get('explosive_damage', base.get('explosive_damage', 0)) or 0)
        rad = float(pd.get('explosive_radius', base.get('explosive_radius', 0)) or 0)
        out = (dmg, rad); break
    cache[mdl] = out
    return out

def base_classes(roots):
    """scripts/propdata.txt: { "Metal.Small" { ... } ... } -> {name: keys}"""
    for r in roots:
        p = os.path.join(r, 'scripts', 'propdata.txt')
        if os.path.exists(p):
            t = open(p, encoding='latin-1').read()
            return {n.lower(): dict((k.lower(), v) for k, v in re.findall(r'"([^"]+)"\s+"([^"]*)"', body)) for n, body in re.findall(r'"([^"]+)"\s*\{([^{}]*)\}', t)}
    return {}

def run(m, roots):
    bases = base_classes(roots); changed = []
    for e in m.entities():
        if m.cls(e) not in PROP_CLASSES: continue
        model = m.P(e, 'model', '')
        if not model: continue
        mdl = re.sub(r'\.vmdl$', '.mdl', model.lower())
        dmg, rad = model_propdata(mdl, roots, bases)
        if not dmg and not rad: continue
        own_d = float(m.P(e, 'ExplodeDamage', '0') or 0); own_r = float(m.P(e, 'ExplodeRadius', '0') or 0)
        if own_d or own_r: continue   # the mapper chose its own explosion
        m.setp(e, 'ExplodeDamage', '%g' % dmg); m.setp(e, 'ExplodeRadius', '%g' % rad)
        changed.append('%s %s (%s: %g / %g)' % (m.cls(e), m.name(e) or '(unnamed)', os.path.basename(mdl), dmg, rad))
    return changed

if __name__ == '__main__':
    if len(sys.argv) < 4: sys.exit(__doc__)
    mp = V.Map(sys.argv[1]); roots = sys.argv[4:] + [sys.argv[3]]
    ch = run(mp, roots); mp.save(sys.argv[2])
    for c in ch: print('explode\t' + c)
    print('summary\tprops given their model\'s explosion: %d' % len(ch))
