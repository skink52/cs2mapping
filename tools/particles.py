"""Stage C step / stage D pass `particles`: info_particle_systems that still name a CS:GO particle system get CS2's particle of that name.

CS:GO's info_particle_system names a system from a .pcf file (`effect_name dust_embers`); CS2 wants a resource path
(`particles/maps/de_dust/dust_embers.vpcf`). Valve's importer can't find them ("WARNING: Failed to find source 2 file for particle
system dust_embers") and leaves the bare name, which the build rejects ("FixupResourceName: Illegal path, missing extension") and
which plays nothing in game. CS2 ships most CS:GO systems under the same name: all 20 that our ports used (8 Nov 2026: 187
entities, 151 of them on mg_antique_course) are in csgo/pak01_dir.vpk, one path each. A name the addon has a particle for wins over
CS2's; a name with several CS2 paths, or none, is left as it is and listed (no guessed stand-ins).
Method from github.com/Ninja-Chris/cs2-slop-porting 2026-11-08g (PARTICLE_PORT, MIT), written fresh for this pipeline.
"""
import os, collections


def stock_index(cs2v):
    """{lower system name: [particles/....vpcf, ...]} from a CS2 VPK (vpk.VPK)"""
    idx = collections.defaultdict(list)
    for p in cs2v.files:
        if p.startswith('particles/') and p.endswith('.vpcf_c'):
            idx[os.path.basename(p)[:-len('.vpcf_c')]].append(p[:-2])
    return idx


def addon_index(c):
    """{lower system name: [particles/....vpcf]} for the addon's own particles (content folder + this run's output)"""
    idx = collections.defaultdict(list)
    rels = set(r for r in c.files if r.startswith('particles/'))
    pd = os.path.join(c.content, 'particles')
    for d, _, fs in os.walk(pd):
        for f in fs:
            rels.add(os.path.relpath(os.path.join(d, f), c.content).replace('\\', '/'))
    for r in rels:
        if r.lower().endswith('.vpcf'):
            idx[os.path.basename(r)[:-5].lower()].append(r)
    return idx


def run(m, c):
    """-> number of entities changed"""
    bare = [e for e in m.by_class('info_particle_system') if _bare(m.P(e, 'effect_name', ''))]
    if not bare: return 0
    if c.cs2v is None or not getattr(c.cs2v, 'files', None):     # not staged, or run_c.py's stub VPK
        c.todo.append('particles: %d info_particle_system name CS:GO particle systems (no CS2 path) and CS2\'s VPK is not staged: run the particles step with <root>/vpk/cs2_pak01_dir.vpk' % len(bare))
        return 0
    stock, own = stock_index(c.cs2v), addon_index(c)
    done, many, none = collections.Counter(), {}, collections.Counter()
    path = {}
    for e in bare:
        ef = m.P(e, 'effect_name', '').strip()
        hits = own.get(ef.lower()) or stock.get(ef.lower(), [])
        if len(hits) == 1:
            m.setp(e, 'effect_name', hits[0]); done[ef] += 1; path[ef] = hits[0]
        elif hits:
            many[ef] = hits
        else:
            none[ef] += 1
    if done:
        c.log.append('particles: %d info_particle_system had a CS:GO particle system name; given CS2\'s particle of that name: %s'
                     % (sum(done.values()), ', '.join('%s x%d -> %s' % (k, n, path[k]) for k, n in sorted(done.items()))))
    if many: c.todo.append('particles: several CS2 particles share these names, left as they are: %s' % '; '.join('%s (%s)' % (k, ', '.join(v[:3])) for k, v in sorted(many.items()))[:800])
    if none: c.todo.append('particles: no CS2 or addon particle of these names (custom .pcf systems; still play nothing): %s' % ', '.join('%s x%d' % kv for kv in sorted(none.items()))[:800])
    return sum(done.values())


def _bare(ef):
    ef = (ef or '').strip()
    return bool(ef) and '/' not in ef and '\\' not in ef and not ef.lower().endswith(('.vpcf', '.vpcf_c'))
