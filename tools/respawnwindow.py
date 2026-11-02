"""Course maps: players who die early respawn, until 5 s before the map's AFK killer switches on.

  python respawnwindow.py <vmap in> <vmap out> [afk target ...] [--lead 5]

A course map's AFK killer is a trigger_hurt / trigger_teleport over the spawns (info_player_terrorist / counterterrorist), StartDisabled,
that something switches on with a delay (logic_auto OnMapSpawn -> afk.Enable 60 s, a start door's OnOpen, a trigger at the spawn).
Players who die on the first obstacles before then sit out the whole round; skink52 wants them back (2 Nov 2026).
The same output that starts the AFK countdown now also triggers a logic_relay `port_respawn_window` (only once, and map entities are made
again every round), which tells `port_servercommand` mp_respawn_on_death_t / _ct 1 at once and 0 when the killer is <lead> seconds away.
Names given on the command line are used as the AFK targets; with none, every disabled hurt / teleport covering a spawn that a >= 15 s
delayed Enable switches on counts. Maps that hand out weapons (shooting arenas, Goldeneye) aren't course maps: don't run it there.
Needs stage C's round setup first (port_servercommand). A rerun replaces the relay's outputs rather than adding a second relay.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, dmx

RELAY = 'port_respawn_window'
KILLERS = ('trigger_hurt', 'trigger_teleport')

def _disabled(m, e): return str(m.P(e, 'StartDisabled', '0')).lower() in ('1', 'true')

def weapons(m):
    """what the map's game_player_equips hand out besides knives (a course map has none, or only a killbox's)"""
    out = set()
    for e in m.by_class('game_player_equip'):
        for a in m.props(e)['attrs']:
            k = a[0].decode() if isinstance(a[0], bytes) else a[0]; v = a[2].decode('utf-8', 'replace') if isinstance(a[2], bytes) else str(a[2])
            w = k if k.startswith('weapon_') else v if k.startswith('weapon') and v.startswith('weapon_') else ''
            if w and 'knife' not in w: out.add(w[7:])
    return sorted(out)

def afk_targets(m):
    """disabled hurts / teleports that cover a spawn point"""
    sp = [m.origin(e) for c in ('info_player_terrorist', 'info_player_counterterrorist') for e in m.by_class(c)]
    out = set()
    for c in KILLERS:
        for e in m.by_class(c):
            if not (_disabled(m, e) and m.name(e)): continue
            try: lo, hi = m.bounds(e)
            except Exception: continue
            if any(all(lo[i] - 8 <= s[i] <= hi[i] + 8 for i in range(3)) for s in sp): out.add(m.name(e).lower())
    return out

def run(m, names=None, lead=5.0):
    """returns (log line, or None when the map has no AFK killer)"""
    want = {n.lower() for n in names} if names else afk_targets(m)
    if not want: return None
    if not any(m.name(e) == 'port_servercommand' for e in m.by_class('point_servercommand')):
        return 'respawn window: no port_servercommand (run round setup first)'
    # every source output that switches an AFK killer on, with its delay: the earliest per source + output wins
    src = {}
    for e, k in m.all_conns():
        u = m.conn_tuple(k)
        if u[1].lower() in want and u[2].lower() == 'enable' and u[4] >= 15 and m.name(e) != RELAY:
            key = (e, u[0])
            if key not in src or u[4] < src[key][0]: src[key] = (u[4], u[5], u[1])
    if not src: return 'respawn window: %s found, but nothing switches it on after a delay' % ', '.join(sorted(want))
    if len({d for d, _, _ in src.values()}) > 1:
        return 'respawn window: AFK killers start at different delays (%s), set it by hand' % ', '.join('%s %gs' % (t, d) for d, _, t in src.values())
    delay = next(iter(src.values()))[0]; off = max(0.0, delay - lead)
    r = next((e for e in m.by_class('logic_relay') if m.name(e) == RELAY), None)
    if r is None:
        e0 = next(iter(src))[0]; o = m.origin(e0)
        r = m.new_entity('logic_relay', [o[0], o[1] + 32, o[2]], {'targetname': RELAY, 'spawnflags': '1', 'StartDisabled': '0'})
    else:
        ca = dmx.geta(m.E[r], b'connectionsData')
        if ca: ca[2][:] = []
    for cv in ('mp_respawn_on_death_t', 'mp_respawn_on_death_ct'):
        m.add_conn(r, 'OnTrigger', 'port_servercommand', 'Command', cv + ' 1', 0.0, -1)
        m.add_conn(r, 'OnTrigger', 'port_servercommand', 'Command', cv + ' 0', off, -1)
    for (e, out), (d, times, t) in src.items():
        if not any(m.conn_tuple(k)[1] == RELAY for k in m.conns(e)): m.add_conn(e, out, RELAY, 'Trigger', '', 0.0, times)
    how = '; '.join('%s(%s).%s' % (m.cls(e), m.name(e) or 'unnamed', out) for e, out in src)
    return 'respawn window: respawning on from %s until %gs later, %gs before %s switches on' % (how, off, lead, ', '.join(sorted({t for _, _, t in src.values()})))

if __name__ == '__main__':
    a = sys.argv[1:]; lead = 5.0
    if '--lead' in a: i = a.index('--lead'); lead = float(a[i + 1]); del a[i:i + 2]
    if len(a) < 2: sys.exit(__doc__)
    m = V.Map(a[0]); msg = run(m, a[2:] or None, lead)
    print(msg or 'respawn window: no AFK killer over the spawns')
    if msg and msg.startswith('respawn window: respawning'): m.save(a[1])
