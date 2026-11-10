"""Writes the IRONFRAME arena map for IF_ARENA (dunes | sprawl | orbital) onto the addon template or the mapper's latest
Hammer save (IF_CURRENT_VMAP), everything in vis group ifr_gen so a re-run replaces only its own nodes.

usage: vmap.py <template_or_current.vmap> <out.vmap> <addon out dir> [--no-pictures]

Writes: the map, out/addon/_gen/arena.json (INTERFACES section 2, with the 56 x 56 nav grid), _gen/entities.json (the mock
engine), the sky + moondome materials (tools/sky.py), loading slides, the radar PSD + resource/overviews/<map>.txt (out/game),
the map icon, and preview/arenas/<arena>.png (top-down + four corner views from tools/vmap_preview.py).
The arena module (tools/arenas/<arena>.py) builds the world; arenas/common.py adds everything the script needs.
"""
import os, sys, json, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
TOOLS = os.path.join(HERE, '..', '..', '..', 'tools')
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import importlib
import numpy as np
from PIL import Image
import dmx, vmaplib, vmesh, voxel, fx_models
import vmapgen as G
import names as N
import sky as SKY
import arenas.common as C
import loading as L

if len(sys.argv) < 4: sys.exit(__doc__)
SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PICTURES = '--no-pictures' not in sys.argv
GEN = os.path.join(OUT, '_gen'); os.makedirs(GEN, exist_ok=True)
GAME_OUT = os.path.join(ROOT, 'out', 'game')
t0 = time.time()

d = G.open_map(SRC, OUT)
ctx = C.Ctx(d, OUT, N.ARENA, N.GROUP)

# the prop pool's null model (models/ifr/null.vmdl is the asset agent's; written here only when it is missing so the map compiles today)
NULL_MODEL = 'models/%s/null.vmdl' % N.PREFIX
if not os.path.exists(os.path.join(OUT, NULL_MODEL)):
    black = fx_models.emissive(OUT, 'materials/models/%s/fx' % N.PREFIX, 'ifr_null_black', (4, 4, 6), 0.0, 'IRONFRAME: invisible pool prop (AI-generated)')
    voxel.null_model(OUT, 'models/%s' % N.PREFIX, black, name='null')
    print('null model written: %s' % NULL_MODEL)

# sky + moondome materials
dome_mat, sky_mat = SKY.write(OUT, N.ARENA)

# the arena itself
arena = importlib.import_module('arenas.' + N.ARENA)
A = arena.build(ctx)
print('%s: %d meshes, %d props, %d lights after the arena build (%.0f s)' % (N.ARENA, ctx.n_mesh, ctx.n_prop, ctx.n_light, time.time() - t0))

# everything the script needs
C.environment(ctx, A, dome_mat, sky_mat)
n_probes = C.probes_and_lmres(ctx, A)
C.hints(ctx, A)
C.gameplay(ctx, A)
booth_pos = C.booth(ctx, A['env'])
cache_pos, cache_counts = C.cache(ctx, A['env'], GEN, NULL_MODEL)

# nav grid + arena.json
nav, nav_counts = C.nav_grid(A)
AJ = C.write_arena_json(A, nav, booth_pos, cache_pos, os.path.join(GEN, 'arena.json'))
print('arena.json: nav %dx%d cells of %d, %d walkable, %d struct; %d drops t / %d ct / %d ffa; %d landmarks' % (
    nav['w'], nav['h'], nav['cell'], nav_counts['walk'], nav_counts['struct'], len(AJ['drops']['t']), len(AJ['drops']['ct']), len(AJ['drops']['ffa']), len(AJ['landmarks'])))

# write the map. The template's own content sits where its default box was (the void now): the generator owns these classes.
DROP = ('info_player_terrorist', 'info_player_counterterrorist', 'info_player_start', 'func_bomb_target', 'point_worldtext', 'func_buyzone',
        'env_combined_light_probe_volume', 'post_processing_volume', 'env_soundscape', 'counterterrorist_team_intro', 'terrorist_team_intro',
        'team_select', 'end_of_match', 'cs_minimap_boundary', 'point_nav_walkable', 'env_cubemap_fog', 'info_map_parameters', 'light_environment', 'env_sky',
        'env_volumetric_fog_controller')
counts = G.finish(d, OUTPATH, group=N.GROUP, drop_classes=DROP, extra_refs=(G.NAVATTR, G.LMRES, G.TOOLSSKY), entities_json=os.path.join(GEN, 'entities.json'))
json.dump(dict(arena=N.ARENA, map=N.MAP, counts=counts, meshes=ctx.n_mesh, props=ctx.n_prop, lights=ctx.n_light, probes=n_probes, cache=cache_counts, nav=nav_counts,
               seconds=round(time.time() - t0)), open(os.path.join(GEN, 'vmap_report.json'), 'w'), indent=1)

# pictures: preview sheet, relief, loading slides, radar, icon
if PICTURES:
    prev_dir = os.path.join(ROOT, 'preview', 'arenas'); os.makedirs(prev_dir, exist_ok=True)
    prev = os.path.join(prev_dir, '%s.png' % N.ARENA)
    sx0, sy0, sz0, sx1, sy1, sz1 = A['shell']
    box = '%g,%g,%g,%g,%g,%g' % (sx0 - 64, sy0 - 64, sz0 - 64, sx1 + 64, sy1 + 64, sz1 + 64)
    r = subprocess.run([sys.executable, '-I', os.path.join(TOOLS, 'vmap_preview.py'), OUTPATH, prev, box], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    (bx0, by0, bz0), (bx1, by1, bz1) = A['bounds']
    rel = C.relief(A, (bx0, by0, bx1, by1), 1024)
    rel.save(os.path.join(prev_dir, '%s_relief.png' % N.ARENA))
    L.write_radar(OUT, N.MAP, rel, (bx0, by0, bx1, by1), game_out=GAME_OUT)
    L.write_icon(OUT, N.MAP, 'M32 2 L58 16 L58 48 L32 62 L6 48 L6 16 Z M32 14 L48 23 L48 41 L32 50 L16 41 L16 23 Z')
    if os.environ.get('IF_SLIDES', 'pixel') == 'pixel':      # pixel-art slides of the map itself (tools/map_slides.py + pixel_slides.py)
        r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'map_slides.py'), OUTPATH, OUT, N.MAP, N.TITLE, box], capture_output=True, text=True)
        print((r.stdout + r.stderr).strip()[-400:])
        names = [f for f in os.listdir(os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p')) if f.startswith(N.MAP)]
    else:
        names = L.write_slides(OUT, N.MAP, C.slides(A, rel, prev, N.TITLE))
    L.write_extras(OUT, GAME_OUT, N.MAP, N.TITLE)
    print('pictures: %s, radar + overview, icon, %d slides' % (prev, len(names)))
print('vmap done in %.0f s' % (time.time() - t0))
