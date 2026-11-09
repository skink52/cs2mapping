"""mg_monsoon map generator.

usage: make_map.py <template or the user's latest .vmap> <out .vmap> <addon content out> [<previous generated .vmap>]

Everything generated goes into vis group mv_gen (replaced on every run); the user's Hammer edits to generated objects are kept as
mv_user (vmapgen.EditKeeper, pass the previous generated output as argv[4]). Each section has its own seeded rng so an added
obstacle never reshuffles another section. Stages:
  1 world: terrain tiles, karst towers, water, sky shell, edge clips, lightmap shells
  2 environment: sun, sky, fog, post, probes, soundscape, 3D skybox reference, vis hints
  3 lobby: briefing room, banner, 32+32 spawns, intro entities, script / HUD / params, effect pools
  4 places: firebase, camp, flags, village, temple, crash site, bridge, paddies dressing, jungle   (mv_places.py)
  5 entities for the script: helicopters, guns, stations, mounts, flags, spawns, caches             (mv_entities.py)
"""
import os, sys, json, math, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmaplib, vmesh, vmapgen as G
from vmaplib import ent
import layout as L
import mv_terrain as TER
from noise import fbm

GROUP = 'mv_gen'
USER_GROUP = 'mv_user'
NAME = 'mg_monsoon'
T0 = time.time()


def stamp(msg):
    print('[%5.1fs] %s' % (time.time() - T0, msg)); sys.stdout.flush()


def main(src, out_vmap, out_addon, prev=None):
    global OUT
    OUT = out_addon
    os.makedirs(os.path.join(OUT, 'maps'), exist_ok=True)
    d = G.open_map(src, OUT)
    keeper = G.EditKeeper(d, prev, GROUP, user_group=USER_GROUP, edits_json=os.path.join(os.path.dirname(os.path.abspath(out_vmap)), '..', 'user_edits.json')) if prev else None
    clone = lambda cls, origin, angles=(0, 0, 0), **k: G.clone(d, cls, origin, angles, GROUP, **k)

    # ---------------------------------------------------------------- 1 world
    stamp('terrain')
    import mv_places as PL
    holes = PL.terrain_holes if hasattr(PL, 'terrain_holes') else None
    T = TER.build_terrain(GROUP, holes_extra=holes)
    stamp('karst'); karst = TER.build_karst(GROUP)
    stamp('water'); TER.build_water(GROUP)
    TER.build_sky_shell(GROUP); TER.build_edge_clips(GROUP)
    stamp('lightmap shells'); TER.build_lmres(GROUP)

    # ---------------------------------------------------------------- 2 environment
    stamp('environment')
    # low, warm sun from the west-south-west through haze; skylight blue-grey
    clone('light_environment', (0, 0, 3000), (28, 205, 0), targetname='mv_sun', color='255 232 196', brightness='1.9', castshadows='1', directlight='3',
          skycolor='170 186 205', skyintensity='1.5', fog='1', fogstrength='0.6', angulardiameter='1.2')
    clone('env_sky', (64, 0, 3000), targetname='sky', skyname='materials/skybox/sky_overcast_01.vmat', tint_color='226 206 180', brightnessscale='1.05')
    clone('env_cubemap_fog', (128, 0, 3000), cubemapfogstartdistance='300', cubemapfogenddistance='9000', cubemapfogfalloffexponent='1.3',
          cubemapheightfog='1', cubemapfogheightstart='-40.0', cubemapfogheightend='1900.0', cubemapfogheightexponent='1.2', cubemapfogmaxopacity='0.88',
          cubemapfogskyentity='sky')
    ent('env_volumetric_fog_controller', (192, 0, 3000), group=GROUP, targetname='mv_vfog', IsMaster='1', FogStrength='0.7', TintColor='214 206 186',
        DrawDistance='1800', FadeInStart='40', FadeInEnd='340', FadeSpeed='2', IndirectEnabled='1', IndirectStrength='1.0', IndirectVoxelDim='256',
        NoiseSpeed='0.12', NoiseStrength='0.6', NoiseScale='.003 .003 .008', volume_depth_override='0', volume_first_slice_thickness='0')
    clone('post_processing_volume', (256, 0, 3000), postprocessing='postprocess/%s.vpost' % NAME, master='1', minexposure='0.55', maxexposure='1.7',
          enableexposure='1', fadetime='1.0', spawnflags='4097')
    # light probes: the valley (64), the bases (48), far slopes (108), the lobby (48); tunnels/bunkers come with the places
    clone('env_combined_light_probe_volume', (0, 0, 300), box_mins='-6500 -3400 -200', box_maxs='6500 3400 1200', voxel_size='64.0', targetname='valley_probe')
    for name, c, r, z0, z1 in (('ct_probe', L.CT_BASE, 1100, L.CT_Z - 420, L.CT_Z + 700), ('t_probe', L.T_BASE, 1000, L.T_Z - 300, L.T_Z + 900)):
        clone('env_combined_light_probe_volume', (c[0], c[1], (z0 + z1) / 2), box_mins='%g %g %g' % (-r, -r, -(z1 - z0) / 2), box_maxs='%g %g %g' % (r, r, (z1 - z0) / 2),
              voxel_size='48.0', targetname=name, indoor_outdoor_level='1')
    for k, (x0, y0, x1, y1) in enumerate(((-7200, 3400, 7200, 6200), (-7200, -6200, 7200, -3400), (-7200, -3400, -6500, 3400), (6500, -3400, 7200, 3400))):
        clone('env_combined_light_probe_volume', ((x0 + x1) / 2, (y0 + y1) / 2, 900), box_mins='%g %g -1100' % (-(x1 - x0) / 2, -(y1 - y0) / 2),
              box_maxs='%g %g 1100' % ((x1 - x0) / 2, (y1 - y0) / 2), voxel_size='108.0', targetname='far_probe_%d' % k, indoor_outdoor_level='-1')
    for kk in karst:   # the tower tops (landable or not) sit above the valley probe
        clone('env_combined_light_probe_volume', (kk['x'], kk['y'], (kk['top'] + kk['z0']) / 2 + 200), box_mins='%g %g %g' % (-kk['r'] - 200, -kk['r'] - 200, -(kk['top'] - kk['z0']) / 2 - 200),
              box_maxs='%g %g %g' % (kk['r'] + 200, kk['r'] + 200, (kk['top'] - kk['z0']) / 2 + 200), voxel_size='96.0', targetname='karst_probe_%d' % int(kk['x']))
    clone('env_soundscape', (0, 0, 300), radius='14000', soundscape='Nothing', enablesoundevent='1', soundevent='mv.amb.valley')
    G.skybox_reference(NAME, GROUP, name='mv_skybox')
    # vis: Lowest over everything, Lower over the open valley, Low only in sealed spaces (lobby; tunnels/bunkers come with the places)
    G.hint((-L.SKY_X, -L.SKY_Y, L.SKY_Z0, L.SKY_X, L.SKY_Y, L.SKY_Z1), 'Lowest', GROUP)
    G.hint((-L.MAP_X, -3400, -120, L.MAP_X, 3400, 900), 'Lower', GROUP)

    # ---------------------------------------------------------------- 3 lobby
    stamp('lobby')
    lobby(d, clone)

    # ---------------------------------------------------------------- 4 places, 5 entities
    stamp('places')
    PL.build(d, GROUP, OUT, T, karst, clone)
    import mv_entities as EN
    stamp('entities')
    EN.build(d, GROUP, OUT, T, clone)

    # ---------------------------------------------------------------- finish
    stamp('finish')
    counts = G.finish(d, out_vmap, group=GROUP, keeper=keeper, drop_classes=G.GENERATOR_OWNS_EXAMPLE,
                      extra_refs=[G.NAVATTR, G.LMRES, TER.CLIP, TER.NODRAW, TER.SKYBOX],
                      entities_json=os.path.join(os.path.dirname(os.path.abspath(out_vmap)), '..', '..', '..', 'entities.json'))
    L.export(os.path.join(os.path.dirname(os.path.abspath(out_vmap)), '..', '..', '..', 'layout.json'))
    stamp('done: %d entities' % sum(counts.values()))


# ---------------------------------------------------------------- lobby (briefing room) with the banner
LZ = L.LOBBY_Z
LW, LD, LH = 1536.0, 1152.0, 352.0
WOODW = 'materials/de_ancient/hr_ancient_ceiling_wood_01_base.vmat'
FLOORM = 'materials/cs_italy/wood/wood_boards_worn_1.vmat'
BANNER = 'materials/mv/briefing_banner.vmat'
for m in (WOODW, FLOORM): vmesh.TEX_SIZE[m] = (1024, 1024)


def lobby(d, clone):
    vmesh.mesh_node(vmesh.box_mesh(-LW / 2, -LD / 2, LZ, LW / 2, LD / 2, LZ + LH, dict(bottom=FLOORM, top=WOODW, side=WOODW), inward=True), GROUP)
    bw, bh = 1100.0, 260.0
    by = LD / 2 - 2
    verts = [(-bw / 2, by, LZ + 60), (bw / 2, by, LZ + 60), (bw / 2, by, LZ + 60 + bh), (-bw / 2, by, LZ + 60 + bh),
             (-bw / 2, by + 1, LZ + 60), (bw / 2, by + 1, LZ + 60), (bw / 2, by + 1, LZ + 60 + bh), (-bw / 2, by + 1, LZ + 60 + bh)]
    vmesh.TEX_SIZE[BANNER] = (2048, int(2048 * bh / bw))
    bm = vmesh.polymesh_open(verts, [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]],
                             [BANNER] + [TER.NODRAW] * 5, scale=0.25)
    fvd = bm.get('faceVertexData'); tex = fvd.get('streams')[0].get('data')
    E_dest = bm.get('edgeVertexIndices'); E_face = bm.get('edgeFaceIndices')
    for i, f in enumerate(E_face):
        if f == 0:
            vx, vy, vz = verts[E_dest[i]]
            tex[i] = ((vx + bw / 2) / bw, 1 - (vz - LZ - 60) / bh)
    vmesh.mesh_node(bm, GROUP, bake=False, shadows=False)
    for i in range(32):
        x = -560 + (i % 8) * 160; y = -420 + (i // 8) * 80
        ent('info_player_terrorist', (x - 40, y, LZ + 8), (0, 90, 0), group=GROUP, enabled='1', priority='0')
        ent('info_player_counterterrorist', (x + 40, y + 340, LZ + 8), (0, 90, 0), group=GROUP, enabled='1', priority='0')
    for (lx, ly) in ((-400, -250), (400, -250), (-400, 250), (400, 250)):
        ent('light_omni2', (lx, ly, LZ + LH - 40), (90, 0, 0), group=GROUP, brightness_units='1', brightness_lumens='9000', brightness='2',
            color='255 220 170', range='1100', directlight='3', castshadows='0', colormode='0', enabled='1', bouncescale='1.0', shape='0')
    clone('env_combined_light_probe_volume', (0, 0, LZ + LH / 2), box_mins='%g %g %g' % (-LW / 2, -LD / 2, -LH / 2), box_maxs='%g %g %g' % (LW / 2, LD / 2, LH / 2),
          voxel_size='48.0', targetname='lobby_probe', indoor_outdoor_level='2')
    for cls, pos, ang in (('counterterrorist_team_intro', (300, 300, LZ + 64), (0, 90, 0)), ('terrorist_team_intro', (-300, 300, LZ + 64), (0, 90, 0)),
                          ('team_select', (0, -300, LZ + 64), (0, 90, 0)), ('end_of_match', (0, 0, LZ + 64), (0, 90, 0))):
        clone(cls, pos, ang)
    G.hint((-LW / 2 - 64, -LD / 2 - 64, LZ - 64, LW / 2 + 64, LD / 2 + 64, LZ + LH + 64), 'Low', GROUP)
    G.lmres_box((-LW / 2, -LD / 2, LZ, LW / 2, LD / 2, LZ + 160), GROUP)
    G.nav_seed((-200, -480, LZ + 2, 200, -400, LZ + 34), GROUP)
    G.nav_seed((-200, 400, LZ + 2, 200, 480, LZ + 34), GROUP)
    # script, HUD, params
    ent('point_script', (0, 0, LZ + 100), group=GROUP, targetname='mv_script', cs_script='maps/scripts/%s.vjs' % NAME)
    ent('custom_hud_layout', (32, 0, LZ + 100), group=GROUP, targetname='mv_hud', layout='panorama/layout/custom_game/%s.vxml' % NAME, observable='1')
    ent('info_map_parameters', (-32, 0, LZ + 100), group=GROUP, targetname='mv_params', buying='3', usenormalspawnsfordm='1', disableautogenerateddmspawns='1')
    banner_png()


def _font(names, size):
    for n in names:
        for d in (r'C:\Windows\Fonts', '/usr/share/fonts/truetype/dejavu'):
            p = os.path.join(d, n)
            if os.path.exists(p):
                try: return ImageFont.truetype(p, size)
                except Exception: pass
    return ImageFont.load_default()


def banner_png():
    bw, bh = 1100.0, 260.0
    W, H = 2048, int(2048 * bh / bw)
    im = Image.new('RGB', (W, H), (28, 33, 26))
    dr = ImageDraw.Draw(im)
    f1 = _font(['impact.ttf', 'DejaVuSerif-Bold.ttf'], 96); f2 = _font(['arialbd.ttf', 'DejaVuSansCondensed-Bold.ttf'], 38)
    f3 = _font(['arialbd.ttf', 'DejaVuSansCondensed-Bold.ttf'], 30); f4 = _font(['arial.ttf', 'DejaVuSansCondensed.ttf'], 26)
    dr.rectangle((14, 14, W - 15, H - 15), outline=(160, 150, 100), width=6)
    def centre(t, y, f, col):
        bb = dr.textbbox((0, 0), t, font=f); dr.text(((W - (bb[2] - bb[0])) / 2 - bb[0], y), t, fill=col, font=f)
    centre('MONSOON VALLEY', 22, f1, (226, 214, 176))
    dr.line((W * 0.3, 134, W * 0.7, 134), fill=(160, 150, 100), width=3)
    centre('FIVE FLAGS, ONE VALLEY, HOLD THREE TO BLEED THEM OUT', 152, f2, (214, 186, 96))
    centre('FLY, RIDE, CALL FIRE, LAY THE GUNS', 200, f2, (214, 186, 96))
    centre('!ROLES  TO VIEW COMBAT ROLES      !RIFLE / !MG / !AT  FOR YOUR KIT', 262, f3, (214, 206, 188))
    centre('HOLD E ON OPEN GROUND TO CALL A FIRE MISSION    E ON A HELICOPTER DOOR TO RIDE', 304, f3, (214, 206, 188))
    centre('CREATED FOR SLIME SERVERS', 372, f4, (170, 160, 136))
    centre('DISCORD.GG/SLIMESERVERS', 406, f4, (150, 200, 140))
    arr = np.asarray(im, np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    grain = fbm(xx / 60.0, yy / 60.0, 1.0, 3, seed=4)[..., None]
    arr = arr * (0.9 + 0.12 * grain)
    p = os.path.join(OUT, 'materials/mv'); os.makedirs(p, exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(p, 'briefing_banner_color.png'))
    open(os.path.join(p, 'briefing_banner.vmat'), 'w', newline='\n').write(
        '// mg_monsoon briefing banner (generated)\nLayer0\n{\n\tshader "csgo_unlitgeneric.vfx"\n\tF_BLEND_MODE 0\n'
        '\tTextureColor "materials/mv/briefing_banner_color.png"\n\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"\n}\n')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
