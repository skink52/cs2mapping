"""Sound emitter patch (remaster step 8 follow-up, 12 Nov 2026): the map side of the three sounds that waited for wiring
(docs/SOUNDS.md), as one guarded delta patch. Reads the input map (never writes it); writes the patched copy, the guard's target list,
the emitters for the mock (test/mock.mjs) and the guard report under out/.

usage: python tools/patch_sounds.py [--in V] [--out V] [--targets T] [--no-guard]
  defaults: --in out/mg_trenchwarfare_terrain.vmap, --out out/mg_trenchwarfare_sounds.vmap,
            --targets out/step8/patch_sounds.targets.json
  then (run here unless --no-guard): python tools/patch_guard.py <in> <out> <targets> --strict
Chain: patch_world_1 -> patch_models -> patch_terrain -> patch_sounds -> patch_nav (each takes --in / --out).

Adds (point_soundevent with make_map.py's key set, startOnSpawn 0, vis group tw_gen):
  tw_whistle_attack        tw.whistle_attack (flat: heard everywhere), beside tw_ambience in the briefing room. The script starts it
                           CONFIG.LOBBY_RESPAWN after each round start (75_front tickWhistle).
  tw_plane_dive_1..4       tw.plane_dive (3D 5000), parked beside it. The script lends one to a diving aircraft for the 3 s of the
                           sound (60_air diveSound: SetSourceEntity, StartSound; StopSound when the flight ends). A pool of 4 instead
                           of one per aircraft (10): the fewest map entities; a dive with all 4 busy is silent (CS2 has no script
                           sound call, so some emitter must exist; cs_script-notes "Sounds").
  tw_rain_tin_<tg>_1..3    tw.amb.rain_tin (3D 600 loop) 88 u over each of the 6 dressing-station shelters (models/tw/shelter, the
                           elephant iron; numbered by y like heal_<tg>_N), all inside patch_terrain's rain tiles.
Changes: the relay tw_rain (patch_terrain's rain switch: ent_fire tw_rain FireUser1 / FireUser2) gets OnUser1 -> StartSound and
  OnUser2 -> StopSound to each tw_rain_tin_* (field conns only), so the tin rings exactly while the rain tiles run. The script does
  not touch the rain. The prefix's per-class entity counts (map_subasset_reference_*) follow the new point_soundevents.
Every target is verified before anything is written: one logic_relay tw_rain in tw_gen whose outputs are exactly the 12 tiles' Start /
  Stop; the 6 shelters at the expected positions (within 2 u, tw_gen); one tw_ambience; none of the new names present (a re-run on its
  own output stops: TARGET MISMATCH, nothing written).
Level: "simulated" (patch_guard --strict, check_contract --vmap); nothing compiled or heard.
"""
import argparse, json, os, subprocess, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
STEP = os.path.join(OUT, 'step8')
# the project's tools/ has its own dmx.py; the repo readers need the repo's
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402

GROUP = 'tw_gen'
TOL = 2.0
SHELTER = 'models/tw/shelter/shelter.vmdl'
# the 6 dressing-station shelters (read from the step 7 map, 12 Nov 2026): tag, number (by y, as heal_<tg>_N), origin
SHELTERS = [('t', 1, (-2238.0, -1056.0, -69.9)), ('t', 2, (-2238.0, 576.0, -69.84)), ('t', 3, (-2238.0, 2304.0, -76.17)),
            ('ct', 1, (2238.0, -1056.0, -71.28)), ('ct', 2, (2238.0, 576.0, -72.9)), ('ct', 3, (2238.0, 2304.0, -71.32))]
TIN_UP = 88.0                 # under the shelter roof (check_play T4: >= 72 u headroom at the dressing station)
DIVE_EMITTERS = 4             # = CONFIG.AIR.DIVE.EMITTERS (tools/check_contract.py compares the two)
RAIN_RELAY, RAIN_TILES = 'tw_rain', 12
# make_map.py's point_soundevent keys (the order Hammer writes them)
SND_KEYS = [('startOnSpawn', '0'), ('toLocalPlayer', '0'), ('stopOnNew', '0'), ('saveAndRestore', '0'), ('vscripts', ''), ('parentname', ''),
            ('parentAttachmentName', ''), ('useLocalOffset', '0'), ('local.origin', ''), ('local.angles', ''), ('local.scales', '1 1 1'),
            ('sourceEntityName', ''), ('sourceEntityAttachment', ''), ('entityIndexSelection', '0')]


class Mismatch(Exception): pass


def near(a, b, tol=TOL): return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def plan(m):
    """verify the targets; -> (relay id, shelters {(tg, n): origin}, ambience origin)"""
    ents = m.entities()
    names = {}
    for e in ents:
        nm = m.name(e)
        if nm: names.setdefault(nm, []).append(e)
    new = new_names()
    have = [n for n in new if n in names]
    if have: raise Mismatch('already patched: %s present' % ', '.join(have[:4]))
    rel = names.get(RAIN_RELAY, [])
    if len(rel) != 1 or m.cls(rel[0]) != 'logic_relay': raise Mismatch('want one logic_relay %s, found %s' % (RAIN_RELAY, [m.cls(e) for e in rel]))
    r = rel[0]
    if (m.g(r, b'customVisGroup') or b'').decode() != GROUP: raise Mismatch('%s is not in vis group %s' % (RAIN_RELAY, GROUP))
    conns = [m.conn_tuple(c) for c in m.conns(r)]
    tiles = sorted({c[1] for c in conns})
    if len(tiles) != RAIN_TILES or len(conns) != 2 * RAIN_TILES or any(c[1] not in names or m.cls(names[c[1]][0]) != 'info_particle_system' for c in conns) \
            or sorted((c[0], c[2]) for c in conns) != sorted([('OnUser1', 'Start'), ('OnUser2', 'Stop')] * RAIN_TILES):
        raise Mismatch('%s outputs are not the %d rain tiles\' Start / Stop: %s' % (RAIN_RELAY, RAIN_TILES, conns[:4]))
    found = {}
    for tg, n, o in SHELTERS:
        hit = [e for e in ents if (m.P(e, 'model', '') or '') == SHELTER and near(m.origin(e), o)]
        if len(hit) != 1: raise Mismatch('shelter %s_%d: %d at %s' % (tg, n, len(hit), o))
        if (m.g(hit[0], b'customVisGroup') or b'').decode() != GROUP: raise Mismatch('shelter %s_%d is not in %s' % (tg, n, GROUP))
        found[(tg, n)] = m.origin(hit[0])
    if sum(1 for e in ents if (m.P(e, 'model', '') or '') == SHELTER) != len(SHELTERS): raise Mismatch('shelter count changed')
    amb = names.get('tw_ambience', [])
    if len(amb) != 1 or m.cls(amb[0]) != 'point_soundevent': raise Mismatch('want one point_soundevent tw_ambience')
    return r, found, m.origin(amb[0])


def new_names():
    return (['tw_whistle_attack'] + ['tw_plane_dive_%d' % i for i in range(1, DIVE_EMITTERS + 1)] +
            ['tw_rain_tin_%s_%d' % (tg, n) for tg, n, _ in SHELTERS])


def main(argv=None):
    ap = argparse.ArgumentParser(description='sound emitter patch (step 8 follow-up)')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'mg_trenchwarfare_terrain.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_sounds.vmap'))
    ap.add_argument('--targets', default=os.path.join(STEP, 'patch_sounds.targets.json'))
    ap.add_argument('--no-guard', action='store_true')
    a = ap.parse_args(argv)
    outp = os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(os.path.abspath(a.inp)):
        sys.exit('patch_sounds: --out must be under %s and not the input' % OUT)
    t0 = time.time()
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw); m.path = a.inp
    V.random.seed('patch_sounds:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw)))   # new guids / referenceIDs / randomSeeds (vmapedit's global random) follow from the input: same input, same bytes
    try:
        relay, shelters, amb = plan(m)
    except Mismatch as ex:
        sys.exit('patch_sounds: TARGET MISMATCH, nothing written: %s' % ex)
    T = dict(input=os.path.abspath(a.inp), input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=[], root=False)
    added = []

    def snd(name, sound, o, why):
        e = m.new_entity('point_soundevent', o, dict([('targetname', name), ('soundName', sound)] + SND_KEYS))
        dmx.set_(m.E[e], b'customVisGroup', dmx.T_STR, GROUP.encode())
        T['add'].append(dict(type='CMapEntity', **{'class': 'point_soundevent'}, name=name, why=why))
        added.append(dict(name=name, cls='point_soundevent', origin=[float(v) for v in o], angles=[0.0, 0.0, 0.0], soundName=sound))

    ax, ay, az = amb
    snd('tw_whistle_attack', 'tw.whistle_attack', (ax, ay + 60, az), 'round-start whistle (flat), script StartSound')
    for i in range(1, DIVE_EMITTERS + 1):
        snd('tw_plane_dive_%d' % i, 'tw.plane_dive', (ax + 60 * i, ay + 120, az), 'dive sound pool, lent to a diving aircraft by the script')
    for tg, n, _ in SHELTERS:
        x, y, z = shelters[(tg, n)]
        nm = 'tw_rain_tin_%s_%d' % (tg, n)
        snd(nm, 'tw.amb.rain_tin', (x, y, z + TIN_UP), 'rain on the shelter\'s elephant iron (loop), started / stopped by %s' % RAIN_RELAY)
        m.add_conn(relay, 'OnUser1', nm, 'StartSound')
        m.add_conn(relay, 'OnUser2', nm, 'StopSound')
    T['modify'][str(m.g(relay, b'nodeID'))] = dict(i=relay, fields=['conns'], why='rain relay also starts / stops the 6 tin loops')
    # the prefix's per-class entity counts
    counts = {}
    for e in m.entities(): counts[m.cls(e)] = counts.get(m.cls(e), 0) + 1
    for attrs in m.doc.prefix:
        pre = {x[0]: x for x in attrs}
        if b'map_subasset_reference_names' in pre:
            names = sorted(counts)
            pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
            pre[b'map_subasset_reference_names'][2] = [nm.encode() for nm in names]
            pre[b'map_subasset_reference_counts'][2] = [counts[nm] for nm in names]
            T['prefix'] += ['map_subasset_reference_counts']
    n = m.save(outp)
    T['output'] = outp
    os.makedirs(os.path.dirname(os.path.abspath(a.targets)), exist_ok=True)
    json.dump(T, open(a.targets, 'w'), indent=1)
    # the emitters in test/mock.mjs's entities.json shape: the mock adds them to the restaged deployed map (out/entities.json)
    with open(os.path.join(STEP, 'patch_sounds.entities.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(tool='tools/patch_sounds.py', output=os.path.relpath(outp, PROJ).replace('\\', '/'), relay=RAIN_RELAY, entities=added), f, indent=1)
    print('patched map: %s (%d bytes); %d emitters added, %d outputs on %s; %.1f s' % (outp, n, len(added), 2 * len(SHELTERS), RAIN_RELAY, time.time() - t0))
    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'patch_guard.py'), a.inp, outp, a.targets, '--strict', '--report',
                            os.path.join(STEP, 'patch_sounds.guard.json')], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode: sys.exit('patch_sounds: GUARD FAILED (see out/step8/patch_sounds.guard.json)')


if __name__ == '__main__':
    main()
