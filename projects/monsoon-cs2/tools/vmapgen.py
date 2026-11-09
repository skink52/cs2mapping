"""Map-writing recipes for generated Hammer maps, on top of dmx.py + vmaplib.py + vmesh.py.

A generator script opens the user's latest vmap (or a template), adds its nodes with these helpers, then calls finish():

    import vmapgen as G
    d = G.open_map('current.vmap', addon_out)          # also sets up vmaplib (node ids, new_children)
    G.room((-768, -768, -12000, 768, 768, -11616), dict(floor=F, ceil=C, wall=W), group='gen')
    G.hint((-832, -832, -12064, 832, 832, -11552), 'Low', group='gen')
    G.finish(d, 'out.vmap', group='gen', entities_json='entities.json')

What is here:
- skies: sky_files() (csgo_moondome vmat + equirect PNG per area), sky_vmat() (env_sky sky.vfx vmat), env_sky()
- shells: room(), shell(), moondome() (+ optional toolsskybox shell, single-sky maps only)
- vis: hint() (hintType by name), path_hints() (Low hints along a path), assert_no_overlap()
- entities: cache_room() (one hidden prop_dynamic per model), sound_events() (point_soundevent per event),
  template_pool() (point_template + source prop for script spawning), nav_seed() (func_nav_markup WALKABLESEED),
  probe_volume(), map_params(), skybox_reference(), clone() (copy the full key set of an existing entity)
- lighting: lmres_grid() / lmres_terrain() / lmres_box() (toolslightmapres player-space shells)
- terrain: Terrain (512-unit tiles, per-tile resolution, crack-free seams, surf_z() for spawn heights), fix_pinches()
- finish(): vis-group swap (re-runs replace only their own nodes), first-run removal of Hammer's sample entities and
  default box, map_asset_references + map_subasset_reference_* rewritten from the real entities, entities.json for the mock
- EditKeeper: keeps the user's Hammer edits to generated objects (previous generated map vs the user's latest save)

From space-racer-cs2/tools/vmap.py, hellmatch-cs2/tools/vmap_env.py and trenchwarfare-cs2/tools/make_map.py (MIT), made project-neutral.
"""
import os, json, math, shutil
import numpy as np
from PIL import Image
import dmx
from dmx import T_STRING
import vmaplib
from vmaplib import ent, polymesh, box_faces
import vmesh

PREFIX = os.environ.get('CS2_MODEL_PREFIX', 'props')
TOOLSSKY = 'materials/tools/toolsskybox.vmat'
NAVATTR = 'materials/tools/toolsnavattribute.vmat'
LMRES = 'materials/tools/toolslightmapres.vmat'
# visibility_hint hintType values (base.fgd; region size in brackets). Low over play space, Lowest over the void.
HINT = {'High': 0, 'Normal': 1, 'Medium': 2, 'Low': 3, 'Lower': 8, 'Lowest': 9, 'Reduced': 10}
# unnamed entities of these classes are Hammer's addon-template samples: dropped on the first run
SAMPLE_CLASSES = ('point_script', 'custom_hud_layout', 'point_soundevent', 'point_template', 'prop_dynamic')
# example of classes a generator that writes its own lighting/spawns may own outright (mg_trenchwarfare). Passing this as
# finish(drop_classes=...) deletes the user's own copies too, whatever their vis group: tell the mapper.
GENERATOR_OWNS_EXAMPLE = ('light_environment', 'env_sky', 'env_cubemap_fog', 'env_combined_light_probe_volume', 'post_processing_volume',
                          'env_soundscape', 'func_buyzone', 'info_player_start', 'info_player_terrorist', 'info_player_counterterrorist',
                          'point_worldtext', 'counterterrorist_team_intro', 'terrorist_team_intro', 'team_select', 'end_of_match',
                          'cs_minimap_boundary', 'point_nav_walkable')


def open_map(src, addon_out):
    """load a vmap and point vmaplib at it (new node ids continue after the highest in the map)"""
    d = dmx.DMX.load(src)
    vmaplib.init(d, addon_out)
    return d


def world_of(d):
    return d.root.get('world')


def walk_nodes(node):
    """every node under node (groups included), depth first"""
    for c in node.get('children') or []:
        yield c
        yield from walk_nodes(c)


def entities(d):
    return [c for c in walk_nodes(world_of(d)) if c.type == 'CMapEntity']


def props_of(c):
    return c.get('entity_properties')


def box_center_half(box):
    x0, y0, z0, x1, y1, z1 = box
    return ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)


# ---------------------------------------------------------------- skies
def _save_img(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(img, str):
        shutil.copy(img, path); im = Image.open(path)
    else:
        im = img if isinstance(img, Image.Image) else Image.fromarray(np.asarray(img))
        im.save(path)
    if abs(im.size[0] - 2 * im.size[1]) > 1:
        print('vmapgen: %s is %dx%d, sky panoramas should be 2:1 equirectangular' % (path, im.size[0], im.size[1]))


def sky_files(out, key, img, rel_dir=None):
    """moondome material for one area: csgo_moondome mesh material showing the equirect panorama img (array, PIL image or png path).
    Unlit, no shadows, no fog. Returns the vmat path for shell()/moondome()."""
    rel_dir = rel_dir or 'materials/%s/sky' % PREFIX
    dd = os.path.join(out, rel_dir); os.makedirs(dd, exist_ok=True)
    white = os.path.join(dd, 'moondome_color.png')
    if not os.path.exists(white): Image.new('RGB', (16, 16), (255, 255, 255)).save(white)
    _save_img(img, os.path.join(dd, 'sky_%s_color.png' % key))
    open(os.path.join(dd, 'moondome_%s.vmat' % key), 'w', newline='\n').write('''// moondome (%s): mesh material that shows the sky panorama, unlit, no shadows, no fog (AI-generated)
Layer0
{
	shader "csgo_moondome.vfx"
	F_DO_NOT_CAST_SHADOWS 1
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "%s/moondome_color.png"
	g_flCubeParallax "0.000"
	g_bFogEnabled "0"
	TextureCubeMap "%s/sky_%s_color.png"
}
''' % (key, rel_dir, rel_dir, key))
    return '%s/moondome_%s.vmat' % (rel_dir, key)


def sky_vmat(out, img, name='sky', rel_dir=None):
    """env_sky material (sky.vfx) for an equirect panorama. F_TEXTURE_FORMAT2 + g_flBrightnessExposureBias are written as
    space-racer/hellmatch do (both work in CS2; which of them is actually needed is unverified)."""
    rel_dir = rel_dir or 'materials/%s/sky' % PREFIX
    dd = os.path.join(out, rel_dir); os.makedirs(dd, exist_ok=True)
    _save_img(img, os.path.join(dd, '%s_color.png' % name))
    open(os.path.join(dd, name + '.vmat'), 'w', newline='\n').write(
        '// sky panorama for env_sky (AI-generated)\nLayer0\n{\n\tshader "sky.vfx"\n\tF_TEXTURE_FORMAT2 1\n'
        '\tSkyTexture "%s/%s_color.png"\n\tg_flBrightnessExposureBias "0.000"\n}\n' % (rel_dir, name))
    return '%s/%s.vmat' % (rel_dir, name)


def env_sky(vmat, origin, group='', name='sky', tint='255 255 255', brightness='1.0'):
    return ent('env_sky', origin, group=group, targetname=name, skyname=vmat, tint_color=tint, brightnessscale=str(brightness), StartDisabled='0')


# ---------------------------------------------------------------- shells (closed boxes seen from inside)
def room(box, mats, group=''):
    """closed room seen from inside; mats: one material or dict(floor, ceil, wall)"""
    v, faces = box_faces(*box)
    fm = [mats] * 6 if isinstance(mats, str) else [mats['floor'], mats['ceil']] + [mats['wall']] * 4
    return vmaplib.mesh_node(polymesh(v, faces, fm), group)


def shell(box, mat, inset=0.0, group=''):
    x0, y0, z0, x1, y1, z1 = box
    v, faces = box_faces(x0 + inset, y0 + inset, z0 + inset, x1 - inset, y1 - inset, z1 - inset)
    return vmaplib.mesh_node(polymesh(v, faces, [mat] * 6, scale=1.0), group)


def moondome(box, mat, group='', toolsskybox=False):
    """sky shell around an area. toolsskybox=True adds a toolsskybox shell 1 unit inside it: only for single-sky maps
    (a toolsskybox face shows the one env_sky, so per-area moondome skies break with it)."""
    shell(box, mat, 0, group)
    if toolsskybox: shell(box, TOOLSSKY, 1, group)


# ---------------------------------------------------------------- vis
def boxes_overlap(a, b):
    return not (a[3] <= b[0] or b[3] <= a[0] or a[4] <= b[1] or b[4] <= a[1] or a[5] <= b[2] or b[5] <= a[2])


def assert_no_overlap(boxes):
    """areas (moondome boxes, arenas) must stay clear of each other"""
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not boxes_overlap(a, b), ('boxes overlap', a, b)


def hint(box, kind='Low', group=''):
    """visibility_hint over box (x0, y0, z0, x1, y1, z1); kind is a HINT name or the hintType number"""
    c, h = box_center_half(box)
    t = HINT[kind] if isinstance(kind, str) else int(kind)
    return ent('visibility_hint', c, group=group, hintType=str(t), box_mins='%g %g %g' % (-h[0], -h[1], -h[2]), box_maxs='%g %g %g' % h)


def path_hints(points, half_width=0.0, area=None, kind='Low', chunk=40, pad_xy=900, pad_down=350, pad_up=1100, closed=True, group='',
               merge=False):
    """Low hints in a band along a path (a race track's centreline): chunks of `chunk` samples, padded sideways/down/up for the
    cameras, clipped 8 units inside `area` (the area's moondome box). Neighbouring chunks overlap (Space Racer shipped like that);
    merge=True merges overlapping boxes until none overlap. Returns the boxes."""
    P = np.asarray(points, float); n = len(P)
    hw = np.broadcast_to(np.asarray(half_width, float), (n,))
    out = []
    last = n if closed else n - 1
    for a0 in range(0, last, chunk):
        idx = [(a0 + k) % n for k in range(chunk + 1)] if closed else list(range(a0, min(a0 + chunk + 1, n)))
        q = P[idx]; w = hw[idx].max()
        b = [q[:, 0].min() - w - pad_xy, q[:, 1].min() - w - pad_xy, q[:, 2].min() - pad_down,
             q[:, 0].max() + w + pad_xy, q[:, 1].max() + w + pad_xy, q[:, 2].max() + pad_up]
        if area is not None:
            b = [max(area[k] + 8, b[k]) for k in range(3)] + [min(area[k + 3] - 8, b[k + 3]) for k in range(3)]
        out.append(tuple(b))
    if merge:
        changed = True
        while changed:
            changed = False
            for i in range(len(out)):
                for j in range(i + 1, len(out)):
                    if boxes_overlap(out[i], out[j]):
                        a, b = out[i], out[j]
                        out[i] = tuple(min(a[k], b[k]) for k in range(3)) + tuple(max(a[k], b[k]) for k in range(3, 6))
                        del out[j]; changed = True; break
                if changed: break
        assert_no_overlap(out)
    for b in out: hint(b, kind, group)
    return out


# ---------------------------------------------------------------- entities the script needs
def _existing(d, classname, key, group):
    """{key value: node} of entities of a class already in the map, outside our own group (finish() replaces that)"""
    out = {}
    for c in entities(d):
        ep = props_of(c)
        if ep.get('classname') == classname and ep.get(key) and c.get('customVisGroup', '') != group: out[ep.get(key)] = c
    return out


def cache_room(d, models, origin, size=(2048, 1024), step=(64, 64), prefix='cache_', group='', only_missing=True):
    """One non-solid prop_dynamic per model in a sealed room, so CS2 compiles and precaches every model the script may SetModel to.
    only_missing: models the map already has a prop for (placed by an earlier build, in any group) are skipped, and new props go on
    free grid spots. Build the room itself with room(). Returns the number added."""
    have = {props_of(c).get('model') for c in entities(d) if props_of(c).get('classname') == 'prop_dynamic' and c.get('customVisGroup', '') != group}
    taken = [tuple(c.get('origin')[:2]) for c in entities(d) if (props_of(c).get('targetname') or '').startswith(prefix)
             and c.get('customVisGroup', '') != group]
    todo = [m for m in models if not (only_missing and m in have)]
    ox, oy, oz = origin
    nx, ny = int(size[0] // step[0]) - 1, int(size[1] // step[1]) - 1
    grid = [(ox - size[0] / 2 + step[0] * (i + 1), oy - size[1] / 2 + step[1] * (j + 1)) for j in range(ny) for i in range(nx)]
    free = [g for g in grid if all(abs(g[0] - t[0]) > step[0] * 0.4 or abs(g[1] - t[1]) > step[1] * 0.4 for t in taken)]
    assert len(free) >= len(todo), ('cache room full', len(free), len(todo))
    for k, m in enumerate(todo):
        name = prefix + os.path.splitext(os.path.basename(m))[0].lower()
        ent('prop_dynamic', (free[k][0], free[k][1], oz + 8), group=group, targetname=name, model=m, solid='0', disableshadows='1')
    return len(todo)


def sound_events(d, events, origin, prefix='snd_', group='', cols=16, step=64, stop_on_new=lambda ev: False, only_missing=True):
    """one point_soundevent per sound event (targetname prefix + event with dots as underscores); the script starts/stops them.
    Events the map already has outside our group (by targetname) are skipped. Returns the number added."""
    have = _existing(d, 'point_soundevent', 'targetname', group)
    todo = [e for e in events if not (only_missing and (prefix + e.replace('.', '_')) in have)]
    for k, ev in enumerate(todo):
        ent('point_soundevent', (origin[0] + (k % cols) * step, origin[1] + (k // cols) * step, origin[2]), group=group,
            targetname=prefix + ev.replace('.', '_'), soundName=ev, startOnSpawn='0', toLocalPlayer='0',
            stopOnNew='1' if stop_on_new(ev) else '0', saveAndRestore='0')
    return len(todo)


def template_pool(name, origin, null_model, group=''):
    """point_template the script spawns props from (ForceSpawn / SpawnEntities): source prop_dynamic '<name>_src' with an
    invisible model, non-solid, never faded; the template inserts into the point_template spawn group for connected clients."""
    ent('prop_dynamic', origin, group=group, targetname=name + '_src', model=null_model, solid='0', disableshadows='1', fademindist='-1',
        fademaxdist='0', skin='default', rendercolor='255 255 255', renderamt='255')
    return ent('point_template', (origin[0], origin[1], origin[2] + 16), group=group, targetname=name, Template01=name + '_src',
               spawnflags='2', asynchronous='0', timeoutInterval='0', spawnGroupType='INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP',
               clientOnlyEntityBehavior='CREATE_FOR_CURRENTLY_CONNECTED_CLIENTS_ONLY')


def nav_seed(box, group=''):
    """func_nav_markup WALKABLESEED with its own closed toolsnavattribute box as child (just above a floor). Without a seed
    nav generation finds nothing and bots can't be added."""
    seed = ent('func_nav_markup', (0, 0, 0), group=group, navProperty_NavGen='WALKABLESEED', flags='1')
    v, faces = box_faces(*box, inward=False)
    seed.attr('children')[2].append(vmaplib.mesh_node(polymesh(v, faces, [NAVATTR] * 6, scale=1.0), group, attach=False))
    return seed


def probe_volume(box, voxel=64, group='', name='', **keys):
    """env_combined_light_probe_volume over box. Sizes used: 48-64 over play space, 32 in tunnels, ~108 for far strips."""
    c, h = box_center_half(box)
    kv = dict(StartDisabled='0', box_mins='%g %g %g' % (-h[0], -h[1], -h[2]), box_maxs='%g %g %g' % h, voxel_size='%.1f' % voxel,
              flood_fill='1', voxelize='1', light_probe_volume_from_cubemap='0', storage='-1', indoor_outdoor_level='0',
              edge_fade_dists='0 32 0', bakenearz='2.0', bakefarz='4096.0')
    if name: kv['targetname'] = name
    kv.update({k: str(v) for k, v in keys.items()})
    return ent('env_combined_light_probe_volume', c, group=group, **kv)


def map_params(origin, name='map_params', group=''):
    """info_map_parameters: no buying, normal spawns in DM; a targetname lets the script call FireWinCondition"""
    return ent('info_map_parameters', origin, group=group, targetname=name, buying='3', usenormalspawnsfordm='1', disableautogenerateddmspawns='1')


def skybox_reference(map_name, group='', name='skybox'):
    """3D skybox: maps/<map>_3dskybox.vmap (mapUsageType skybox, sky_camera scale 16 at its origin; see make_skybox.py).
    Origin (0,0,0): mg_trenchwarfare first had (0,0,-12000) and the mapper moved it to the origin."""
    return ent('skybox_reference', (0, 0, 0), group=group, targetname=name, targetMapName='maps/%s_3dskybox.vmap' % map_name,
               fixupNames='1', worldGroupID='skyboxWorldGroup0')


def clone(d, cls, origin, angles=(0, 0, 0), group='', **keys):
    """new entity of cls carrying the full key set of the first one already in the map (template entities have every key
    Hammer writes); keys override. Without a template it is a plain ent()."""
    e = ent(cls, origin, angles, group=group)
    props = props_of(e)
    for c in entities(d):
        if c is e or props_of(c).get('classname') != cls: continue
        have = {a[0] for a in props.attrs}
        for a in props_of(c).attrs:
            if a[0] not in have and a[0] != 'targetname': props.attrs.append([a[0], a[1], a[2]])
        break
    for k, v in keys.items(): props.set(k, T_STRING, str(v))
    return e


# ---------------------------------------------------------------- lightmap player space (toolslightmapres)
def fix_pinches(valid):
    """cells touching only diagonally would make a non-manifold vertex: fill one of the other two cells"""
    v = np.array(valid, bool)
    for _ in range(8):
        a = v[:-1, :-1]; b = v[1:, :-1]; c = v[:-1, 1:]; dd = v[1:, 1:]
        p1 = a & dd & ~b & ~c; p2 = b & c & ~a & ~dd
        if not (p1.any() or p2.any()): break
        ii, jj = np.nonzero(p1); v[ii + 1, jj] = True
        ii, jj = np.nonzero(p2); v[ii, jj] = True
    return v


def lmres_grid(occ, x0, y0, cell, z_bottom, z_top, group=''):
    """one closed toolslightmapres mesh over the occupied cells of a grid: the lightmap compiler gives surfaces near it more
    texels. z_bottom/z_top: per cell (nx, ny) or scalars; shared corners take the lowest bottom / highest top.
    Side faces only on the outline. Not solid, not in vis. Returns the node."""
    occ = fix_pinches(occ)
    nx, ny = occ.shape
    zb = np.broadcast_to(np.asarray(z_bottom, float), (nx, ny)); zt = np.broadcast_to(np.asarray(z_top, float), (nx, ny))
    LB = np.full((nx + 1, ny + 1), 1e9); LT = np.full((nx + 1, ny + 1), -1e9)
    ci, cj = np.nonzero(occ)
    for di, dj in ((0, 0), (1, 0), (0, 1), (1, 1)):
        np.minimum.at(LB, (ci + di, cj + dj), zb[ci, cj]); np.maximum.at(LT, (ci + di, cj + dj), zt[ci, cj])
    lv = {}; verts = []; faces = []
    def V(i, j, top):
        k = (i, j, top)
        if k not in lv: lv[k] = len(verts); verts.append((x0 + i * cell, y0 + j * cell, LT[i, j] if top else LB[i, j]))
        return lv[k]
    for i, j in zip(ci, cj):
        faces.append([V(i, j, 0), V(i + 1, j, 0), V(i + 1, j + 1, 0), V(i, j + 1, 0)][::-1])     # bottom, facing down
        faces.append([V(i, j, 1), V(i + 1, j, 1), V(i + 1, j + 1, 1), V(i, j + 1, 1)])           # top
        for (a, b, ni, nj) in (((i, j), (i + 1, j), i, j - 1), ((i + 1, j), (i + 1, j + 1), i + 1, j),
                               ((i + 1, j + 1), (i, j + 1), i, j + 1), ((i, j + 1), (i, j), i - 1, j)):
            if 0 <= ni < nx and 0 <= nj < ny and occ[ni, nj]: continue
            faces.append([V(a[0], a[1], 0), V(b[0], b[1], 0), V(b[0], b[1], 1), V(a[0], a[1], 1)])
    vmesh.TEX_SIZE[LMRES] = (64, 64)
    return vmesh.mesh_node(vmesh.polymesh_open(verts, faces, [LMRES] * len(faces)), group, bake=False, shadows=False, visexclude=True)


def lmres_terrain(occ, x0, y0, cell, height, below=8.0, above=128.0, samples=4, group=''):
    """lmres_grid over terrain: each cell from (lowest ground - below) to (highest ground + above); height(X, Y) -> Z arrays"""
    nx, ny = occ.shape
    f = (np.arange(samples + 1) / samples) * cell
    ox, oy = np.meshgrid(f, f, indexing='ij')
    X = x0 + np.arange(nx)[:, None, None, None] * cell + ox[None, None]
    Y = y0 + np.arange(ny)[None, :, None, None] * cell + oy[None, None]
    X, Y = np.broadcast_arrays(X, Y)
    Z = np.asarray(height(X, Y), float)
    return lmres_grid(occ, x0, y0, cell, Z.min((2, 3)) - below, Z.max((2, 3)) + above, group)


def lmres_box(box, group=''):
    """lightmap player-space box (a room or tunnel), 2 units inside its walls"""
    x0, y0, z0, x1, y1, z1 = box
    vmesh.TEX_SIZE[LMRES] = (64, 64)
    return vmesh.mesh_node(vmesh.box_mesh(x0 + 2, y0 + 2, z0 + 2, x1 - 2, y1 - 2, z1 - 2, LMRES), group, bake=False, shadows=False, visexclude=True)


# ---------------------------------------------------------------- terrain
class Terrain:
    """Open-sheet terrain in square tiles. Each tile has its own cell size (res(cx, cy) -> 32/64/128..., powers of two that divide
    the tile); along an edge shared with a coarser tile the finer tile's heights are interpolated between the coarser vertices,
    so the seams don't crack.
      height(X, Y) -> Z (arrays); material: one vmat or material(cx, cy) -> vmat per cell;
      paint(X, Y, Z) -> (blend, tint) per vertex (..., 4) arrays for Valve blend materials (VertexPaintBlendParams / TintColor), or None;
      holes(CX, CY, r) -> bool per cell to leave out (tunnel mouths, pits)."""

    def __init__(self, height, x0, y0, x1, y1, tile=512, res=lambda cx, cy: 64):
        self.height = height; self.tile = tile
        self.tiles = {}
        for tx in range(int(x0), int(x1), tile):
            for ty in range(int(y0), int(y1), tile):
                r = int(res(tx + tile / 2, ty + tile / 2))
                assert tile % r == 0, ('cell size must divide the tile', r)
                self.tiles[(tx, ty)] = r

    def grid(self, tx, ty):
        r = self.tiles[(tx, ty)]; n = self.tile // r
        xs = tx + np.arange(n + 1) * r; ys = ty + np.arange(n + 1) * r
        X, Y = np.meshgrid(xs.astype(float), ys.astype(float), indexing='ij')
        Z = np.asarray(self.height(X, Y), float).copy()
        for dx, dy, edge in ((-1, 0, 'x0'), (1, 0, 'x1'), (0, -1, 'y0'), (0, 1, 'y1')):
            nb = self.tiles.get((tx + dx * self.tile, ty + dy * self.tile))
            if nb is None or nb <= r: continue
            k = nb // r
            line = Z[0 if edge == 'x0' else n] if edge in ('x0', 'x1') else Z[:, 0 if edge == 'y0' else n]
            new = line.copy()
            for j in range(n + 1):
                j0 = (j // k) * k; j1 = min(j0 + k, n); t = (j - j0) / k if j1 > j0 else 0
                new[j] = line[j0] * (1 - t) + line[j1] * t
            if edge in ('x0', 'x1'): Z[0 if edge == 'x0' else n] = new
            else: Z[:, 0 if edge == 'y0' else n] = new
        return X, Y, Z

    def build(self, material, paint=None, holes=None, group='', bake=True, shadows=True):
        """writes one mesh per tile; returns the quad count"""
        nq = 0
        for (tx, ty), r in self.tiles.items():
            X, Y, Z = self.grid(tx, ty)
            CX = (X[:-1, :-1] + X[1:, 1:]) / 2; CY = (Y[:-1, :-1] + Y[1:, 1:]) / 2
            valid = None
            if holes is not None:
                cut = np.asarray(holes(CX, CY, r), bool)
                if cut.all(): continue
                if cut.any(): valid = fix_pinches(~cut)
            fm = (lambda i, j: material) if isinstance(material, str) else (lambda i, j: material(CX[i, j], CY[i, j]))
            for m in ([material] if isinstance(material, str) else []): vmesh.TEX_SIZE.setdefault(m, (1024, 1024))
            if paint is not None:
                pa, ti = paint(X, Y, Z)
                verts, faces, mats, (pa, ti) = vmesh.grid_sheet(X, Y, Z, fm, valid, vert_attr=(np.asarray(pa), np.asarray(ti)))
            else:
                verts, faces, mats = vmesh.grid_sheet(X, Y, Z, fm, valid); pa = ti = None
            vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, paint=pa, tint=ti), group, bake=bake, shadows=shadows)
            nq += len(faces)
        return nq

    def surf_z(self, x, y, pad=24.0):
        """height to put a spawn / teleport target on: per sample the bilinear height of the tile cell plus 0.25 x the cell's z range
        (quads may be split either way), max over a 3x3 pattern within pad. Add your own clearance."""
        best = -1e9; T = self.tile
        for qx in (x - pad, x, x + pad):
            for qy in (y - pad, y, y + pad):
                tx = int(math.floor(qx / T) * T); ty = int(math.floor(qy / T) * T)
                r = self.tiles.get((tx, ty))
                if r is None: continue
                cx0 = tx + math.floor((qx - tx) / r) * r; cy0 = ty + math.floor((qy - ty) / r) * r
                z00, z10, z01, z11 = np.asarray(self.height(np.array([cx0, cx0 + r, cx0, cx0 + r], float),
                                                            np.array([cy0, cy0, cy0 + r, cy0 + r], float)), float)
                u, v = (qx - cx0) / r, (qy - cy0) / r
                zb = z00 * (1 - u) * (1 - v) + z10 * u * (1 - v) + z01 * (1 - u) * v + z11 * u * v
                best = max(best, float(zb) + 0.25 * float(max(z00, z10, z01, z11) - zb))
        return best


# ---------------------------------------------------------------- keeping the user's edits to generated objects
def obj_sig(c):
    """signature of a node: entities by class/model/origin/angles, meshes by materials + bbox + vertex count"""
    if c.type == 'CMapEntity':
        ep = props_of(c)
        return json.dumps(['E', ep.get('classname') or '', ep.get('model') or '', [round(v, 1) for v in c.get('origin')], [round(v, 1) for v in c.get('angles')]])
    if c.type == 'CMapMesh':
        md = c.get('meshData'); o = np.array(c.get('origin') or (0, 0, 0), float)
        mats = list(md.get('materials') or [])
        pos = None
        for st in md.get('vertexData').get('streams'):
            if st.get('semanticName') == 'position': pos = np.array(st.get('data'), float)
        bb = [] if pos is None or not len(pos) else np.round(np.concatenate([pos.min(0) + o, pos.max(0) + o]), 0).tolist()
        return json.dumps(['M', mats, bb, len(pos) if pos is not None else 0])
    return None


def _adiff(a, b):
    return max(abs(((x - y) + 180) % 360 - 180) for x, y in zip(a, b))


class EditKeeper:
    """Run the generator as: gen.py <user's latest vmap> <out> <addon> <previous generated vmap (what the user was given)>.
    Create the keeper right after open_map(), before writing anything:
      - generated objects in the user's map with no match in the previous output (same class+model, origin < 0.75 u, angles < 1 deg;
        meshes by material + bbox + vertex count) were moved/edited/added by the user: they are re-tagged user_group and kept;
      - the previous objects they replaced are recorded in edits_json and the generator's copies are skipped from then on;
      - in finish(), a user copy within 12 u / 8 deg of something the generator now makes itself is dropped (edit adopted).
    Keep each delivered output (gen_1.vmap, gen_2.vmap...) for the next run's prev argument."""

    def __init__(self, d, prev_path, group, user_group='user_edits', edits_json='user_edits.json', move_tol=0.75, ang_tol=1.0,
                 adopt_move=12.0, adopt_ang=8.0):
        self.group, self.user_group, self.edits_json = group, user_group, edits_json
        self.adopt_move, self.adopt_ang = adopt_move, adopt_ang
        self.skip = set(json.load(open(edits_json))) if edits_json and os.path.exists(edits_json) else set()
        self.kept = 0
        if not prev_path: return
        world = world_of(d)
        prev = [c for c in dmx.DMX.load(prev_path).root.get('world').get('children') if c.get('customVisGroup', '') == group]
        mine = [c for c in world.get('children') if c.get('customVisGroup', '') == group]
        key = lambda c: (props_of(c).get('classname') or '', props_of(c).get('model') or '')
        pool, msig, used = {}, {}, set()
        for c in prev:
            if c.type == 'CMapEntity': pool.setdefault(key(c), []).append(c)
            elif c.type == 'CMapMesh': msig.setdefault(obj_sig(c), []).append(c)
        for c in mine:
            hit = None
            if c.type == 'CMapEntity':
                o = np.array(c.get('origin')); an = c.get('angles')
                for g in pool.get(key(c), ()):
                    if id(g) not in used and np.abs(np.array(g.get('origin')) - o).max() < move_tol and _adiff(an, g.get('angles')) < ang_tol:
                        hit = g; break
            elif c.type == 'CMapMesh':
                hit = next((g for g in msig.get(obj_sig(c), ()) if id(g) not in used), None)
            else:
                continue
            if hit is not None: used.add(id(hit)); continue
            c.attr('customVisGroup')[2] = user_group; self.kept += 1
        self.skip |= {obj_sig(g) for g in prev if id(g) not in used and g.type in ('CMapEntity', 'CMapMesh')}
        if edits_json: json.dump(sorted(self.skip), open(edits_json, 'w'), indent=0)
        print('user edits: %d kept as %s, %d generated objects replaced so far' % (self.kept, user_group, len(self.skip)))

    def filter_new(self, new):
        return [c for c in new if not self.skip or obj_sig(c) not in self.skip]

    def adopt(self, kept, new):
        """drop user copies the generator now reproduces itself"""
        idx = {}
        for c in new:
            if c.type == 'CMapEntity': idx.setdefault((props_of(c).get('classname'), props_of(c).get('model')), []).append(c)
        out, n = [], 0
        for c in kept:
            if c.get('customVisGroup', '') == self.user_group and c.type == 'CMapEntity':
                o = np.array(c.get('origin')); an = c.get('angles')
                if any(np.abs(np.array(g.get('origin')) - o).max() < self.adopt_move and _adiff(an, g.get('angles')) < self.adopt_ang
                       for g in idx.get((props_of(c).get('classname'), props_of(c).get('model')), ())):
                    n += 1; continue
            out.append(c)
        if n: print('user edits now produced by the generator (user copy dropped): %d' % n)
        return out


# ---------------------------------------------------------------- finish: swap into the world, bookkeeping, save
def rewrite_refs(d, extra_refs=(), strip_refs=()):
    """map_asset_references gets every material written + every model on an entity + extra_refs (minus strip_refs);
    map_subasset_reference_types/names/counts are recounted from the real entities (Hammer reports stale counts otherwise)"""
    pre = {a[0]: a for a in d.prefix[0]} if d.prefix else {}
    counts = {}
    models = set()
    for c in entities(d):
        ep = props_of(c); cls = ep.get('classname'); counts[cls] = counts.get(cls, 0) + 1
        m = ep.get('model') or ''
        if m.endswith('.vmdl'): models.add(m)
    if 'map_asset_references' in pre:
        refs = pre['map_asset_references'][2]
        refs[:] = [r for r in refs if r not in set(strip_refs)]
        for m in list(vmaplib.materials_used) + sorted(models) + list(extra_refs):
            if m and m not in refs and m not in strip_refs: refs.append(m)
    names = sorted(counts)
    if 'map_subasset_reference_names' in pre:
        pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
        pre['map_subasset_reference_names'][2] = names
        pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]
    return counts


def dump_entities(d, path):
    """entities.json for create/test/mock_point_script.mjs: named entities + spawns (name, cls, origin, angles, model)"""
    out = []
    for c in entities(d):
        ep = props_of(c); cls = ep.get('classname'); nm = ep.get('targetname') or ''
        if nm or cls.startswith('info_player'):
            r = dict(name=nm, cls=cls, origin=list(c.get('origin')), angles=list(c.get('angles')))
            if ep.get('model'): r['model'] = ep.get('model')
            out.append(r)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(out, open(path, 'w'), indent=0)
    return len(out)


def finish(d, out_path, group=None, first_run_cleanup=True, sample_classes=SAMPLE_CLASSES, drop_classes=(), keep=None,
           keeper=None, extra_refs=(), strip_refs=(), entities_json=None):
    """Put vmaplib.new_children into the world and save.
    group: our vis group; its old nodes are removed first (None = remove nothing, for delta patches).
    first_run_cleanup: when the map has no node of `group` yet, drop meshes with no vis group (Hammer's default box) and unnamed
      entities of sample_classes (the addon template's samples).
    drop_classes: classes removed whatever their group (see GENERATOR_OWNS_EXAMPLE; this removes the user's own copies too).
    keep(node) -> False removes other nodes of yours (e.g. props that must always match the current build).
    keeper: an EditKeeper. Returns {classname: count}."""
    world = world_of(d)
    kids = world.attr('children')
    first_run = bool(group) and first_run_cleanup and not any(c.get('customVisGroup', '') == group for c in kids[2])
    kept = []
    for c in kids[2]:
        if group and c.get('customVisGroup', '') == group: continue
        if first_run and c.type == 'CMapMesh' and not c.get('customVisGroup', ''): continue
        if c.type == 'CMapEntity':
            ep = props_of(c); cls = ep.get('classname')
            if cls in drop_classes: continue
            if first_run and cls in sample_classes and not ep.get('targetname'): continue
        if keep is not None and not keep(c): continue
        kept.append(c)
    removed = len(kids[2]) - len(kept)
    new = list(vmaplib.new_children)
    if keeper is not None:
        new = keeper.filter_new(new)
        kept = keeper.adopt(kept, new)
    kids[2] = kept + new
    counts = rewrite_refs(d, extra_refs, strip_refs)
    d.elements = [d.root]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    d.save(out_path)
    n_ent = dump_entities(d, entities_json) if entities_json else 0
    print('vmap: %d entities, %d meshes, %d new nodes, %d old nodes replaced%s -> %s (%.1f MB)' % (
        sum(counts.values()), sum(1 for c in walk_nodes(world) if c.type == 'CMapMesh'), len(new), removed,
        ' (first run: template samples dropped)' if first_run else '', out_path, os.path.getsize(out_path) / 1e6)
          + ('; %d entities -> %s' % (n_ent, entities_json) if entities_json else ''))
    return counts
