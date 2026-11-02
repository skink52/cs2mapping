"""prop_physics_respawnable -> prop_physics + point_template + env_entity_maker, with no script.

  python respawnable.py <vmap in> <vmap out>

CS:GO's prop_physics_respawnable is a prop_physics that comes back at its spawn point RespawnTime seconds (default 60) after it is broken, and
waits until nothing stands in that spot. The importer keeps the class, but CS2 has no such entity (Hammer reports an error, the game doesn't spawn it).
Each one becomes:
  prop_physics <name>                     same model, keys and outputs; RespawnTime removed; OnBreak -> <name>_respawn ForceSpawn after RespawnTime
  point_template <name>_tpl               Template01 <name>, at the prop's spot; spawnflags 1 (keep the original) + 2 (keep its name, so the copy's own
                                          OnBreak still reaches the maker)
  env_entity_maker <name>_respawn         EntityTemplate <name>_tpl, at the same spot; spawnflags 8 (only if there's room); OnEntityFailedSpawn ->
                                          itself ForceSpawn after 1 s, which is CS:GO's "wait until the spot is clear". (CS2's point_template has
                                          no failed-spawn output, so the maker does the spawning.)
A prop that can't break never fires OnBreak, so it is an ordinary physics prop, as it was in CS:GO.
Props without a name, or sharing one that nothing else targets, get a unique name first. Re-runnable: a converted map has no respawnables left.
"""
import collections, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V

def run(m):
    props = m.by_class('prop_physics_respawnable')
    if not props: return 'respawnable: none'
    names = collections.Counter(m.name(e) for e in m.entities())
    targeted = {str(m.conn_tuple(c)[1]).lower() for e in m.entities() for c in m.conns(e)}
    renamed = shared = 0
    for k, e in enumerate(props):
        name = m.name(e)
        if not name or names[name] > 1:
            if name and name.lower() in targeted: shared += 1   # its I/O needs the name, so the template copy keeps it
            else:
                name = '%s_resp%d' % (name or 'port_prop', k); m.setp(e, 'targetname', name); renamed += 1
        delay = float(m.P(e, 'RespawnTime', '60') or 60)
        m.delp(e, 'RespawnTime')
        m.setp(e, 'classname', 'prop_physics')
        tpl, maker = name + '_tpl', name + '_respawn'
        m.new_entity('point_template', m.origin(e), {'targetname': tpl, 'Template01': name, 'spawnflags': '3'})
        mk = m.new_entity('env_entity_maker', m.origin(e), {'targetname': maker, 'EntityTemplate': tpl, 'spawnflags': '8'})
        m.add_conn(e, 'OnBreak', maker, 'ForceSpawn', '', delay, -1)
        m.add_conn(mk, 'OnEntityFailedSpawn', maker, 'ForceSpawn', '', 1.0, -1)
    return 'respawnable: %d prop_physics_respawnable -> prop_physics + point_template / env_entity_maker respawn (%d renamed to be unique%s)' % (
        len(props), renamed, ', %d keep a shared name because I/O targets it: their template respawns every prop with that name' % shared if shared else '')

if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    mp = V.Map(sys.argv[1]); print(run(mp)); mp.save(sys.argv[2])
