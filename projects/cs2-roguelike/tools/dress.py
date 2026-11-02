"""Set dressing: everything that makes a room look lived in and fought over. Called by vmap.py after each room's shell is written.

Stock CS2 props (Anubis ivy, Ancient candles, Aztec pottery, Cache debris, Overpass wiring and junk, Nuke monitors, Train racks) plus
CS:GO decals ported by the ba_jail_lightsout import (graffiti, stains, trash, rugs), copied into materials/nt/decals as csgo_static_overlay
quads. Every room is seeded by its id, so a rebuild places the same clutter. Placement keeps clear of pillars, blocks, the dais, both
plates and everything placed before (circle footprints).

Rules (skink52, 3 Nov 2026): details are part of the design; graffiti, vegetation, puddles, refuse; a AAA team's density. Re-read this
when adding a room kind.
"""
import os, math, random, shutil

LIGHTSOUT = os.environ.get('NT_DECAL_SRC', r'C:\source1\links\content_addons\ba_jail_lightsout\materials\decals')

# ---------------------------------------------------------------- decal sets (name -> brightness)
GRAFFITI = ['decalgraffiti001a_cs', 'decalgraffiti002a', 'decalgraffiti007a', 'decalgraffiti013a', 'decalgraffiti014a', 'decalgraffiti015a',
            'decalgraffiti017a', 'decalgraffiti018a', 'decalgraffiti019a', 'decalgraffiti020a', 'decalgraffiti028a', 'decalgraffiti029a',
            'decalgraffiti031a', 'decalgraffiti032a', 'decalgraffiti033a', 'decalgraffiti034a', 'decalgraffiti035a', 'decalgraffiti039a',
            'decalgraffiti041a', 'decalgraffiti045a', 'decalgraffiti047a', 'decalgraffiti049a', 'decalgraffiti051a', 'decalgraffiti052a',
            'decalgraffiti053a', 'decalgraffiti057a', 'decalgraffiti060a', 'decalgraffiti064a', 'graffiti_germany_01', 'graffiti_germany_02',
            'graffiti_germany_face_01', 'graffiti_spray_01', 'graffiti_spray_03', 'graffiti_tag_02', 'graffiti_venice_03', 'graffiti_venice_05']
STAINS = ['decalstain002a', 'decalstain003a', 'decalstain005a', 'decalstain006a', 'decalstain008a', 'decalstain010a', 'decalstain012a', 'decalstain014a']
DRIPS = ['drainage_stain_02', 'drainage_stain_04', 'hpe_plaster_decal_decay_05']
FLOOR_TRASH = ['trash01', 'trashdecal02a', 'trashdecal04a', 'trash_00']
FLOOR_DEBRIS = ['debris_concrete001a', 'debris_exterior_00', 'debris_exterior_01', 'rubble01a']
LEAVES = ['leaves02', 'milleaves']
RUGS = ['decalrug003a', 'milrug001', 'tides_redcarpet']
MURALS = ['mural_flower_01', 'mural_flower_02', 'mural_flower_03']
BLOOD = ['blood3', 'bloodstain_001']
MISC = ['decalsigndanger001c', 'decal_paintsplatter002']
BRIGHT = {'graffiti': 0.45, 'stain': 0.35, 'floor': 0.4, 'rug': 0.5, 'mural': 0.5, 'blood': 0.35, 'misc': 0.45}
PUDDLE = 'materials/de_nuke/hr_nuke/puddle_sheet_001.vmat'      # stock static overlay, compiled in the game files

# ---------------------------------------------------------------- stock props (bounds from create/s2/prop_mesh.mjs; z = floor offset of the origin)
IVY_WALL = ['models/ivy/ivy_wall_%02d.vmdl' % i for i in range(1, 14)]                     # ~10 proud (+x), z -27..47
IVY_PILLAR = ['models/anubis/foliage/ivy02_pillar.vmdl', 'models/anubis/foliage/ivy02_pillar_flowers01.vmdl']
IVY_HANG = ['models/anubis/foliage/ivy02a.vmdl', 'models/anubis/foliage/ivy02b.vmdl', 'models/anubis/foliage/ivy02c.vmdl',
            'models/anubis/foliage/ivy02a_flowers01.vmdl', 'models/anubis/foliage/ivy02b_flowers02.vmdl', 'models/anubis/foliage/ivy02c_flowers01.vmdl']   # hang down from the origin
VINES = 'models/props_foliage/hangingvines_straight.vmdl'                                   # z +-16, hangs from the ceiling
GRASS_PACK = ['models/foliage/background/background_foliage_grass_pack_%02d.vmdl' % i for i in (1, 2, 3)]   # ~100 x 100 x 60
GRASS_TUFT = 'models/de_overpass/foliage/grass_detail_001/grass_detail_001.vmdl'          # 30 x 25 x 22
CANDLE_CLUSTER = ['models/props/de_ancient/ancient_lighting/ancient_lighting_candle_cluster_01_lit.vmdl', 'models/props/de_ancient/ancient_lighting/ancient_lighting_candle_cluster_02_lit.vmdl']
CANDLE = ['models/props/de_ancient/ancient_lighting/ancient_lighting_candle_01_lit.vmdl', 'models/props/de_ancient/ancient_lighting/ancient_lighting_candle_02_lit.vmdl', 'models/props/de_ancient/ancient_lighting/ancient_lighting_candle_03_lit.vmdl']
LANTERN = 'models/props/de_aztec/hr_aztec/aztec_lighting/aztec_lighting_lantern_01_lit.vmdl'   # hangs 31 below the origin
BOWLS = ['models/props/de_aztec/hr_aztec/aztec_pottery/aztec_pottery_bowl_01.vmdl', 'models/props/de_aztec/hr_aztec/aztec_pottery/aztec_pottery_bowl_02.vmdl', 'models/generic/ceramic_kit_01/ceramic_bowl_01.vmdl']
VASES = ['models/generic/ceramic_kit_01/ceramic_small_vase_01.vmdl', 'models/cs_italy/props/planter/clay_pottery_vase_1.vmdl']
RUG = 'models/anubis/market/rug01.vmdl'                                                     # 66 x 104, flat
MARKET = ['models/anubis/market/market_bag01.vmdl', 'models/anubis/market/market_bag02.vmdl', 'models/anubis/market/wooden_cage01.vmdl', 'models/anubis/market/wooden_cage01_stack01.vmdl']
STONE_PILES = ['models/anubis/structures/stone_pile01.vmdl', 'models/anubis/structures/stone_pile02.vmdl']
STONE_SINGLE = ['models/anubis/structures/stone_single01.vmdl', 'models/anubis/structures/stone_single02.vmdl', 'models/anubis/structures/stone_single03.vmdl']
DEBRIS_PILE = 'models/cs_italy/nature/debris/nature_debris_pile_1.vmdl'                    # 125 x 62 x 14
DEBRIS_SMALL = ['models/de_cache_s2/debris/debris_ground_01/ch2_debris_ground_01_medium_a.vmdl', 'models/de_cache_s2/debris/debris_ground_01/ch2_debris_ground_01_small_a.vmdl', 'models/de_cache_s2/debris/debris_ground_01/ch2_debris_ground_01_medium_b.vmdl']
TRASH_FLAT = ['models/de_cache_s2/debris/detail_debris/ch2_detail_debris_trash_%03d.vmdl' % i for i in (1, 2, 3, 4)]
JUNK = ['models/de_overpass/garbage/garbage_bag_1.vmdl', 'models/de_overpass/junk/cardboard_box/cardboard_box_4.vmdl', 'models/props/cs_office/cardboard_box01.vmdl', 'models/de_overpass/junk/plastic_crate_01.vmdl']
WALL_MONITOR = 'models/props/de_nuke/hr_nuke/nuke_office_desk/nuke_office_wall_monitor.vmdl'   # 25 wide, 2 deep (+y), z +-9
RETRO_MONITOR = ['models/generic/retro_monitor_01/retro_monitor_01.vmdl', 'models/generic/retro_monitor_02/retro_monitor_02.vmdl']
WIRE32 = ['models/de_overpass/industrial/simple_wiring_1/simple_wire_1_32a.vmdl', 'models/de_overpass/industrial/simple_wiring_1/simple_wire_1_32b.vmdl', 'models/de_overpass/industrial/simple_wiring_1/simple_wire_1_32c.vmdl']   # local -32..0 in x
EXHIBIT_LIGHT = 'models/anubis/lights/anubis_exhibit_light03.vmdl'
HOLO_PANEL = 'models/anubis/signs/anubis_exhibition_panel_01.vmdl'                         # 32 x 36 x 105
INFO_PANEL = 'models/anubis/signs/anubis_info_panel_01.vmdl'                               # 16 x 31 x 95
SERVER = 'models/props/de_train/hr_t/server_a/server_a.vmdl'                               # 35 x 54 x 96 centred
CRATE_ANCIENT = 'models/props/crates/crate_aus2025_promo_de_ancient.vmdl'                  # 77 x 10 x 27
FOUNTAIN = 'models/anubis/unique/a_site_fountain.vmdl'                                     # r 81, 88 tall
BANNERS = 'models/anubis/unique/banners_a.vmdl'                                            # 630 x 730, z 40..141
TOWER_RUIN = 'models/anubis/structures/tower01_destroyed.vmdl'                             # 120 x 120 x 220
PILLAR_BROKEN = 'models/anubis/structures/pillar02_broken_b.vmdl'                          # r 35, 122 tall
WALL_PANEL_BROKEN = 'models/anubis/structures/wall_detail01_192_broken.vmdl'
STATUE_SMALL = 'models/generic/stone_statue_01/stone_statue_01.vmdl'                      # 18 x 15 x 64
CLOTHES_LINE = 'models/cs_italy/props/clothing/italy_hanging_clothes_line_1.vmdl'          # 171 long (local -x)


class Ctx:
    """what the map writer lends us: prop(model, origin, yaw, solid, **kw), lamp(origin, lumens, range, color, shadows, baked_only),
    quad(verts4, mat) (a static-overlay quad with 0..1 UVs), wall_runs(box), out dir"""
    def __init__(self, prop, lamp, quad, out):
        self.prop, self.lamp, self.quad, self.out = prop, lamp, quad, out
        self.decals_done = set()


# ---------------------------------------------------------------- decal materials: copied from the lightsout port into materials/nt/decals
def decal_mat(ctx, name, group='graffiti'):
    rel = 'materials/nt/decals'
    vmat = '%s/%s.vmat' % (rel, name)
    if name in ctx.decals_done: return vmat
    src_png = os.path.join(LIGHTSOUT, name + '.png'); src_mask = os.path.join(LIGHTSOUT, name + '_mask.png')
    if not os.path.exists(src_png): return None
    d = os.path.join(ctx.out, rel); os.makedirs(d, exist_ok=True)
    shutil.copy(src_png, os.path.join(d, name + '.png'))
    has_mask = os.path.exists(src_mask)
    if has_mask: shutil.copy(src_mask, os.path.join(d, name + '_mask.png'))
    open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write(f'''// {name}: CS:GO decal (Valve) as a CS2 static overlay, from the ba_jail_lightsout import (AI-generated file)
Layer0
{{
	shader "csgo_static_overlay.vfx"
	F_BLEND_MODE 1
	g_flModelTintAmount "1.000"
	g_fTextureColorBrightness "{BRIGHT.get(group, 0.4):.3f}"
	g_fTextureColorContrast "1.000"
	g_fTextureColorSaturation "1.000"
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "{rel}/{name}.png"
	g_bFogEnabled "1"
	g_nTextureAddressModeU "1"
	g_nTextureAddressModeV "1"
	g_flOpacityScale "1.000"
	{('TextureTranslucency "%s/%s_mask.png"' % (rel, name)) if has_mask else ''}
}}
''')
    ctx.decals_done.add(name)
    return vmat


def tex_aspect(name):
    try:
        from PIL import Image
        w, h = Image.open(os.path.join(LIGHTSOUT, name + '.png')).size; return w / h
    except Exception:
        return 1.0


# ---------------------------------------------------------------- quads
def wall_quad(ctx, mat, wall, along, z, w, h, off=0.6, flip=False):
    """a decal on a wall. wall = (origin point on the wall, yaw of the inward normal, step unit vector along the wall);
    along = distance along the wall of the decal centre; z = centre height; w x h in units. UVs 0..1 (u along the wall)."""
    (ox, oy, oz), yaw, (sx, sy) = wall[:3]
    nx, ny = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))      # inward normal
    cx, cy = ox + sx * along + nx * off, oy + sy * along + ny * off
    hw, hh = w / 2, h / 2
    # corners so the face points inward (counter-clockwise seen from the room)
    a = (cx - sx * hw, cy - sy * hw, z - hh); b = (cx + sx * hw, cy + sy * hw, z - hh)
    c = (cx + sx * hw, cy + sy * hw, z + hh); d = (cx - sx * hw, cy - sy * hw, z + hh)
    verts = [a, b, c, d]
    # the face normal of (a,b,c,d) is step x up = (sx,sy,0) x (0,0,1) = (sy, -sx, 0); we want it = inward normal
    if sy * nx - sx * ny < 0: verts = [b, a, d, c]
    uvs = [(0, 1), (1, 1), (1, 0), (0, 0)] if not flip else [(1, 1), (0, 1), (0, 0), (1, 0)]
    ctx.quad(verts, mat, uvs)


def floor_quad(ctx, mat, cx, cy, w, h, yaw_deg, z=0.4):
    """a decal flat on the floor, facing up, turned by yaw"""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    def P(u, v):
        return (cx + u * c - v * s, cy + u * s + v * c, z)
    hw, hh = w / 2, h / 2
    verts = [P(-hw, -hh), P(hw, -hh), P(hw, hh), P(-hw, hh)]       # counter-clockwise seen from above (+z)
    ctx.quad(verts, mat, [(0, 1), (1, 1), (1, 0), (0, 0)])


# ---------------------------------------------------------------- room-local placement
class Spots:
    def __init__(self, box, rng):
        self.b = box; self.rng = rng; self.taken = []   # (x, y, r)
    def block(self, x, y, r): self.taken.append((x, y, r))
    def free(self, x, y, r):
        b = self.b
        if x - r < b[0] + 4 or x + r > b[3] - 4 or y - r < b[1] + 4 or y + r > b[4] - 4: return False
        return all(math.hypot(x - tx, y - ty) >= r + tr for tx, ty, tr in self.taken)
    def near_wall(self, r, tries=30, inset=None):
        """a free spot close to a random wall; returns (x, y, wall index, yaw facing into the room)"""
        b = self.b; inset = inset if inset is not None else r + 6
        for _ in range(tries):
            w = self.rng.randrange(4)
            if w == 0: x, y, yaw = b[0] + inset, self.rng.uniform(b[1] + 64, b[4] - 64), 0
            elif w == 1: x, y, yaw = b[3] - inset, self.rng.uniform(b[1] + 64, b[4] - 64), 180
            elif w == 2: x, y, yaw = self.rng.uniform(b[0] + 64, b[3] - 64), b[1] + inset, 90
            else: x, y, yaw = self.rng.uniform(b[0] + 64, b[3] - 64), b[4] - inset, 270
            if self.free(x, y, r): self.block(x, y, r); return x, y, w, yaw
        return None
    def anywhere(self, r, tries=30, margin=96):
        b = self.b
        for _ in range(tries):
            x, y = self.rng.uniform(b[0] + margin, b[3] - margin), self.rng.uniform(b[1] + margin, b[4] - margin)
            if self.free(x, y, r): self.block(x, y, r); return x, y
        return None
    def corner(self, r, k=None):
        b = self.b; cs = [(b[0] + r + 8, b[1] + r + 8), (b[3] - r - 8, b[1] + r + 8), (b[0] + r + 8, b[4] - r - 8), (b[3] - r - 8, b[4] - r - 8)]
        order = [k] if k is not None else self.rng.sample(range(4), 4)
        for i in order:
            x, y = cs[i]
            if self.free(x, y, r): self.block(x, y, r); return x, y, i
        return None


def wall_list(box):
    """(origin, yaw of inward normal, unit step along the wall, length) for each wall, same convention as vmap.wall_runs"""
    x0, y0, z0, x1, y1, z1 = box
    return [((x0, y0, z0), 0, (0, 1), y1 - y0), ((x1, y1, z0), 180, (0, -1), y1 - y0), ((x1, y0, z0), 90, (-1, 0), x1 - x0), ((x0, y1, z0), 270, (1, 0), x1 - x0)]


def wall_point(wall, along, proud, z):
    (ox, oy, oz), yaw, (sx, sy), L = wall
    nx, ny = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (ox + sx * along + nx * proud, oy + sy * along + ny * proud, z)


# ---------------------------------------------------------------- the passes
def graffiti_pass(ctx, rng, box, n_graffiti=5, n_stains=4, panel_offsets=(-256, 256), avoid=120, zrange=(100, 180), tag='vault'):
    walls = wall_list(box)
    placed = 0
    for _ in range(n_graffiti * 3):
        if placed >= n_graffiti: break
        w = rng.choice(walls); L = w[3]
        along = rng.uniform(80, L - 80)
        if any(abs(along - (L / 2 + o)) < avoid for o in panel_offsets): continue
        name = rng.choice(GRAFFITI); mat = decal_mat(ctx, name, 'graffiti')
        if not mat: continue
        asp = tex_aspect(name); h = rng.uniform(56, 104) if asp < 1.6 else rng.uniform(40, 72); wdt = h * asp
        wall_quad(ctx, mat, w, along, rng.uniform(*zrange), min(wdt, 320), h)
        placed += 1
    for _ in range(n_stains):
        w = rng.choice(walls); L = w[3]
        name = rng.choice(STAINS + DRIPS); mat = decal_mat(ctx, name, 'stain')
        if not mat: continue
        asp = tex_aspect(name); h = rng.uniform(60, 120); drip = name in DRIPS
        wall_quad(ctx, mat, w, rng.uniform(60, L - 60), 48 + h / 2 if not drip else 200 + rng.uniform(-20, 30), min(h * asp, 200), h)


def floor_pass(ctx, rng, S, n_trash=3, n_debris=2, n_puddles=2, n_leaves=1, rugs=0):
    for _ in range(n_trash):
        p = S.anywhere(40, margin=80)
        if not p: continue
        name = rng.choice(FLOOR_TRASH); mat = decal_mat(ctx, name, 'floor')
        if mat: floor_quad(ctx, mat, p[0], p[1], rng.uniform(80, 140), rng.uniform(80, 140), rng.uniform(0, 360))
        S.taken.pop()   # decals don't block props
    for _ in range(n_debris):
        p = S.anywhere(40, margin=60)
        if not p: continue
        name = rng.choice(FLOOR_DEBRIS); mat = decal_mat(ctx, name, 'floor')
        if mat: floor_quad(ctx, mat, p[0], p[1], rng.uniform(96, 180), rng.uniform(96, 180), rng.uniform(0, 360))
        S.taken.pop()
    for _ in range(n_puddles):
        p = S.anywhere(60, margin=100)
        if not p: continue
        floor_quad(ctx, PUDDLE, p[0], p[1], rng.uniform(110, 200), rng.uniform(90, 160), rng.uniform(0, 360), z=0.3)
        S.taken.pop()
    for _ in range(n_leaves):
        p = S.anywhere(40, margin=60)
        if not p: continue
        name = rng.choice(LEAVES); mat = decal_mat(ctx, name, 'floor')
        if mat: floor_quad(ctx, mat, p[0], p[1], rng.uniform(100, 160), rng.uniform(100, 160), rng.uniform(0, 360), z=0.5)
        S.taken.pop()
    for _ in range(rugs):
        p = S.anywhere(70, margin=160)
        if not p: continue
        name = rng.choice(RUGS); mat = decal_mat(ctx, name, 'rug')
        asp = tex_aspect(name)
        if mat: floor_quad(ctx, mat, p[0], p[1], 120 * asp, 120, rng.choice([0, 90]), z=0.6)


def plant_pass(ctx, rng, box, S, pillars, n_wall_ivy=2, n_pillar_ivy=None, n_hang=2, n_grass=2, n_tufts=5, n_vines=2):
    walls = wall_list(box)
    x0, y0, z0, x1, y1, z1 = box
    for _ in range(n_wall_ivy):
        w = rng.choice(walls); along = rng.uniform(120, w[3] - 120)
        p = wall_point(w, along, 0, rng.uniform(90, 150))
        ctx.prop(rng.choice(IVY_WALL), p, w[1], solid='0', bake='0')
    pil = list(pillars); rng.shuffle(pil)
    k = n_pillar_ivy if n_pillar_ivy is not None else max(1, len(pil) // 3)
    for (px, py) in pil[:k]:
        ctx.prop(rng.choice(IVY_PILLAR), (px, py, 0), rng.uniform(0, 360), solid='0', bake='0')
    for _ in range(n_hang):
        w = rng.choice(walls); along = rng.uniform(120, w[3] - 120)
        p = wall_point(w, along, 2, z1 - rng.uniform(8, 40))
        ctx.prop(rng.choice(IVY_HANG), p, w[1] + rng.uniform(-20, 20), solid='0', bake='0')
    for _ in range(n_grass):
        c = S.corner(56)
        if c: ctx.prop(rng.choice(GRASS_PACK), (c[0], c[1], 0), rng.uniform(0, 360), solid='0', bake='0')
    for _ in range(n_tufts):
        sp = S.near_wall(16, inset=rng.uniform(14, 40))
        if sp: ctx.prop(GRASS_TUFT, (sp[0], sp[1], 0), rng.uniform(0, 360), solid='0', bake='0'); S.taken.pop()
    for _ in range(n_vines):
        x, y = rng.uniform(x0 + 100, x1 - 100), rng.uniform(y0 + 100, y1 - 100)
        ctx.prop(VINES, (x, y, z1 - 16), rng.uniform(0, 360), solid='0', bake='0')


def clutter_pass(ctx, rng, S, dais=None, n_candles=3, n_pots=3, n_piles=1, n_market=1, n_debris=1, n_small=3, n_rugs=1):
    corners = []
    if dais:
        h = dais['half']; corners = [(dais['cx'] + sx * (h - 18), dais['cy'] + sy * (h - 18), dais['h']) for sx in (-1, 1) for sy in (-1, 1)]
        rng.shuffle(corners)
    for i in range(n_candles):
        if corners: x, y, z = corners.pop(); ctx.prop(rng.choice(CANDLE_CLUSTER), (x, y, z), rng.uniform(0, 360), solid='0', bake='0')
        else:
            sp = S.near_wall(14, inset=rng.uniform(16, 28))
            if sp: ctx.prop(rng.choice(CANDLE_CLUSTER if rng.random() < 0.5 else CANDLE), (sp[0], sp[1], 0), rng.uniform(0, 360), solid='0', bake='0')
    for _ in range(n_pots):
        sp = S.near_wall(14, inset=rng.uniform(18, 36))
        if sp: ctx.prop(rng.choice(BOWLS + VASES), (sp[0], sp[1], 0), rng.uniform(0, 360), solid='0', bake='0')
    for _ in range(n_piles):
        c = S.corner(36)
        if c: ctx.prop(rng.choice(STONE_PILES), (c[0], c[1], 0), rng.uniform(0, 360), solid='6', bake='0')
    for _ in range(n_market):
        sp = S.near_wall(28, inset=rng.uniform(30, 44))
        if sp: ctx.prop(rng.choice(MARKET), (sp[0], sp[1], 0), sp[3] + rng.uniform(-30, 30), solid='6', bake='0')
    for _ in range(n_debris):
        sp = S.near_wall(64, inset=rng.uniform(40, 60))
        if sp: ctx.prop(DEBRIS_PILE, (sp[0], sp[1], 0), sp[3] + 90 + rng.uniform(-15, 15), solid='0', bake='0')
    for _ in range(n_small):
        p = S.anywhere(10, margin=48)
        if p: ctx.prop(rng.choice(DEBRIS_SMALL + STONE_SINGLE + TRASH_FLAT), (p[0], p[1], 0), rng.uniform(0, 360), solid='0', bake='0'); S.taken.pop()
    for _ in range(n_rugs):
        if dais:
            side = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            x, y = dais['cx'] + side[0] * (dais['half'] + 70), dais['cy'] + side[1] * (dais['half'] + 70)
            if S.free(x, y, 50): S.block(x, y, 50); ctx.prop(RUG, (x, y, 0.5), 90 if side[0] else 0, solid='0', bake='0')
        else:
            p = S.anywhere(56, margin=140)
            if p: ctx.prop(RUG, (p[0], p[1], 0.5), rng.choice([0, 90]), solid='0', bake='0')


def cyber_pass(ctx, rng, box, panel_offsets=(-256, 256), monitors=2, wire_runs=2, exhibit=2, z_panel=160, lights=True):
    """the nanite infusion: wall monitors on the carved panels, exhibit lights pooling onto them, cable runs under the conduit"""
    walls = wall_list(box)
    x0, y0, z0, x1, y1, z1 = box
    spots = [(w, w[3] / 2 + o) for w in walls for o in panel_offsets]; rng.shuffle(spots)
    for (w, along) in spots[:monitors]:
        p = wall_point(w, along + rng.uniform(-60, 60), 22, z_panel + rng.uniform(20, 50))
        ctx.prop(WALL_MONITOR, p, w[1] + 90, solid='0', bake='0')       # the monitor's +y is its back: turn it to face the room
    for (w, along) in spots[monitors:monitors + exhibit]:
        p = wall_point(w, along, 10, z_panel + 100)
        ctx.prop(EXHIBIT_LIGHT, p, w[1], solid='0', bake='0')
        if lights:
            lp = wall_point(w, along, 26, z_panel + 92)
            ctx.lamp(lp, 260, 230, color='255 236 200', shadows=False, baked_only=True)
    for _ in range(wire_runs):
        w = rng.choice(walls); L = w[3]
        n = rng.randrange(4, 9); start = rng.uniform(40, L - 40 - n * 32); z = 76 + rng.uniform(0, 12)
        for k in range(n):
            p = wall_point(w, start + (k + 1) * 32, 2.5, z)
            ctx.prop(rng.choice(WIRE32), p, w[1] + 90, solid='0', bake='0')


# ---------------------------------------------------------------- per area
def vault(ctx, rm, pillars_placed):
    """rm: layout room dict. Density: a AAA pass, not a sprinkle."""
    rng = random.Random(1000 + rm['id'])
    b = rm['box']; S = Spots(b, rng)
    for (x, y) in rm['pillars']: S.block(x, y, 60)
    for (x, y) in rm['blocks']: S.block(x, y, 72)
    if rm['dais']: S.block(rm['dais']['cx'], rm['dais']['cy'], rm['dais']['half'] * 1.42 + 20)
    for (x, y) in rm['statues']: S.block(x, y, 60)
    S.block(rm['entry'][0], rm['entry'][1], 140); S.block(rm['exit'][0], rm['exit'][1], 140)
    k = rm['kind']
    graffiti_pass(ctx, rng, b, n_graffiti=4 if k != 'archive' else 6, n_stains=4)
    floor_pass(ctx, rng, S, n_trash=2 if k in ('shrine', 'garden') else 3, n_debris=3 if k == 'ruin' else 2, n_puddles=3 if k == 'garden' else 2, n_leaves=2 if k == 'garden' else 1)
    if k == 'garden':
        plant_pass(ctx, rng, b, S, rm['pillars'], n_wall_ivy=5, n_pillar_ivy=len(rm['pillars']), n_hang=5, n_grass=4, n_tufts=12, n_vines=5)
        clutter_pass(ctx, rng, S, rm['dais'], n_candles=4, n_pots=5, n_piles=1, n_market=0, n_debris=1, n_small=4, n_rugs=0)
        cyber_pass(ctx, rng, b, monitors=1, wire_runs=1, exhibit=1)
    elif k == 'archive':
        plant_pass(ctx, rng, b, S, rm['pillars'], n_wall_ivy=1, n_pillar_ivy=0, n_hang=1, n_grass=0, n_tufts=2, n_vines=1)
        # server racks along one wall, monitors on crates, holo panels by the pillars
        w = wall_list(b)[rng.randrange(4)]
        for i in range(4):
            p = wall_point(w, 160 + i * 96, 30, 48)
            if S.free(p[0], p[1], 30): S.block(p[0], p[1], 30); ctx.prop(SERVER, p, w[1], solid='6', bake='0')
        for _ in range(3):
            sp = S.near_wall(30, inset=40)
            if sp:
                ctx.prop(CRATE_ANCIENT, (sp[0], sp[1], 0), sp[3] + 90, solid='6', bake='0')
                ctx.prop(rng.choice(RETRO_MONITOR), (sp[0], sp[1], 26.6), sp[3] + rng.uniform(-25, 25), solid='0', bake='0')
        for (px, py) in rm['pillars'][:4]:
            x, y = px + rng.choice([-1, 1]) * 70, py + rng.choice([-1, 1]) * 70
            if S.free(x, y, 24): S.block(x, y, 24); ctx.prop(HOLO_PANEL, (x, y, 0), rng.uniform(0, 360), solid='6', bake='0')
        clutter_pass(ctx, rng, S, rm['dais'], n_candles=1, n_pots=1, n_piles=0, n_market=0, n_debris=0, n_small=3, n_rugs=0)
        for _ in range(3):
            sp = S.near_wall(20, inset=30)
            if sp: ctx.prop(rng.choice(JUNK), (sp[0], sp[1], 0), rng.uniform(0, 360), solid='0', bake='0')
        cyber_pass(ctx, rng, b, monitors=4, wire_runs=5, exhibit=3)
    elif k == 'ruin':
        plant_pass(ctx, rng, b, S, rm['pillars'], n_wall_ivy=3, n_hang=3, n_grass=2, n_tufts=6, n_vines=3)
        c = S.corner(70)
        if c: ctx.prop(TOWER_RUIN, (c[0], c[1], 0), rng.choice([0, 90, 180, 270]), solid='6', bake='0')
        clutter_pass(ctx, rng, S, rm['dais'], n_candles=2, n_pots=2, n_piles=3, n_market=0, n_debris=2, n_small=6, n_rugs=0)
        for _ in range(2):
            p = S.anywhere(40, margin=120)
            if p:
                name = rng.choice(BLOOD); mat = decal_mat(ctx, name, 'blood')
                if mat: floor_quad(ctx, mat, p[0], p[1], 72, 72, rng.uniform(0, 360), z=0.7)
                S.taken.pop()
        cyber_pass(ctx, rng, b, monitors=1, wire_runs=2, exhibit=2)
    elif k == 'shrine':
        plant_pass(ctx, rng, b, S, rm['pillars'], n_wall_ivy=2, n_hang=2, n_grass=1, n_tufts=4, n_vines=2)
        clutter_pass(ctx, rng, S, rm['dais'], n_candles=4, n_pots=4, n_piles=1, n_market=1, n_debris=0, n_small=3, n_rugs=2)
        for (x, y, z) in [(rm['dais']['cx'] + sx * (rm['dais']['half'] + 40), rm['dais']['cy'] + sy * (rm['dais']['half'] + 40), 0) for sx in (-1, 1) for sy in (-1, 1)]:
            if S.free(x, y, 16): S.block(x, y, 16); ctx.prop(STATUE_SMALL, (x, y, z), math.degrees(math.atan2(rm['dais']['cy'] - y, rm['dais']['cx'] - x)), solid='6', bake='0')
        for (px, py) in rm['pillars']:
            ctx.prop(LANTERN, (px + 50, py, 140), 0, solid='0', bake='0')
        cyber_pass(ctx, rng, b, monitors=2, wire_runs=2, exhibit=2)
    else:
        plant_pass(ctx, rng, b, S, rm['pillars'], n_wall_ivy=2, n_hang=2, n_grass=2, n_tufts=5, n_vines=2)
        clutter_pass(ctx, rng, S, rm['dais'], n_candles=3, n_pots=3, n_piles=1, n_market=1, n_debris=1, n_small=4, n_rugs=1)
        cyber_pass(ctx, rng, b, monitors=2, wire_runs=3, exhibit=2)
        if k == 'ring':
            for (px, py) in rm['pillars'][::2]: ctx.prop(LANTERN, (px, py, 272 - 8), 0, solid='0', bake='0')
    return S


def lobby(ctx, L, spawn_rows):
    rng = random.Random(77); b = L['box']; S = Spots(b, rng)
    cx, cy = L['cx'], L['cy']
    for (x, y) in spawn_rows: S.block(x, y, 24)
    S.block(cx, cy, 120)
    ctx.prop(FOUNTAIN, (cx, cy, 0), 0, solid='6', bake='0')
    ctx.prop(BANNERS, (cx, cy, 150), 0, solid='0', bake='0')
    for sx in (-1, 1):
        for sy in (-1, 1): S.block(cx + sx * 512, cy + sy * 512, 60)
    # class kiosks: four exhibition panels around the fountain (the HUD class picker stands here later)
    for i, (dx, dy) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        x, y = cx + dx * 260, cy + dy * 260
        S.block(x, y, 30); ctx.prop(HOLO_PANEL, (x, y, 0), math.degrees(math.atan2(dy, dx)) + 180, solid='6', bake='0')
        ctx.prop(INFO_PANEL, (x + dy * 70, y - dx * 70, 0), math.degrees(math.atan2(dy, dx)) + 180, solid='6', bake='0')
    graffiti_pass(ctx, rng, b, n_graffiti=6, n_stains=5, panel_offsets=(-384, 0, 384))
    floor_pass(ctx, rng, S, n_trash=3, n_debris=2, n_puddles=3, n_leaves=2, rugs=2)
    plant_pass(ctx, rng, b, S, [(cx + sx * 512, cy + sy * 512) for sx in (-1, 1) for sy in (-1, 1)], n_wall_ivy=6, n_pillar_ivy=4, n_hang=6, n_grass=4, n_tufts=10, n_vines=4)
    clutter_pass(ctx, rng, S, None, n_candles=6, n_pots=6, n_piles=2, n_market=3, n_debris=1, n_small=5, n_rugs=2)
    cyber_pass(ctx, rng, b, panel_offsets=(-384, 0, 384), monitors=4, wire_runs=4, exhibit=4, z_panel=160)


def staging(ctx, st):
    rng = random.Random(500 + st['id']); b = st['box']; S = Spots(b, rng)
    S.block(st['pad'][0], st['pad'][1], 90)
    x0, y0, z0, x1, y1, z1 = b
    S.block(x0 + 30, y0 + 64, 32); S.block(x0 + 30, y1 - 64, 32)
    graffiti_pass(ctx, rng, b, n_graffiti=3, n_stains=3, panel_offsets=(), zrange=(90, 150))
    floor_pass(ctx, rng, S, n_trash=2, n_debris=1, n_puddles=1, n_leaves=0)
    for _ in range(4):
        sp = S.near_wall(22, inset=28)
        if sp: ctx.prop(rng.choice(JUNK), (sp[0], sp[1], 0), rng.uniform(0, 360), solid='0', bake='0')
    sp = S.near_wall(30, inset=40)
    if sp:
        ctx.prop(CRATE_ANCIENT, (sp[0], sp[1], 0), sp[3] + 90, solid='6', bake='0')
        ctx.prop(rng.choice(RETRO_MONITOR), (sp[0], sp[1], 26.6), sp[3] + rng.uniform(-20, 20), solid='0', bake='0')
    plant_pass(ctx, rng, b, S, [], n_wall_ivy=1, n_pillar_ivy=0, n_hang=1, n_grass=0, n_tufts=2, n_vines=1)
    clutter_pass(ctx, rng, S, None, n_candles=1, n_pots=1, n_piles=0, n_market=1, n_debris=0, n_small=2, n_rugs=0)
    cyber_pass(ctx, rng, b, panel_offsets=(-96, 96), monitors=2, wire_runs=3, exhibit=1, z_panel=130)


def arena(ctx, A):
    rng = random.Random(9000); b = A['box']; S = Spots(b, rng)
    cx, cy = A['cx'], A['cy']
    S.block(cx, cy, 1024 * 1.42 + 40)
    for bal in A['balconies']: S.block(bal['pad'][0], bal['pad'][1], 300)
    for (x, y) in A['blocks']: S.block(x, y, 72)
    # ruined towers in the four corners, broken pillars and stone piles along the walls
    for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = cx + sx * (A['w'] / 2 - 140), cy + sy * (A['d'] / 2 - 140)
        S.block(x, y, 90); ctx.prop(TOWER_RUIN, (x, y, 0), rng.choice([0, 90, 180, 270]), solid='6', bake='0')
    for _ in range(6):
        sp = S.near_wall(40, inset=120)
        if sp: ctx.prop(PILLAR_BROKEN, (sp[0], sp[1], 0), rng.uniform(0, 360), solid='6', bake='0')
    for _ in range(8):
        sp = S.near_wall(40, inset=rng.uniform(60, 200))
        if sp: ctx.prop(rng.choice(STONE_PILES), (sp[0], sp[1], 0), rng.uniform(0, 360), solid='6', bake='0')
    graffiti_pass(ctx, rng, b, n_graffiti=12, n_stains=10, panel_offsets=(-1152, -384, 384, 1152), zrange=(110, 220))
    floor_pass(ctx, rng, S, n_trash=6, n_debris=6, n_puddles=6, n_leaves=3)
    plant_pass(ctx, rng, b, S, A['dais_pillars'], n_wall_ivy=10, n_pillar_ivy=2, n_hang=8, n_grass=6, n_tufts=16, n_vines=0)
    # grass and candles along the tier edge, lanterns on the balconies, banners over the dais
    for i in range(12):
        a = i / 12 * math.pi * 2; r = 1024 + 40
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        x = max(cx - 1024 - 40, min(cx + 1024 + 40, x)); y = max(cy - 1024 - 40, min(cy + 1024 + 40, y))
        if S.free(x, y, 30): S.block(x, y, 30); ctx.prop(rng.choice(GRASS_PACK if i % 3 else CANDLE_CLUSTER), (x, y, 0), rng.uniform(0, 360), solid='0', bake='0')
    for bal in A['balconies']:
        bx0, by0, bz0, bx1, by1, bz1 = bal['box']
        for (x, y) in ((bx0 + 24, by0 + 24), (bx1 - 24, by1 - 24)):
            ctx.prop(rng.choice(CANDLE_CLUSTER), (x, y, bz1), rng.uniform(0, 360), solid='0', bake='0')
        ctx.prop(LANTERN, ((bx0 + bx1) / 2, (by0 + by1) / 2, bz1 + 150), 0, solid='0', bake='0')
    ctx.prop(BANNERS, (cx, cy, A['box'][5] - 150), 0, solid='0', bake='0')
    ctx.prop(BANNERS, (cx, cy, A['box'][5] - 190), 90, solid='0', bake='0')
    clutter_pass(ctx, rng, S, None, n_candles=6, n_pots=8, n_piles=0, n_market=4, n_debris=4, n_small=12, n_rugs=0)
    cyber_pass(ctx, rng, b, panel_offsets=(-1152, -384, 384, 1152), monitors=6, wire_runs=8, exhibit=6, z_panel=200)
