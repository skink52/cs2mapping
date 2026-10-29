"""Blend a map's water into its 3D skybox water (cs2kz mapping guide, "Infinite water"; skink52's mg_pirates, 29 Oct 2026).

  python3 waterblend.py <main.vmap> <skybox.vmap> <main out> <skybox out> <addon content root> <name> <cs2 pak01_dir.vpk> [fade]

The main map renders over the 3D skybox, so the main map's water has to fade out at its edges to show the skybox water behind it:
- The water material both maps use (a stock csgo_water_fancy one, decompiled from the VPK with vmatc.py, or the addon's own vmat) is
  copied to materials/<name>/<name>_water.vmat with g_vMapUVMin/Max = the main water's XY extent, g_flSkyBoxFadeRange = fade (default 0.1)
  and g_flSkyBoxScale = the sky_camera scale, and to <name>_water_skybox.vmat (same look, no fade) for the skybox map.
- Main-map meshes under the water (the sea bed) would show through the fading water and hide the skybox: they are cut back to the
  inner rectangle that doesn't fade (fade x the water's width / depth from each edge).
- The skybox sea bed is moved down so the water fog hides it, as it does in the deeper main map.
- Skybox light probe volumes whose edges cross the water are grown to cover the whole skybox water (probe edges on water show as seams).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V, vmatc


def is_water(mat): return 'water' in mat or mat.startswith('materials/liquids/')


def meshes(m):
    for n, _ in m.walk():
        if m.type(n) == b'CMapMesh':
            mats = [x.decode() for x in m.g(m.g(n, b'meshData'), b'materials') or []]
            yield n, mats


def positions(m, n):
    for st in m.g(m.g(m.g(n, b'meshData'), b'vertexData'), b'streams'):
        if m.E[st]['name'].startswith(b'position'): return dmx.geta(m.E[st], b'data')


def set_mat(m, n, old, new):
    md = m.E[m.g(n, b'meshData')]
    dmx.set_(md, b'materials', dmx.ARR + dmx.T_STR, [new.encode() if x.decode() == old else x for x in dmx.get(md, b'materials')])


def water_of(m):
    ws = [(n, [x for x in mats if is_water(x)][0]) for n, mats in meshes(m) if any(is_water(x) for x in mats)]
    if not ws: raise SystemExit('no water mesh')
    lo = [min(m.bounds(n)[0][k] for n, _ in ws) for k in range(3)]; hi = [max(m.bounds(n)[1][k] for n, _ in ws) for k in range(3)]
    return ws, lo, hi


def run(main_in, sky_in, main_out, sky_out, content, name, dir_vpk, fade=0.1):
    main, sky = V.Map(main_in), V.Map(sky_in)
    cams = sky.by_class('sky_camera')
    scale = float(sky.P(cams[0], 'scale', '16') or 16) if cams else 16.0
    ws, lo, hi = water_of(main)
    src = ws[0][1]
    own = os.path.join(content, src)
    text = open(own, encoding='utf-8').read() if os.path.exists(own) else vmatc.to_vmat(vmatc.parse(vmatc.read_vpk_file(dir_vpk, src + '_c')), src + '_c')
    if 'csgo_water_fancy' not in text: raise SystemExit('%s is not a csgo_water_fancy material' % src)
    mv = vmatc.set_param(text, 'g_vMapUVMin', '"[%g %g 0.000000 0.000000]"' % (lo[0], lo[1]))
    mv = vmatc.set_param(mv, 'g_vMapUVMax', '"[%g %g 0.000000 0.000000]"' % (hi[0], hi[1]))
    mv = vmatc.set_param(mv, 'g_flSkyBoxFadeRange', '"%.6f"' % fade)
    mv = vmatc.set_param(mv, 'g_flSkyBoxScale', '"%.6f"' % scale)
    sv = vmatc.set_param(mv, 'g_flSkyBoxFadeRange', '"0.000000"')
    sv = vmatc.set_param(sv, 'g_vMapUVMin', '"[-100000 -100000 0.000000 0.000000]"')
    sv = vmatc.set_param(sv, 'g_vMapUVMax', '"[100000 100000 0.000000 0.000000]"')
    mm, sm = 'materials/%s/%s_water.vmat' % (name, name), 'materials/%s/%s_water_skybox.vmat' % (name, name)
    files = {mm: '// main-map water: fades out at its edges (g_vMapUVMin/Max, g_flSkyBoxFadeRange) into the 3D skybox water\n' + mv,
             sm: '// 3D skybox water: same look as %s, no fade\n' % mm + sv}
    log = []
    for n, mats in ws: set_mat(main, n, src, mm)
    # main-map meshes under the water inside the fade band -> cut back to the inner rectangle
    top = hi[2]
    bx, by = fade * (hi[0] - lo[0]), fade * (hi[1] - lo[1])
    ilo, ihi = [lo[0] + bx, lo[1] + by], [hi[0] - bx, hi[1] - by]
    cut = 0
    for n, mats in meshes(main):
        if any(is_water(x) for x in mats) or all(x.startswith('materials/tools/') for x in mats): continue
        b = main.bounds(n)
        if not b or b[1][2] > top + 1 or list(main.g(n, b'angles', [0, 0, 0])) != [0, 0, 0]: continue
        if b[0][0] >= ilo[0] and b[1][0] <= ihi[0] and b[0][1] >= ilo[1] and b[1][1] <= ihi[1]: continue
        if b[1][0] < lo[0] or b[0][0] > hi[0] or b[1][1] < lo[1] or b[0][1] > hi[1]: continue
        o = main.origin(n); a = positions(main, n)
        a[2] = [[min(max(p[0] + o[0], ilo[0]), ihi[0]) - o[0], min(max(p[1] + o[1], ilo[1]), ihi[1]) - o[1], p[2]] for p in a[2]]
        cut += 1
    log.append('main map: water -> %s (fade %.2f of the width from each edge, MapUV %g %g .. %g %g); %d meshes under the water cut back to %g %g .. %g %g'
               % (mm, fade, lo[0], lo[1], hi[0], hi[1], cut, ilo[0], ilo[1], ihi[0], ihi[1]))
    # skybox: water material, sea bed down, probe volumes over the whole water
    sws, slo, shi = water_of(sky)
    for n, mats in sws:
        for x in mats:
            if is_water(x): set_mat(sky, n, x, sm)
    sz = shi[2]; depth = 256.0 / scale * 4                     # sea bed at least 1024 world units down
    moved = 0
    for n, mats in meshes(sky):
        if any(is_water(x) for x in mats): continue
        b = sky.bounds(n)
        if not b or b[1][2] > sz + 0.5 or b[1][2] < sz - depth: continue
        if b[1][0] < slo[0] or b[0][0] > shi[0] or b[1][1] < slo[1] or b[0][1] > shi[1]: continue
        dz = (sz - depth) - b[1][2]
        a = positions(sky, n); a[2] = [[p[0], p[1], p[2] + dz] for p in a[2]]
        moved += 1
    grown = 0
    for e in sky.by_class('env_combined_light_probe_volume'):
        o = sky.origin(e)
        mn = [float(x) for x in (sky.P(e, 'box_mins', '-64 -64 -64') or '').split()]; mx = [float(x) for x in (sky.P(e, 'box_maxs', '64 64 64') or '').split()]
        wl = [o[k] + mn[k] for k in range(3)]; wh = [o[k] + mx[k] for k in range(3)]
        if not (wl[2] <= sz <= wh[2]): continue
        if wl[0] <= slo[0] - 8 and wh[0] >= shi[0] + 8 and wl[1] <= slo[1] - 8 and wh[1] >= shi[1] + 8: continue
        nl = [min(wl[0], slo[0] - 64), min(wl[1], slo[1] - 64), min(wl[2], sz - depth - 16)]
        nh = [max(wh[0], shi[0] + 64), max(wh[1], shi[1] + 64), wh[2]]
        sky.setp(e, 'box_mins', '%g %g %g' % tuple(nl[k] - o[k] for k in range(3)))
        sky.setp(e, 'box_maxs', '%g %g %g' % tuple(nh[k] - o[k] for k in range(3)))
        grown += 1
    log.append('skybox: water -> %s; %d sea-bed meshes moved to %g below the water (%g world units); %d light probe volumes grown over the water'
               % (sm, moved, depth, depth * scale, grown))
    main.prune(); sky.prune(); main.save(main_out); sky.save(sky_out)
    return files, log


if __name__ == '__main__':
    a = sys.argv[1:]
    files, log = run(a[0], a[1], a[2], a[3], a[4], a[5], a[6], float(a[7]) if len(a) > 7 else 0.1)
    for rel, t in files.items():
        p = os.path.join(os.path.dirname(os.path.abspath(a[2])), '..', rel)
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w', encoding='utf-8').write(t); print('wrote', os.path.normpath(p))
    print('\n'.join(log))
