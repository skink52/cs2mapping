"""Gentle fog (short front revision step 3, 17 Nov 2026), as one guarded delta patch. Reads the input map (never writes it); writes the
patched copy, the guard's target list and a report.

The user (17 Nov 2026): "reinstate a gentle fog, that's atmospheric but still allows for the infantry to see from one side of the trench
to the other". The user's 29 Oct save already had no env_volumetric_fog_controller (only env_cubemap_fog), so the visible mist was gone.

usage: python tools/patch_fog_2.py [--in V] [--out V] [--targets T] [--report R] [--no-guard]
  defaults: --in out/step9/chain/7_nav.vmap (the last chain stage), --out out/short_front/step3/mg_trenchwarfare_fog.vmap,
            --targets / --report beside the output
  then (here unless --no-guard): python tools/patch_guard.py <in> <out> <targets> --strict

Changes (by class, so it runs on any stage of the chain, and on the short-front map later):
  env_cubemap_fog (exactly one): CUBEMAP below. The far fire trench (3,282 u, fire step to fire step) goes from ~29 % fog to ~12 %
      (opacity = max * ((d - start) / (end - start)) ** exponent, the formula REVIEW_WORLD_3 checked against the old values).
  env_volumetric_fog_controller tw_vfog: added when there is none (VFOG below: make_map.py's key set, strength 0.35 against the old
      0.8, drawn to 2,400 u), or its keys set when one exists. Vis group tw_gen.
  The prefix's per-class entity counts follow.
Level: "simulated" (patch_guard --strict); how thick 0.35 looks is only known in CS2 (docs/TESTING.md L5). AI-generated (Claude) for skink52.
"""
import argparse, json, os, subprocess, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
STEP = os.path.join(OUT, 'short_front', 'step3')
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402

GROUP = 'tw_gen'
CUBEMAP = dict(cubemapfogstartdistance='400', cubemapfogenddistance='9000', cubemapfogfalloffexponent='1.6', cubemapfogmaxopacity='0.7')
# make_map.py's tw_vfog keys (tw13-tw32), thinner and drawn further: patches of mist that drift (noise), lit by the sun
VFOG = [('targetname', 'tw_vfog'), ('IsMaster', '1'), ('FogStrength', '0.35'), ('TintColor', '205 210 215'), ('DrawDistance', '2400'),
        ('FadeInStart', '60'), ('FadeInEnd', '400'), ('FadeSpeed', '2'), ('IndirectEnabled', '1'), ('IndirectStrength', '0.8'),
        ('IndirectVoxelDim', '256'), ('NoiseSpeed', '0.12'), ('NoiseStrength', '0.6'), ('NoiseScale', '.003 .003 .008'),
        ('volume_depth_override', '0'), ('volume_first_slice_thickness', '0')]
VFOG_AT = (192.0, 0.0, 2000.0)
SPAN = 3282.0                 # fire step to fire step (layout XF 1641 a side)


def opacity(p, d):
    s, e, x, mx = (float(p[k]) for k in ('cubemapfogstartdistance', 'cubemapfogenddistance', 'cubemapfogfalloffexponent', 'cubemapfogmaxopacity'))
    t = min(1.0, max(0.0, (d - s) / max(1.0, e - s)))
    return mx * t ** x


def main(argv=None):
    ap = argparse.ArgumentParser(description='gentle fog patch (short front step 3)')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'step9', 'chain', '7_nav.vmap'))
    ap.add_argument('--out', default=os.path.join(STEP, 'mg_trenchwarfare_fog.vmap'))
    ap.add_argument('--targets'); ap.add_argument('--report')
    ap.add_argument('--no-guard', action='store_true')
    a = ap.parse_args(argv)
    outp = os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(os.path.abspath(a.inp)):
        sys.exit('patch_fog_2: --out must be under %s and not the input' % OUT)
    tp = a.targets or os.path.splitext(outp)[0] + '.targets.json'
    rp = a.report or os.path.splitext(outp)[0] + '.report.json'
    t0 = time.time()
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw); m.path = a.inp
    V.random.seed('patch_fog_2:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw)))
    T = dict(input=os.path.abspath(a.inp), input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=[], root=False)
    rep = dict(tool='tools/patch_fog_2.py')
    cm = m.by_class('env_cubemap_fog')
    if len(cm) != 1: sys.exit('patch_fog_2: TARGET MISMATCH, nothing written: %d env_cubemap_fog (want 1)' % len(cm))
    c = cm[0]
    before = {k: m.P(c, k, '') for k in CUBEMAP}
    rep['cubemap_before'] = dict(before, at_span=round(opacity(before, SPAN), 3), at_6000=round(opacity(before, 6000), 3))
    changed = []
    for k, v in CUBEMAP.items():
        if m.P(c, k, '') != v: m.setp(c, k, v); changed.append('kv:' + k)
    if changed: T['modify'][str(m.g(c, b'nodeID'))] = dict(i=c, fields=changed, why='gentler distance fog: the far fire trench stays readable')
    rep['cubemap_after'] = dict(CUBEMAP, at_1600=round(opacity(CUBEMAP, 1600), 3), at_span=round(opacity(CUBEMAP, SPAN), 3), at_6000=round(opacity(CUBEMAP, 6000), 3))
    vf = m.by_class('env_volumetric_fog_controller')
    if len(vf) > 1: sys.exit('patch_fog_2: TARGET MISMATCH, nothing written: %d volumetric fog controllers' % len(vf))
    if vf:
        e = vf[0]; fields = []
        for k, v in VFOG:
            if m.P(e, k, None) != v: m.setp(e, k, v); fields.append('kv:' + k)
        if fields: T['modify'][str(m.g(e, b'nodeID'))] = dict(i=e, fields=fields, why='gentle volumetric fog values')
        rep['volumetric'] = 'set on the existing controller (%d keys)' % len(fields)
    else:
        e = m.new_entity('env_volumetric_fog_controller', VFOG_AT, dict(VFOG))
        dmx.set_(m.E[e], b'customVisGroup', dmx.T_STR, GROUP.encode())
        T['add'].append(dict(type='CMapEntity', **{'class': 'env_volumetric_fog_controller'}, name='tw_vfog', why='gentle volumetric mist (none in the user save)'))
        counts = {}
        for x in m.entities(): counts[m.cls(x)] = counts.get(m.cls(x), 0) + 1
        for attrs in m.doc.prefix:
            pre = {x[0]: x for x in attrs}
            if b'map_subasset_reference_names' in pre:
                names = sorted(counts)
                pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
                pre[b'map_subasset_reference_names'][2] = [nm.encode() for nm in names]
                pre[b'map_subasset_reference_counts'][2] = [counts[nm] for nm in names]
                T['prefix'] += ['map_subasset_reference_counts', 'map_subasset_reference_names', 'map_subasset_reference_types']
        rep['volumetric'] = 'added tw_vfog'
    rep['volumetric_keys'] = dict(VFOG)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    n = m.save(outp)
    T['output'] = outp
    json.dump(T, open(tp, 'w'), indent=1)
    json.dump(rep, open(rp, 'w'), indent=1)
    print('patched map: %s (%d bytes); cubemap fog at the far trench %.0f %% -> %.0f %%; %s; %.1f s'
          % (outp, n, 100 * rep['cubemap_before']['at_span'], 100 * rep['cubemap_after']['at_span'], rep['volumetric'], time.time() - t0))
    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'patch_guard.py'), a.inp, outp, tp, '--strict', '--report',
                            os.path.splitext(outp)[0] + '.guard.json'], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode: sys.exit('patch_fog_2: GUARD FAILED (see %s)' % (os.path.splitext(outp)[0] + '.guard.json'))


if __name__ == '__main__':
    main()
