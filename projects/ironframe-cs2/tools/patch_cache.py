"""Adds cache props for every model the script may SetModel to that the map doesn't have yet, in the generator's cache room, plus the
particle pool entities it lacks (info_particle_system ifr_pfx_<kind>_NN: the aura flare pools on a map the generator made before
they existed) and the mailbox fallbacks, and nothing else. CS2 shows an ERROR model or nothing for a model the map never loaded.
What "every model" is comes from tools/cache_check.py (wanted_models: out/addon/_gen models.json frames / weapons / fx, auras.json,
objectives.json, the null model), so the patch and the check can't disagree; run the check on the result.
usage: python -I tools/patch_cache.py <the map as last saved in Hammer .vmap> <out .vmap> [addon out dir = out/addon] [--gen DIR = out/addon/_gen]
Close Hammer, back up the map, run, then copy the output over the map. Re-runnable: the patch lives in its own vis group
(ifr_cache_patch), which a re-run replaces; props the map already has outside that group are never doubled.
Patch props sit on a 64 u grid between the generator's 96 u one (585 spots); the room is sealed, overlap doesn't matter.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import vmapgen as G
import cache_check as CC
from arenas.common import CACHE, CACHE_W, CACHE_D, PREFIX


def main(src, out, addon='out/addon', gen=None):
    gen = gen or os.path.join(PROJ, 'out', 'addon', '_gen')
    models = list(CC.wanted_models(gen))
    pools = CC.wanted_pools(gen)
    grp = '%s_cache_patch' % PREFIX
    d = G.open_map(src, addon)
    cx, cy, cz = CACHE
    size = (CACHE_W - 128, CACHE_D - 640)
    have = {G.props_of(c).get('model') for c in G.entities(d) if G.props_of(c).get('classname') != 'prop_static' and c.get('customVisGroup', '') != grp}
    todo = [m for m in models if m not in have]
    try:
        n = G.cache_room(d, todo, (cx, cy - 256, cz), size=size, step=(64, 64), prefix='%s_cache_' % PREFIX, group=grp, only_missing=True)
    except AssertionError as e:
        sys.exit('patch_cache: the cache room is full (%s): %d models to add. Enlarge CACHE_W / CACHE_D in tools/arenas/common.py.' % (e, len(todo)))
    have_p = G._existing(d, 'info_particle_system', 'targetname', grp)
    k = 0
    for kind, (count, effect) in sorted(pools.items()):
        for tn in CC.pool_names(kind, count):
            if tn in have_p: continue
            G.ent('info_particle_system', (cx - CACHE_W / 2 + 96 + (k % 30) * 96, cy + CACHE_D / 2 - 140 - (k // 30) * 48, cz + 520), group=grp,
                  targetname=tn, effect_name=effect, start_active='0')
            k += 1
    # mailbox origin fallback (MailboxMode "origin"): ifr_mail_NN_0..3 per slot, Teleported by the plugin. The 10 Nov 2026 server
    # sim read ifr_mail_00 back unrenamed after AddOutput targetname, so the name mode looks refused in CS2.
    have_t = G._existing(d, 'info_target', 'targetname', grp)
    nm = 0
    for s_ in range(64):
        for q in range(4):
            tn = '%s_mail_%02d_%d' % (PREFIX, s_, q)
            if tn in have_t: continue
            G.ent('info_target', (cx - CACHE_W / 2 + 128 + (s_ % 16) * 64 + q * 12, cy + CACHE_D / 2 - 200 - (s_ // 16) * 64, cz + 360), group=grp,
                  targetname=tn)
            nm += 1
    G.finish(d, out, group=grp, first_run_cleanup=False)   # attaches the new props; replaces this group's earlier ones (re-runnable)
    print('patch_cache: %d models wanted, %s added, %d particle pool entities, %d fallback mailboxes -> %s' % (len(models), n, k, nm, out))


if __name__ == '__main__':
    args = sys.argv[1:]; gen = None
    if '--gen' in args: i = args.index('--gen'); gen = args[i + 1]; del args[i:i + 2]
    if len(args) < 2: sys.exit(__doc__)
    main(*args[:3], gen=gen)
