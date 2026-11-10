"""Lighting presets for original maps: sun + sky + fog + light probes + cubemap + lightmap resolution over the play box, in one call.

  light(box, preset='noon', group='light', sun_angles=None, sky=None)   -> entity nodes + the lightmap-res mesh (vmaplib map open)
  PRESETS: noon, golden_hour, overcast, night, dusk, inferno (warm Italian afternoon), indoor (no sun; probes, cubemap, lightmapres only)
  lamp(origin, kind='omni', color=(255, 220, 180), brightness=1.0, range_=512, name='')  one light_omni2 (kind 'spot': with a cone)

Sun angles are [pitch, yaw, 0] (pitch = height above the horizon, as Hammer shows it); skies are stock CS2 materials/skybox/*.vmat.
Fog: env_gradient_fog with a height fade. Probes: env_combined_light_probe_volume over the box (without one players and weapons render
near black); env_cubemap_box over the box; a toolslightmapres box (no "No lightmap resolution volumes" warning).

Ported from lighting.py (lighting_preset, add_light) of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT), the "inferno" look
included as a preset; fresh code on create/primitives.py. Not ported: lighting_build's cubemap bake through the live game, light shafts.
"""
import primitives as P

PRESETS = {
    'noon':        dict(sun=(60, 35), color=(255, 248, 235), bright=2.0, sky='materials/skybox/sky_csgo_cloudy01.vmat', skycolor=(150, 185, 255), skyint=1.0,
                        fog=None),
    'golden_hour': dict(sun=(18, 250), color=(255, 196, 130), bright=2.4, sky='materials/skybox/light_test_sky_sunset_light.vmat', skycolor=(255, 190, 150),
                        skyint=0.8, fog=dict(color='255 200 160', strength=0.35, start=1024, end=8192)),
    'overcast':    dict(sun=(70, 0), color=(220, 225, 235), bright=0.6, sky='materials/skybox/rush_cloudy_01a.vmat', skycolor=(180, 190, 205), skyint=1.6,
                        fog=dict(color='190 195 205', strength=0.5, start=512, end=6000)),
    'night':       dict(sun=(45, 120), color=(120, 140, 200), bright=0.25, sky='materials/skybox/sky_black.vmat', skycolor=(40, 50, 80), skyint=0.3,
                        fog=dict(color='20 25 40', strength=0.6, start=256, end=4000)),
    'dusk':        dict(sun=(8, 270), color=(255, 150, 110), bright=1.2, sky='materials/skybox/light_test_sky_sunset_light.vmat', skycolor=(200, 140, 170),
                        skyint=0.7, fog=dict(color='170 120 140', strength=0.45, start=512, end=6000)),
    'inferno':     dict(sun=(50, 300), color=(255, 232, 196), bright=2.2, sky='materials/skybox/cs_italy_s2_skybox_2.vmat', skycolor=(170, 190, 230), skyint=1.1,
                        fog=dict(color='230 215 190', strength=0.2, start=2048, end=12000)),
    'indoor':      dict(sun=None, fog=None),
}


def light(box, preset='noon', group='light', sun_angles=None, sky=None, probes=True, cubemap=True, lightmapres=True, voxel=64):
    if preset not in PRESETS: raise ValueError('preset must be one of %s' % ', '.join(PRESETS))
    pr = PRESETS[preset]
    lo, hi = box
    c = tuple((lo[i] + hi[i]) / 2 for i in range(3)); half = tuple((hi[i] - lo[i]) / 2 for i in range(3))
    top = (c[0], c[1], hi[2] + 64)
    nodes = []
    if pr.get('sun') is not None:
        pitch, yaw = sun_angles or pr['sun']
        nodes.append(P.entity('env_sky', (c[0], c[1], hi[2] + 128), group=group, strict=False, targetname='sky', skyname=sky or pr['sky'],
                              brightnessscale=1.0))
        rgb = lambda t: '%d %d %d' % t
        nodes.append(P.entity('light_environment', top, (pitch, yaw, 0), group=group, strict=False, targetname='sun', color=rgb(pr['color']),
                              brightness=pr['bright'], skycolor=rgb(pr['skycolor']), skyintensity=pr['skyint'], skytexture='sky', castshadows=1,
                              directlight=2))
    if pr.get('fog'):
        f = pr['fog']
        nodes.append(P.entity('env_gradient_fog', (c[0], c[1], hi[2]), group=group, strict=False, targetname='fog', fogcolor=f['color'],
                              fogstrength=f['strength'], fogmaxopacity=0.8, fogstart=f['start'], fogend=f['end'], heightfog=1,
                              fogstartheight=lo[2], fogendheight=hi[2] + 512, fogfalloffexponent=2, fogverticalexponent=1))
    if probes:
        nodes.append(P.entity('env_combined_light_probe_volume', c, group=group, strict=False, targetname='probes',
                              box_mins='%g %g %g' % tuple(-h for h in half), box_maxs='%g %g %g' % half, voxel_size=voxel, flood_fill=1, storage=-1))
    if cubemap:
        nodes.append(P.entity('env_cubemap_box', c, group=group, strict=False, targetname='cubemap',
                              box_mins='%g %g %g' % tuple(-h for h in half), box_maxs='%g %g %g' % half))
    if lightmapres:
        nodes.append(P.add(P.box(lo, hi, 'materials/tools/toolslightmapres.vmat'), group))
    return nodes


def lamp(origin, kind='omni', color=(255, 220, 180), brightness=1.0, range_=512.0, name='', angles=(90, 0, 0), group='light', cone=45.0):
    if kind not in ('omni', 'spot'): raise ValueError('kind: omni or spot')
    cls = 'light_omni2'                  # CS2 has no light_spot: a spot is light_omni2 with a cone (outer / inner angle) and angles
    keys = dict(color='%d %d %d' % tuple(color), brightness=brightness, range=range_, directlight=2, castshadows=1)
    if name: keys['targetname'] = name
    if kind == 'spot': keys.update(outer_angle=cone, inner_angle=cone * 0.6)
    return P.entity(cls, origin, angles if kind == 'spot' else (0, 0, 0), group=group, strict=False, **keys)
