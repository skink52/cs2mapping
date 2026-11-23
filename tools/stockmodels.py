"""CS:GO stock character models on props -> CS2's own (a stage D pass like `weaponmodels`).

cs_mdl_import can't make CS:GO's chicken, hostage or agent models into working CS2 models: post_import_cleanup skips models/player/
(the t/ct_animations set runs for an hour and the result is unusable) and the chicken / hostage compiles fail ("MODELS - FAILED TO
COMPILE" in 11 cleanup reports: chicken/chicken x2, characters/hostage_01, player/tm_pirate_variantb/c, player/tm_professional_var3;
mg_50arenas lists 27 agents under FAILED TO IMPORT). CS2 ships its own:
  models/chicken/<name>.mdl                    -> models/chicken/<name>.vmdl (same path)
  models/characters/hostage_0N[_*].mdl         -> models/hostage/hostage.vmdl
  models/player/[custom_player/legacy/]<agent>.mdl  (tm_* / ctm_*)
      -> characters/models/<family>/<agent>.vmdl, else <family>/<family>.vmdl, else that family's first variant,
         else the team default (tm_phoenix / ctm_sas): CS2 dropped gsg9, gign, idf, separatist, anarchist, pirate, ...
A prop is repointed when CS2's pak01 has the target, also when the addon has its own import of the model (an opt-in pass, like weaponmodels). Custom player
models (models/player/custom/..., mapeadores, ...) are left alone. Substitutes (not the same agent) and every repointed agent prop
(CS2 agents have no CS:GO idle sequences, a prop_dynamic stands in its bind pose) go to TO CHECK.

    stockmodels.run(m, c)      c.cs2v = CS2 pak01 VPK (vpk.VPK), (nothing else used)
    stockmodels.remap(path, cs2_models) -> (new path, 'same' | 'family' | 'variant' | 'team') or (None, None)
"""
import re

TEAM_DEFAULT = {'tm': 'characters/models/tm_phoenix/tm_phoenix.vmdl', 'ctm': 'characters/models/ctm_sas/ctm_sas.vmdl'}
HOSTAGE = 'models/hostage/hostage.vmdl'
AGENT_RE = re.compile(r'^models/player/(?:custom_player/legacy/)?((c?tm)_[a-z0-9_]+?)\.(?:vmdl|mdl)$')
CHICKEN_RE = re.compile(r'^models/chicken/([a-z0-9_]+)\.(?:vmdl|mdl)$')
HOSTAGE_RE = re.compile(r'^models/characters/hostage_0\d[a-z0-9_]*\.(?:vmdl|mdl)$')


def cs2_models(cs2v):
    """set of CS2 stock model paths (.vmdl) from pak01's directory"""
    return set(p[:-2] for p in (cs2v.files if cs2v else {}) if p.endswith('.vmdl_c'))


def family_of(agent):
    """ctm_fbi_variantc -> ctm_fbi; tm_professional_var3 -> tm_professional; tm_phoenix -> tm_phoenix"""
    return re.sub(r'_var(?:iant)?[a-z0-9]*$', '', agent)


def remap(path, have):
    p = path.lower().replace('\\', '/')
    mt = CHICKEN_RE.match(p)
    if mt:
        new = 'models/chicken/%s.vmdl' % mt.group(1)
        return (new, 'same') if new in have else (None, None)
    if HOSTAGE_RE.match(p):
        return (HOSTAGE, 'family') if HOSTAGE in have else (None, None)
    mt = AGENT_RE.match(p)
    if not mt: return None, None
    agent, team = mt.group(1), mt.group(2)
    fam = family_of(agent)
    for new, how in (('characters/models/%s/%s.vmdl' % (fam, agent), 'same'), ('characters/models/%s/%s.vmdl' % (fam, fam), 'family')):
        if new in have: return new, how
    var = sorted(x for x in have if x.startswith('characters/models/%s/%s_' % (fam, fam)))
    if var: return var[0], 'variant'
    new = TEAM_DEFAULT[team]
    return (new, 'team') if new in have else (None, None)


def run(m, c):
    have = cs2_models(getattr(c, 'cs2v', None))
    if not have:
        c.todo.append('stockmodels: CS2 pak01 not staged (<root>/vpk/cs2_pak01_dir.vpk), no character models repointed'); return
    done = {}; how_of = {}
    for e in m.entities():
        md = (m.P(e, 'model', '') or '').replace('\\', '/')
        if not md: continue
        key = md.lower()
        if have and key in have: continue                          # already a CS2 stock path
        new, how = remap(key, have)
        if not new: continue
        m.setp(e, 'model', new); done[md] = done.get(md, 0) + 1; how_of[md] = (new, how)
    if not done: return
    swap = {k.encode(): v[0].encode() for k, v in how_of.items()}
    swap.update({k.lower().encode(): v[0].encode() for k, v in how_of.items()})
    targets = ([m.doc.prefix[0]] if getattr(m, 'doc', None) is not None and m.doc.prefix else []) + [el['attrs'] for el in m.E if el['type'] == b'$prefix_element$']
    for attrs in targets:                                          # Hammer's asset list: the build's asset pre-compile reads it
        for pa in attrs:
            if pa[0] == b'map_asset_references':
                new = []
                for x in pa[2]:
                    y = swap.get(x, swap.get(x.lower(), x))
                    if y not in new: new.append(y)
                pa[2] = new
    c.log.append('stockmodels: %d props on CS:GO stock character models -> CS2 stock models (%s)' %
                 (sum(done.values()), ', '.join('%s x%d -> %s%s' % (k, v, how_of[k][0], '' if how_of[k][1] == 'same' else ' (%s)' % how_of[k][1])
                                                for k, v in sorted(done.items()))))
    sub = sorted(k for k in done if how_of[k][1] in ('variant', 'team'))
    if sub: c.todo.append('stockmodels: CS2 has no such agent, a different one stands in: %s' % ', '.join('%s -> %s' % (k, how_of[k][0]) for k in sub))
    if any(AGENT_RE.match(k.lower()) or HOSTAGE_RE.match(k.lower()) for k in done):
        c.todo.append('stockmodels: repointed agent / hostage props show CS2\'s model in its default pose (no CS:GO sequences); check size, pose and any DefaultAnim / SetAnimation input')


def main(argv=None):
    """python stockmodels.py <map.vmap> <cs2_pak01_dir.vpk> [<out.vmap>]: report (and with <out> write) the repoint"""
    import argparse, vpk, vmapedit as V
    ap = argparse.ArgumentParser(description='CS:GO chicken / hostage / agent props -> CS2 stock models')
    ap.add_argument('vmap'); ap.add_argument('cs2vpk'); ap.add_argument('out', nargs='?')
    a = ap.parse_args(argv)
    m = V.Map(a.vmap)
    class C: pass
    c = C(); c.log = []; c.todo = []; c.cs2v = vpk.VPK(a.cs2vpk)
    run(m, c)
    for l in c.log: print(l)
    for l in c.todo: print('TO CHECK:', l)
    if a.out and c.log: print('wrote', a.out, m.save(a.out), 'bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
