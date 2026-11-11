"""mg_monsoon model table: ONE place that says which model stands for each logical thing (helicopter, howitzer, emplaced gun, truck,
foliage piece ...), its bounds and where its pivots are. Used by mv_places.py (static dressing), mv_entities.py (script props) and
layout.export() (the `models` block of out/layout.json, which the script reads instead of hard-coded seat / hub / trunnion numbers).

Each entry has an `ext` variant (a converted GMod Workshop model under models/mv/ext/, docs/ASSETS.md) and a `proc` variant (our
procedural prop from build_all_props.py). pick(name) returns the ext variant when its .vmdl is in the addon, else the procedural
one, so the map still builds on a machine without the Workshop conversions (and for a Steam Workshop release: set MV_NO_EXT=1).

Frames: every offset is in the MODEL's own space after conversion: +x nose / muzzle, +y left, +z up, origin on the ground under the
model (helicopters: under the main rotor mast) unless the note says otherwise. Units: Hammer units, 40 per metre.
Hip numbers were measured from the converted SMDs on 12 Nov 2026 (cabin floor z 30 from x -60 to 150, cockpit floor z 40 from
x 150 to 210, left door gun mesh x 115..124, y 30..72, z 56..67, UB-16 pods to x 57 at y +-83 / 104 / 124, z 35); the rotor and
tail hubs are the source bones (models/mv/ext/hip/hip_skeleton.json). Not compiled, not seen in game.
"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out'))
ADDON = os.environ.get('MV_OUT') or os.path.join(OUT, 'addon')


def mv(name):
    return 'models/mv/%s/%s.vmdl' % (name, name)


def ext(name, folder=None):
    return 'models/mv/ext/%s/%s.vmdl' % (folder or name, name)


def B(x0, y0, z0, x1, y1, z1):
    return ((x0, y0, z0), (x1, y1, z1))


# ---------------------------------------------------------------- bounds of the converted models (lo, hi); out/gmod_models.json wins
EXT_BOUNDS = {
    ext('hip_slick'): B(-517.3, -96.0, 0.0, 224.1, 98.0, 162.8), ext('hip_upper', 'hip'): B(-517.3, -133.9, 0.0, 224.0, 135.7, 162.8),
    ext('hip_rotor', 'hip'): B(-382.9, -371.7, -5.6, 416.3, 417.5, 36.3), ext('hip_tail', 'hip'): B(-64.6, -0.5, -75.2, 73.6, 7.5, 49.6),
    ext('m101'): B(-150.2, -69.2, 0.0, 41.6, 65.9, 70.6), ext('m101_gun'): B(-40.5, -9.1, -17.3, 99.1, 9.1, 17.7),
    ext('m2_tripod'): B(-30.9, -23.1, 0.0, 32.7, 28.0, 62.9), ext('m2_gun'): B(-28.6, -6.5, -4.8, 44.5, 19.9, 6.3),
    ext('dshk_tripod'): B(-27.2, -30.9, 0.0, 18.2, 31.2, 50.2), ext('dshk_gun'): B(-24.7, -3.6, -4.6, 48.3, 14.6, 14.9),
    ext('heli_wreck'): B(-217.0, -269.5, 0.0, 217.0, 308.5, 147.3), ext('heli_wreck_dyn', 'heli_wreck'): B(-217.0, -269.5, 0.0, 217.0, 308.5, 147.3),
    ext('m35'): B(-137.9, -56.8, 0.0, 141.0, 56.8, 122.3), ext('ural'): B(-153.9, -49.4, 0.0, 141.3, 49.4, 97.7),
    ext('m113'): B(-98.8, -51.1, 0.0, 95.2, 53.1, 129.7), ext('pbr'): B(-183.3, -70.0, 0.0, 196.1, 70.0, 159.0),
    ext('t54'): B(-133.6, -72.8, 0.0, 249.8, 72.8, 136.9), ext('m151'): B(-79.9, -41.1, 0.0, 63.4, 42.4, 59.5),
    ext('gaz69'): B(-85.2, -37.5, 0.0, 73.9, 37.5, 77.9), ext('bm21'): B(-134.8, -47.6, 0.0, 160.4, 48.4, 120.4),
    ext('zpu4'): B(-96.7, -36.5, 0.0, 70.3, 36.5, 75.0), ext('comm_station'): B(-41.8, -22.8, 0.0, 41.8, 22.4, 81.3),
    ext('nva_ammo_case'): B(-15.7, -35.3, 0.0, 15.2, 35.5, 15.1), ext('nva_ammo_case_open'): B(-28.4, -35.4, 0.0, 14.9, 35.4, 40.3),
    ext('sandbag_cover'): B(-69.8, -42.7, 0.0, 72.1, 42.4, 45.6),
    ext('rs_elephant_grass'): B(-82.2, -81.9, 0.0, 82.4, 79.1, 47.6), ext('rs_grass_set'): B(-57.3, -55.9, 0.0, 57.7, 57.1, 32.5),
    ext('rs_bamboo_bundle'): B(-159.5, -107.4, 0.0, 146.1, 121.1, 325.2), ext('rs_bamboo_wall'): B(-71.4, -56.4, 0.0, 70.6, 55.8, 124.4),
    ext('rs_jungle_tree'): B(-96.8, -71.3, 0.0, 80.0, 87.7, 294.6), ext('rs_jungle_palm'): B(-69.3, -70.5, 0.0, 93.0, 82.6, 317.9),
    ext('rs_coconut_palm'): B(-39.2, -54.6, 0.0, 77.8, 75.9, 271.1), ext('rs_nypa_palm'): B(-67.5, -41.2, 0.0, 54.7, 85.4, 107.1),
    ext('rs_mangrove'): B(-135.2, -97.2, 0.0, 126.9, 98.0, 215.2), ext('rs_taro'): B(-27.3, -109.0, 0.0, 26.4, 109.0, 42.4),
    ext('rs_ferns'): B(-70.7, -54.9, 0.0, 66.3, 66.2, 21.7), ext('rs_jungle_bush'): B(-58.0, -59.5, 0.0, 38.5, 38.4, 79.6),
    ext('rs_hedge'): B(-73.1, -182.3, 0.0, 73.1, 182.3, 103.7),
}

# ---------------------------------------------------------------- helicopters (seat / exit / pod / gun offsets in the model's nose frame)
_PK = dict(name='PK DOOR GUN', yaw=90, cone=60, up=25, down=60)
HELIS = {
    # Mi-8 slick (T pads 1, 2): pilot in the left cockpit seat, the PK in the open left door, four riders on the cabin floor
    'hip': dict(
        ext=dict(body=ext('hip_slick'), rotor=ext('hip_rotor', 'hip'), tail=ext('hip_tail', 'hip'), nose_yaw=0.0, rotor_r=418.0,
                 hub=(0.0, 0.0, 149.46), tail_hub=(-513.2, 22.21, 157.27), length=741.0,
                 seats=[('pilot', (176.0, 22.0, 56.0)), ('gunner', (119.0, 30.0, 46.0)), ('rider', (62.0, 22.0, 46.0)), ('rider', (62.0, -22.0, 46.0)),
                        ('rider', (4.0, 22.0, 46.0)), ('rider', (4.0, -22.0, 46.0))],
                 exits=[(119.0, 140.0, 0.0), (60.0, 140.0, 0.0), (180.0, 140.0, 0.0), (0.0, 140.0, 0.0), (-110.0, 140.0, 0.0), (-170.0, 140.0, 0.0)],
                 pods=[], gun=dict(_PK, muzzle=(119.5, 74.0, 61.5), cam=(119.0, 44.0, 78.0))),
        proc=dict(body=mv('heli_hip'), rotor=mv('rotor_hip'), tail=mv('tailrotor_hip'), nose_yaw=0.0, rotor_r=344.0,
                  hub=(-30.0, 0.0, 173.84), tail_hub=(-541.2, 16.0, 160.72), length=871.0,
                  seats=[('pilot', (215.0, 22.0, 52.0)), ('gunner', (128.0, 34.0, 46.0)), ('rider', (40.0, 22.0, 46.0)), ('rider', (40.0, -22.0, 46.0)),
                         ('rider', (-40.0, 22.0, 46.0)), ('rider', (-40.0, -22.0, 46.0))],
                  exits=[(128.0, 130.0, 0.0), (60.0, 130.0, 0.0), (190.0, 130.0, 0.0), (0.0, 130.0, 0.0), (-60.0, 130.0, 0.0), (-120.0, 130.0, 0.0)],
                  pods=[], gun=dict(_PK, muzzle=(128.0, 62.0, 80.0), cam=(128.0, 40.0, 96.0)))),
    # Mi-8 gunship (T pad 3): six UB-16 pods on outriggers, the same left door gun, two riders
    'hip_gun': dict(
        ext=dict(body=ext('hip_upper', 'hip'), rotor=ext('hip_rotor', 'hip'), tail=ext('hip_tail', 'hip'), nose_yaw=0.0, rotor_r=418.0,
                 hub=(0.0, 0.0, 149.46), tail_hub=(-513.2, 22.21, 157.27), length=741.0,
                 seats=[('pilot', (176.0, 22.0, 56.0)), ('gunner', (119.0, 30.0, 46.0)), ('rider', (62.0, 22.0, 46.0)), ('rider', (62.0, -22.0, 46.0))],
                 exits=[(119.0, 175.0, 0.0), (180.0, 175.0, 0.0), (60.0, 175.0, 0.0), (0.0, 175.0, 0.0)],
                 pods=[(57.0, 104.0, 35.0), (57.0, -104.0, 35.0), (57.0, 124.0, 35.0), (57.0, -124.0, 35.0), (57.0, 83.0, 35.0), (57.0, -83.0, 35.0)],
                 gun=dict(_PK, muzzle=(119.5, 74.0, 61.5), cam=(119.0, 44.0, 78.0))),
        proc=dict(body=mv('heli_hip_gun'), rotor=mv('rotor_hip'), tail=mv('tailrotor_hip'), nose_yaw=0.0, rotor_r=344.0,
                  hub=(-30.0, 0.0, 173.84), tail_hub=(-541.2, 16.0, 160.72), length=871.0,
                  seats=[('pilot', (215.0, 22.0, 52.0)), ('gunner', (128.0, 34.0, 46.0)), ('rider', (40.0, 22.0, 46.0)), ('rider', (40.0, -22.0, 46.0))],
                  exits=[(128.0, 130.0, 0.0), (60.0, 130.0, 0.0), (190.0, 130.0, 0.0), (0.0, 130.0, 0.0)],
                  pods=[(74.0, 95.0, 80.0), (74.0, -95.0, 80.0), (74.0, 125.0, 80.0), (74.0, -125.0, 80.0)],
                  gun=dict(_PK, muzzle=(128.0, 62.0, 80.0), cam=(128.0, 40.0, 96.0)))),
}
HELI_ON_PAD = dict(t=['hip', 'hip', 'hip_gun'], ct=['apache', 'apache', 'apache'])
APACHE_MODEL = 'models/vehicles/apache/apache.vmdl'

# ---------------------------------------------------------------- guns: carriage / stand (static part) + the part the script turns
GUNS = {
    # trunnion: where the tube's origin sits on the carriage; muzzle: distance from the trunnion to the muzzle along the bore
    'howitzer': dict(ext=dict(carriage=ext('m101'), tube=ext('m101_gun'), trunnion=(-18.73, 0.0, 40.22), muzzle=99.0, rest_pitch=-8.0, label='M101 105 MM'),
                     proc=dict(carriage=mv('howitzer_m102'), tube=mv('howitzer_m102_gun'), trunnion=(0.0, 0.0, 44.0), muzzle=152.0, rest_pitch=-8.0, label='M102 105 MM')),
    'rocket': dict(proc=dict(carriage=mv('rocket_tripod'), tube=mv('rocket_rail'), round=mv('rocket_122'), trunnion=(0.0, 0.0, 46.0), round_up=8.0, muzzle=60.0,
                             rest_pitch=-20.0, label='GRAD-P 122 MM')),
    # pintle: the gun part's origin on its stand; seat_back: where the gunner stands behind the pintle; muzzle: pintle to muzzle
    'm2': dict(ext=dict(stand=ext('m2_tripod'), gun=ext('m2_gun'), pintle=(0.0, 0.0, 62.9), muzzle=44.5, seat_back=60.0, cover_r=56.0),
               proc=dict(stand=mv('m3_tripod'), gun=mv('m2_gun'), pintle=(0.0, 0.0, 30.0), muzzle=64.0, seat_back=58.0, cover_r=56.0)),
    'dshk': dict(ext=dict(stand=ext('dshk_tripod'), gun=ext('dshk_gun'), pintle=(-4.06, 0.0, 48.77), muzzle=48.3, seat_back=60.0, cover_r=56.0),
                 proc=dict(stand=mv('dshk_mount'), gun=mv('dshk_gun'), pintle=(0.0, 0.0, 58.0), muzzle=82.0, seat_back=86.0, cover_r=76.0)),
    'quad50': dict(proc=dict(stand=mv('quad50_mount'), gun=mv('quad50_gun'), pintle=(0.0, 0.0, 66.0), muzzle=64.0, seat_back=150.0, cover_r=118.0)),
}

# ---------------------------------------------------------------- static dressing: logical name -> (ext model or None, procedural prop or None, note)
STATIC = {
    'wreck_t': (ext('heli_wreck_dyn', 'heli_wreck'), mv('wreck_hip'), 'crash hulk (prop_dynamic). ext: burnt light helicopter, long axis y: yaw +90 on the nose'),
    'wreck_ct': (ext('heli_wreck_dyn', 'heli_wreck'), mv('wreck_huey'), 'crash hulk (prop_dynamic), as wreck_t'),
    'truck_us': (ext('m35'), mv('truck_wreck'), 'M35 body, NO wheels (the addon never merged them): only as a stripped hulk sitting on its axles'),
    'truck_nva': (ext('ural'), mv('truck_wreck'), 'Ural cargo truck on its wheels'),
    'apc': (ext('m113'), mv('m113_hulk'), 'intact M113; origin on the ground'),
    'pbr': (ext('pbr'), mv('pbr_wreck'), 'ext: intact PBR, origin = keel (floats: z = water - PBR_DRAFT). proc: wreck, origin on the river bed'),
    'jeep_us': (ext('m151'), None, 'M151 MUTT'), 'jeep_nva': (ext('gaz69'), None, 'GAZ-69'),
    'bm21': (ext('bm21'), None, 'BM-21 on Ural-375, launcher fixed forward (out of period: camp dressing only)'),
    'zpu4': (ext('zpu4'), None, 'ZPU-4, one piece'), 't54': (ext('t54'), None, 'T-54 with DShK'),
    'comm_station': (ext('comm_station'), mv('radio_prc25'), 'crate with radio sets and a whip antenna'),
    'ammo_case_nva': (ext('nva_ammo_case'), mv('ammo_crate'), 'long axis y'), 'ammo_case_nva_open': (ext('nva_ammo_case_open'), mv('ammo_crate'), 'lid open, empty; long axis y'),
    'sandbag_cover': (ext('sandbag_cover'), None, 'horseshoe of sandbags 46 high, CLOSED toward -y, open toward +y: yaw = facing + 90; one convex hull (the inside is solid)'),
    'tent': (None, mv('gp_tent'), 'ours kept: sandbag skirt and the same canvas as the rest of the base; ext tent_gp is a closed tent with guy ropes (unused)'),
    'tower': (None, mv('guard_tower'), 'ours kept (fixed 12 Nov); ext wood_tower reads medieval (unused)'),
    'grass_tall': (ext('rs_elephant_grass'), mv('elephant_grass_a'), 'ext is 48 u high: scale 2 - 2.5'), 'grass_low': (ext('rs_grass_set'), None, 'ground cover patch'),
    'bamboo': (ext('rs_bamboo_bundle'), mv('bamboo_clump'), ''), 'bamboo_thicket': (ext('rs_bamboo_wall'), None, ''),
    'tree_small': (ext('rs_jungle_tree'), None, ''), 'palm_jungle': (ext('rs_jungle_palm'), None, ''), 'palm_coconut': (ext('rs_coconut_palm'), None, ''),
    'palm_nypa': (ext('rs_nypa_palm'), None, ''), 'mangrove': (ext('rs_mangrove'), mv('root_tangle'), ''), 'taro': (ext('rs_taro'), None, 'a row along y'),
    'ferns': (ext('rs_ferns'), None, ''), 'bush': (ext('rs_jungle_bush'), None, ''), 'hedge': (ext('rs_hedge'), None, 'earth bank with shrubs, long axis y'),
}
PBR_DRAFT = 20.0
# trunk radius (placer footprint and the player clip) of the ext trees; their own hull is one convex blob, so they are placed non-solid
TRUNK = {ext('rs_jungle_tree'): 9.0, ext('rs_jungle_palm'): 9.0, ext('rs_coconut_palm'): 8.0, ext('rs_bamboo_bundle'): 60.0, ext('rs_mangrove'): 50.0}
# converted models deliberately not used by the map (docs/ASSETS.md has the reasons; the files stay in out/addon)
UNUSED = {'hind': 'out of theatre', 'huey': 'the CT side flies the CC-BY Apache', 'lssc_boat': 'one boat on the marsh is enough', 'pbr_mcv': '30 % over scale; pbr used',
          'm114_howitzer': 'one-piece 155 mm, no pit for it', 'm40_rr': 'no position designed for it', 'm60_gun': 'door mount not modelled on the Apache',
          'mortar_m1': 'facing unchecked', 'rocket_grad': 'full-length 9M22 does not fit the Grad-P rail; ours kept', 'skyraider': '66k triangles, intact (optional)',
          'tent_gp': 'gp_tent kept', 'wood_tower': 'guard_tower kept', 'sandbag_fort': 'one convex hull: the roofed inside would be an invisible solid',
          'w_ak47': 'weapon work later', 'w_m14': 'weapon work later', 'w_m60': 'weapon work later', 'w_m79': 'weapon work later', 'w_rpg7': 'weapon work later'}


# ---------------------------------------------------------------- choosing
def have(model, addon=None):
    """is this model's .vmdl in the addon content (MV_NO_EXT=1 hides every converted model)"""
    if '/ext/' in model and os.environ.get('MV_NO_EXT'): return False
    return os.path.isfile(os.path.join(addon or ADDON, model.replace('/', os.sep)))


def pick(name, addon=None):
    """the active variant dict of a helicopter or gun (ext when all its models are in the addon, else procedural), with 'variant'"""
    e = HELIS.get(name) or GUNS[name]
    v = e.get('ext')
    if v is not None and all(have(m, addon) for m in v.values() if isinstance(m, str) and m.endswith('.vmdl')):
        return dict(v, variant='ext')
    if 'proc' not in e: raise KeyError('%s: converted model missing and no procedural fallback' % name)
    return dict(e['proc'], variant='proc')


def static(name, addon=None):
    """model path for a piece of static dressing, or None when neither variant exists (the caller skips it)"""
    e, p, _ = STATIC[name]
    if e is not None and have(e, addon): return e
    return p


def is_ext(model):
    return bool(model) and '/ext/' in model


def bounds_table():
    """{model: (lo, hi)} for every converted model, exact numbers from out/gmod_models.json when it is there"""
    t = dict(EXT_BOUNDS)
    p = os.path.join(OUT, 'gmod_models.json')
    if os.path.isfile(p):
        try:
            for k, v in json.load(open(p)).items():
                if isinstance(v, dict) and v.get('model') and v.get('bounds'): t[v['model']] = (tuple(v['bounds'][0]), tuple(v['bounds'][1]))
        except Exception as ex: print('mv_models: gmod_models.json ignored (%s)' % ex)
    t[ext('heli_wreck_dyn', 'heli_wreck')] = t[ext('heli_wreck')]
    return t


def ensure_dyn(addon=None):
    """heli_wreck is converted as a static prop; the script moves the crash hulk, so write a prop_dynamic twin (model_archetype "")
    beside it. Returns the path written or None."""
    addon = addon or ADDON
    src = os.path.join(addon, ext('heli_wreck').replace('/', os.sep)); dst = os.path.join(addon, ext('heli_wreck_dyn', 'heli_wreck').replace('/', os.sep))
    if not os.path.isfile(src): return None
    s = open(src, encoding='utf-8').read()
    if 'model_archetype = "static_prop_model"' not in s: return None
    s = s.replace('model_archetype = "static_prop_model"', 'model_archetype = ""').replace('primary_associated_entity = "prop_static"', 'primary_associated_entity = "prop_dynamic"')
    if not os.path.isfile(dst) or open(dst, encoding='utf-8').read() != s:
        open(dst, 'w', encoding='utf-8', newline='\n').write(s)
    return dst


def apache(out=None):
    """the Apache block from out/apache.json (tools/apache_setup.py), in the same shape as a HELIS variant; None without the file"""
    p = os.path.join(out or OUT, 'apache.json')
    if not os.path.isfile(p): return None
    a = json.load(open(p)); s = a.get('seats', {})
    seats = [(k, tuple(s[n])) for k, n in (('pilot', 'pilot_fwd'), ('gunner', 'gunner_fwd'), ('rider', 'wing_left_fwd'), ('rider', 'wing_right_fwd')) if n in s]
    hub = a.get('rotor_hub', [0, 0, 156.5]); ny = float(a.get('nose_yaw', -90.0))
    return dict(variant='apache.json', body=a.get('model', APACHE_MODEL), nose_yaw=ny, rotor_r=float(a.get('rotor_radius', 303.0)), hub=(0.0, 0.0, float(hub[2])),
                length=float(a.get('body_length', 592.0)), animated=True, anims=dict(off='idle', slow='spin_slow', full='spin'), seats=seats,
                exits=[(40.0, 150.0, 0.0), (40.0, -150.0, 0.0), (-60.0, 170.0, 0.0), (-60.0, -170.0, 0.0)],
                pods=[tuple(q['muzzle_fwd']) for q in a.get('rocket_pods', []) if 'muzzle_fwd' in q],
                gun=dict(name='M230 30 MM', yaw=0, cone=110, up=15, down=60, muzzle=tuple(a.get('gun', {}).get('muzzle_fwd', (153.0, 0.0, 27.2))), cam=(118.0, 0.0, 74.0)),
                scale=float(a.get('scale', 1.0)))


def export(addon=None, out=None):
    """the `models` block of layout.json: what the script needs to know about the models the map was built with"""
    r3 = lambda v: [round(float(c), 2) for c in v]
    def heli(v):
        d = dict(variant=v['variant'], model=v['body'], nose_yaw=v['nose_yaw'], rotor_r=v['rotor_r'], hub=r3(v['hub']), length=v['length'],
                 seats=[dict(kind=k, off=r3(o)) for k, o in v['seats']], exits=[r3(e) for e in v['exits']], pods=[r3(p) for p in v['pods']],
                 gun=dict(v['gun'], muzzle=r3(v['gun']['muzzle']), cam=r3(v['gun']['cam'])))
        if 'tail_hub' in v: d['tail_hub'] = r3(v['tail_hub']); d['rotor'] = v['rotor']; d['tail'] = v['tail']
        if v.get('animated'): d['animated'] = True; d['anims'] = v['anims']
        return d
    m = {}
    for k in HELIS: m[k] = heli(pick(k, addon))
    a = apache(out)
    if a is not None: m['apache'] = heli(a)
    for k in GUNS:
        v = pick(k, addon); d = dict(variant=v['variant'], muzzle=v['muzzle'])
        for key in ('trunnion', 'pintle'):
            if key in v: d[key] = r3(v[key])
        for key in ('seat_back', 'rest_pitch', 'round_up', 'label'):
            if key in v: d[key] = v[key]
        d['model'] = v.get('tube') or v.get('gun'); d['base'] = v.get('carriage') or v.get('stand')
        m[k] = d
    w = static('wreck_t', addon)
    m['wreck'] = dict(t=w, ct=static('wreck_ct', addon), yaw=90.0 if is_ext(w) else 0.0)
    m['pads'] = HELI_ON_PAD
    return m


def unused_ext(vmap_models, addon=None):
    """converted model folders under models/mv/ext that the map does not reference: [(folder, reason)]"""
    root = os.path.join(addon or ADDON, 'models', 'mv', 'ext')
    used = {m.split('/')[3] for m in vmap_models if m.startswith('models/mv/ext/')}
    return [(f, UNUSED.get(f, '')) for f in sorted(os.listdir(root)) if f not in used] if os.path.isdir(root) else []


if __name__ == '__main__':
    print(json.dumps(export(), indent=1))
