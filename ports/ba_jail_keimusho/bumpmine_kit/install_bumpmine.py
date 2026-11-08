"""Add the bump mine entities to a CS2 Hammer map (.vmap) without opening Hammer, and wire them to your buttons/triggers.

Close Hammer first (it keeps the open map in memory and overwrites the file on its next save). A backup is written next to the map.
Needs Python 3 only (lib/ holds the .vmap reader/writer).

  python install_bumpmine.py <map.vmap> --at X Y Z [options]

  --at X Y Z              where the pool goes: script, HUD, 8 parked mine props (invisible) and their 16 sound entities.
                          Must be INSIDE the playable world (e.g. under the arena floor in a sealed room or just inside a wall gap),
                          not out in the void.
  --give NAME[:OUTPUT]    entity (button/trigger) that hands the activating player CHARGES bump mines. OUTPUT default OnPressed
                          (use OnStartTouch for a trigger). Repeatable.
  --start NAME[:OUTPUT[:DELAY]]  entity that turns the game on (bump_on). Repeatable. Skip it if bumpmine.js has ALWAYS_ON = true.
  --stop NAME[:OUTPUT[:DELAY]]   entity that turns it off (bump_off). Repeatable.
  --strip                 also add game_player_equip "bumpmine_equip" (strip all weapons + give a decoy) fired by each --give,
                          so players hold nothing but bump mines (keimusho's behaviour). Without it the script only gives the decoy.
  --remove                take out everything this script added (entities and the outputs pointing at them), then stop.
  --dry-run               do everything but write nothing.

Example: python install_bumpmine.py C:/.../content/csgo_addons/my_addon/maps/my_map.vmap --at -2144 -4544 -73 \\
             --give bumpbutton --start bump_start_button --stop bump_stop_button
"""
import argparse, os, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
import dmx, vmapedit as V  # noqa: E402

PREFAB = os.path.join(HERE, 'prefab', 'bumpmine_prefab.vmap')
OURS = {'bumpscript', 'bumphud', 'bumpmine_equip'} | {'bumpmine_%d%s' % (i, s) for i in range(1, 9) for s in ('', '_land', '_det')}
ASSETS = [b'maps/scripts/bumpmine.vjs', b'models/weapons/w_eq_bumpmine_dropped.vmdl', b'panorama/layout/custom_game/bumpmine_hud.vxml']
SOUNDS = [b'bumpmine.land', b'bumpmine.detonate']


def spec(s, default_out):
    p = s.split(':')
    return p[0], (p[1] if len(p) > 1 and p[1] else default_out), (float(p[2]) if len(p) > 2 else 0.0)


def find(m, name):
    return [e for e in m.entities() if m.name(e) == name]


def remove(m):
    n = 0
    for e in m.entities():
        if m.name(e) in OURS:
            m.remove_node(e); n += 1
    c = 0
    for e in m.entities():
        a = dmx.geta(m.E[e], b'connectionsData')
        if not a: continue
        keep = [x for x in a[2] if dmx.get(m.E[x], b'targetName', b'').decode() not in ('bumpscript', 'bumpmine_equip')]
        c += len(a[2]) - len(keep); a[2] = keep
    return n, c


def prefix_refs(m, add):
    """keep the map's asset list in step (Hammer rewrites it on save anyway)"""
    if not m.doc.prefix: return
    P = {pa[0]: pa for pa in m.doc.prefix[0]}
    if b'map_asset_references' in P:
        refs = P[b'map_asset_references'][2]
        for a in ASSETS:
            if add and a not in refs: refs.append(a)
            if not add and a in refs: refs.remove(a)
    t, n = P.get(b'map_subasset_reference_types'), P.get(b'map_subasset_reference_names')
    c = P.get(b'map_subasset_reference_counts')
    if t and n and c and len(t[2]) == len(n[2]) == len(c[2]):
        for snd in SOUNDS:
            idx = [i for i in range(len(n[2])) if n[2][i] == snd and t[2][i] == b'soundevent']
            if add and not idx: t[2].append(b'soundevent'); n[2].append(snd); c[2].append(8)
            if not add:
                for i in reversed(idx): del t[2][i]; del n[2][i]; del c[2][i]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('vmap')
    ap.add_argument('--at', nargs=3, type=float)
    ap.add_argument('--give', action='append', default=[])
    ap.add_argument('--start', action='append', default=[])
    ap.add_argument('--stop', action='append', default=[])
    ap.add_argument('--strip', action='store_true')
    ap.add_argument('--remove', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    m = V.Map(a.vmap)
    log = []
    if a.remove:
        n, c = remove(m); prefix_refs(m, False)
        log.append('removed %d bump mine entities and %d outputs pointing at bumpscript/bumpmine_equip' % (n, c))
    else:
        if a.at is None: sys.exit('--at X Y Z is required (where the pool goes, inside the playable world)')
        have = sorted(set(m.name(e) for e in m.entities()) & OURS)
        if have: sys.exit('the map already has %s - run with --remove first to reinstall' % ', '.join(have))
        missing = [spec(s, '')[0] for s in a.give + a.start + a.stop if not find(m, spec(s, '')[0])]
        if missing: sys.exit('no entity named %s in the map (give the targetname of your button/trigger)' % ', '.join(missing))
        if not a.give: log.append('WARNING: no --give: nothing hands out bump mines yet (fire bumpscript RunScriptInput bump_give with a player as activator)')

        pm = V.Map(PREFAB)
        memo, nid, n = {}, [m.next_node_id()], 0
        for ch in pm.children(pm.world):
            if pm.type(ch) != b'CMapEntity': continue
            if pm.name(ch) == 'bumpmine_equip' and not a.strip: continue
            j = m.import_subtree(pm, ch, memo, nid)
            o = m.g(j, b'origin', [0, 0, 0])
            dmx.set_(m.E[j], b'origin', dmx.T_V3, [o[0] + a.at[0], o[1] + a.at[1], o[2] + a.at[2]])
            dmx.geta(m.E[m.world], b'children')[2].append(j); n += 1
        log.append('added %d entities at %s (bumpscript, bumphud, bumpmine_1..8 + _land/_det sounds%s)' % (n, a.at, ', bumpmine_equip' if a.strip else ''))

        for s in a.give:
            name, out, d = spec(s, 'OnPressed')
            for e in find(m, name):
                if a.strip: m.add_conn(e, out, 'bumpmine_equip', 'TriggerForActivatedPlayer', '', d)
                m.add_conn(e, out, 'bumpscript', 'RunScriptInput', 'bump_give', d + 0.05)
            log.append('give: %d x "%s" %s -> bumpscript bump_give%s' % (len(find(m, name)), name, out, ' (+ bumpmine_equip strip)' if a.strip else ''))
        for lst, inp in ((a.start, 'bump_on'), (a.stop, 'bump_off')):
            for s in lst:
                name, out, d = spec(s, 'OnPressed')
                for e in find(m, name): m.add_conn(e, out, 'bumpscript', 'RunScriptInput', inp, d)
                log.append('%s: %d x "%s" %s (delay %g) -> bumpscript %s' % (inp, len(find(m, name)), name, out, d, inp))
        prefix_refs(m, True)

    out = m.dumps()
    V.Map(data=out)  # re-read check
    if a.dry_run:
        log.append('dry run: nothing written')
    else:
        bak = a.vmap + '.bak_bumpmine_' + time.strftime('%Y%m%d_%H%M%S')
        shutil.copy2(a.vmap, bak)
        open(a.vmap, 'wb').write(out)
        log.append('saved %s (%d bytes); backup %s' % (a.vmap, len(out), bak))
    print('\n'.join(log))


if __name__ == '__main__':
    main()
