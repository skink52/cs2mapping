"""Model swap patch (remaster step 6): applies tools/tw_models.py SWAPS to the map as a guarded delta patch, and writes the step 6
deploy list. Reads the input map (never writes it); writes the patched copy, the guard's target list, the guard report and
out/step6/deploy_files.txt.

usage: python tools/patch_models.py [--in out/mg_trenchwarfare_patched.vmap] [--out out/mg_trenchwarfare_models.vmap] [--stage out/addon]
                                    [--no-guard]
  then (run here unless --no-guard): python tools/patch_guard.py <in> <out> out/step6/patch_models.targets.json --strict

Rules:
- Only tw_gen instances of a slot model are swapped (the model key, plus the SWAPS fix-ups: yaw added, z offset, uniform scale). Instances
  in tw_user or with no vis group are the user's: listed (out/step6/user_owned.txt), never touched.
- Every instance count is checked against EXPECT before anything is written (a Hammer save that moved things makes the patch stop).
- A swap to a dynamic-archetype slot needs a model with model_archetype "" (checked in the staged vmdl); static slots need
  static_prop_model.
- The prefix map_asset_references gets the new models (and loses a replaced model no entity uses any more).
Level: "simulated" (guard + check_world + check_play offline); nothing compiled.
"""
import argparse, json, os, re, subprocess, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
sys.path.insert(0, HERE)
import tw_models as TM    # noqa: E402  (puts create/ first and drops tools/ from sys.path again)
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402

# slot model -> tw_gen instances expected in the input (read from the step 5 map, 12 Nov 2026)
EXPECT = {'models/tw/ext/gun_75mm/gun_75mm.vmdl': 1}
OURS = ('tw_gen',)

# files staged by step 6 that the deploy needs even when the map does not change for them (LODs, the uniform fix)
LOD_MODELS = ['models/tw/ext/tank_a7v/tank_a7v.vmdl', 'models/tw/ext/gun_75mm/gun_75mm.vmdl', 'models/tw/ext/howitzer_bl8/howitzer_bl8.vmdl',
              'models/tw/ext/plane_dr1/plane_dr1.vmdl', 'models/tw/ext/plane_dr1/plane_dr1_dyn.vmdl',
              'models/tw/ext/plane_spad7/plane_spad7.vmdl', 'models/tw/ext/plane_spad7/plane_spad7_dyn.vmdl']
UNIFORM_FILES = ['models/tw/players/tw_de_a/tw_de_a_body.dmx']


class Mismatch(Exception): pass


def archetype(stage, vmdl):
    for root in (stage, TM.CONTENT):
        p = os.path.join(root, *vmdl.split('/'))
        if os.path.exists(p):
            m = re.search(r'model_archetype\s*=\s*"([^"]*)"', open(p, encoding='utf-8', errors='ignore').read())
            return m.group(1) if m else None
    return None


def staged_files(stage, vmdl):
    """addon-relative files a staged vmdl needs from the staging tree: itself, its SMDs / DMXs and the materials + textures they name"""
    p = os.path.join(stage, *vmdl.split('/'))
    if not os.path.exists(p): return []
    txt = open(p, encoding='utf-8', errors='ignore').read()
    out = [vmdl]
    for f in re.findall(r'filename\s*=\s*"([^"]+)"', txt) + re.findall(r'to\s*=\s*"([^"]+\.vmat)"', txt):
        f = f.replace('\\', '/')
        if os.path.exists(os.path.join(stage, *f.split('/'))):
            out.append(f)
            if f.endswith('.vmat'):
                for t in re.findall(r'"(materials/[^"]+\.(?:png|tga|jpg))"', open(os.path.join(stage, *f.split('/')), errors='ignore').read()):
                    if os.path.exists(os.path.join(stage, *t.split('/'))): out.append(t)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='model swap patch (step 6)')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'mg_trenchwarfare_patched.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_models.vmap'))
    ap.add_argument('--stage', default=os.path.join(OUT, 'addon'))
    ap.add_argument('--no-guard', action='store_true')
    a = ap.parse_args(argv)
    outp = os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(os.path.abspath(a.inp)):
        sys.exit('patch_models: --out must be under %s and not the input' % OUT)
    t0 = time.time()
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw); m.path = a.inp
    V.random.seed('patch_models:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw)))   # new guids / referenceIDs / randomSeeds (vmapedit's global random) follow from the input: same input, same bytes
    nid = lambda i: m.g(i, b'nodeID')
    T = dict(input=os.path.abspath(a.inp), input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=['map_asset_references'], root=False)
    swaps = TM.swaps_to_apply()
    slot_arch = {s['slot']: s['archetype'] for s in TM.SWAPS.values()}
    todo, user_owned = [], []
    try:
        for e in m.entities():
            mdl = m.P(e, 'model', '') or ''
            if mdl not in swaps: continue
            vg = (m.g(e, b'customVisGroup') or b'').decode()
            if vg in OURS: todo.append(e)
            else: user_owned.append((e, m.cls(e), mdl, [round(v, 1) for v in m.origin(e)], vg or '(none)'))
        for slot in swaps:
            n = sum(1 for e in todo if m.P(e, 'model', '') == slot)
            if n != EXPECT.get(slot, -1): raise Mismatch('%s: %d tw_gen instances, EXPECT says %s' % (slot, n, EXPECT.get(slot)))
            new = swaps[slot][0]
            arch = archetype(a.stage, new)
            want_dyn = slot_arch[slot].startswith('dynamic')
            if arch is None: raise Mismatch('%s: chosen model %s not staged' % (slot, new))
            if want_dyn != (arch in ('', 'animated_model')): raise Mismatch('%s: %s has archetype %r, slot needs %s' % (slot, new, arch, 'dynamic' if want_dyn else 'static'))
    except Mismatch as ex:
        sys.exit('patch_models: TARGET MISMATCH, nothing written: %s' % ex)

    log = []
    for e in todo:
        slot = m.P(e, 'model', ''); new, fix = swaps[slot]
        m.setp(e, 'model', new); fields = ['kv:model']
        if fix.get('yaw'):
            ang = list(m.g(e, b'angles') or [0.0, 0.0, 0.0]); ang[1] = (ang[1] + fix['yaw']) % 360
            dmx.set_(m.E[e], b'angles', dmx.T_V3, ang); fields.append('angles')
        if fix.get('z'):
            o = m.origin(e); dmx.set_(m.E[e], b'origin', dmx.T_V3, [o[0], o[1], o[2] + fix['z']]); fields.append('origin')
        if fix.get('scale'):
            dmx.set_(m.E[e], b'scales', dmx.T_V3, [fix['scale']] * 3); fields.append('scales')
        T['modify'][str(nid(e))] = dict(i=e, fields=fields, why='step 6 swap %s -> %s' % (slot, new))
        log.append('%d %s at %s: %s -> %s %s' % (e, m.cls(e), [round(v, 1) for v in m.origin(e)], slot, new, fix or ''))
    used = {m.P(e, 'model', '') for e in m.entities()}
    for attrs in m.doc.prefix:
        pre = {x[0]: x for x in attrs}
        if b'map_asset_references' in pre:
            ar = pre[b'map_asset_references'][2]
            for slot, (new, fix) in swaps.items():
                if new.encode() not in ar: ar.append(new.encode())
                if slot not in used and slot.encode() in ar: ar.remove(slot.encode())
    n = m.save(outp)
    os.makedirs(os.path.join(OUT, 'step6'), exist_ok=True)
    tp = os.path.join(OUT, 'step6', 'patch_models.targets.json')
    T['output'] = outp
    json.dump(T, open(tp, 'w'), indent=1)
    for l in log: print('  ' + l)
    with open(os.path.join(OUT, 'step6', 'user_owned.txt'), 'w', newline='\n') as f:
        f.write('# instances of swapped slot models that belong to the user (tw_user / no vis group): NOT swapped, for the user to decide\n')
        for u in user_owned: f.write('%d %s %s at %s vis group %s\n' % u)
    print('patched map: %s (%d bytes); %d swaps; %d user-owned instances listed; %.1f s' % (outp, n, len(todo), len(user_owned), time.time() - t0))

    # ---- deploy list: map, the swapped-in models, the LOD rewrites, the uniform fix
    dep = ['maps/mg_trenchwarfare.vmap   <- %s' % os.path.relpath(outp, PROJ).replace('\\', '/')]
    files = []
    for slot, (new, fix) in swaps.items(): files += staged_files(a.stage, new)
    for v in LOD_MODELS: files += staged_files(a.stage, v)
    files += [f for f in UNIFORM_FILES if os.path.exists(os.path.join(a.stage, *f.split('/')))]
    seen = set(); files = [f for f in files if not (f in seen or seen.add(f))]
    open(os.path.join(OUT, 'step6', 'deploy_files.txt'), 'w', newline='\n').write(
        '# remaster step 6: files to copy into content\\csgo_addons\\mg_trenchwarfare\\ (addon-relative), from out/addon unless noted.\n'
        '# Builds on step 5: deploy out/step5/deploy_files.txt first (this map already contains the step 5 patch).\n'
        '# Back up the vmap, close Hammer and cs2 -tools, then compile the models (none is compiled yet); tw_de_a.vmdl must be recompiled\n'
        '# for its new body DMX (a player model that fails to load is what gave the giant first-person weapons).\n'
        + '\n'.join(dep + files) + '\n')
    print('deploy list: out/step6/deploy_files.txt (%d files + map)' % len(files))
    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'patch_guard.py'), a.inp, outp, tp, '--strict', '--report',
                            os.path.join(OUT, 'step6', 'guard_models.json')], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode: sys.exit('patch_models: GUARD FAILED (see out/step6/guard_models.json)')


if __name__ == '__main__':
    main()
