"""IRONFRAME weapon props: one prop per weapon part key in data/parts.json -> out/addon/models/ifr/weapons/<key>.vmdl, recorded in
out/addon/_gen/models.json#weapons. Props a script attaches at the frame's hardpoints: forward (muzzle) = +x, origin at the centre.

Sources: the Armored Core model pack's guns and units (frames.json alt_item 3708956431) through create/mdl2cs2.py (--yaw long,
--origin center, --length per family: rifles ~90 u, cannons ~140 u, for a medium frame's hand). Families without a source are plain
box props written directly (geo + modelio, flat csgo_complex paint, an emissive edge on the blade) so the game is buildable; the
Titanfall Titan weapon packs (frames.json weapon_props.items, extracted under <work>/extract) are the upgrade path (TITAN table below,
--titan converts them in place of the boxes).

Every slot now has a real source in SOURCES (Titan packs, AC packs, XCOM MEC weapons, DOOM Atlan weapons, ...); the boxes remain only as a
fallback when a source fails. data/weapons.json {key: {source, status}} is the review state (tools/review_weapons.py,
docs/WEAPON_REVIEW.md): models.json gets only `approved` keys unless --all is passed (build_all.sh passes it until skink52 approves).

Pivots (10 Nov 2026): mdl2cs2 centres each prop on its bounds; repivot() then moves the model origin to the GRIP (arm weapons: where the
hand closes, fractions of the bounds in GRIPS) or the MOUNT BASE (shoulder units: bottom centre), the point the game script puts on the
frame's palm / shoulder mount (out/addon/_gen/models.json#mounts, written by tools/weapon_fit.py). Idempotent: a second run moves 0.
--repivot re-pivots the existing SMDs only (no reconversion) and compiles the ones that moved.

usage: python -I tools/weapon_props.py [--only key,..] [--no-compile] [--all] [--preview] [--repivot]
"""
import glob, json, os, subprocess, sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.join(os.path.dirname(os.path.dirname(PROJ)), 'create')
sys.path.insert(0, HERE); sys.path.insert(0, CREATE); sys.path.insert(0, os.path.join(CREATE, 'playermodels'))
import geo, modelio, fx_models                                # noqa: E402
import frames as FR                                           # noqa: E402

OUT = os.path.join(PROJ, 'out', 'addon')
REL_M, REL_T = 'models/ifr/weapons', 'materials/ifr/weapons'
AC_PACK = 3708956431
# part key -> source. item = Workshop id (data/frames.json weapon_props.item_info), mdl = path inside the extracted item, length = the prop's
# longest side in u for a 288 u medium frame, args = extra mdl2cs2 flags (--only-parts / --only-bones / --bodygroup / --skin / --yaw).
# Muzzle +X, origin = bounding-box centre (the game script offsets to the grip). The 'W' helper keeps the table readable.
E_ = 'models/ac4/ene/'
W = lambda item, mdl, length, what, *args: dict(item=item, mdl=mdl, length=length, what=what, args=list(args))
SOURCES = {
    # --- hand weapons (arm)
    'rifle':       W(AC_PACK, 'models/naki/ac4a/right gun.mdl', 120, 'White Glint rifle'),
    'laser':       W(AC_PACK, 'models/naki/ac4a/left gun.mdl', 110, 'White Glint left-hand gun'),
    'rail':        W(AC_PACK, 'models/naki/ac4/right gun.mdl', 140, '03-AALIYAH right gun (long rifle)'),
    'bazooka':     W(AC_PACK, 'models/naki/ac4/left gun.mdl', 150, '03-AALIYAH left gun'),
    'gatling':     W(3309731444, 'models/jijia/jiatlein.mdl', 140, 'Titanfall 2 Legion Predator cannon'),
    'smg':         W(268095616, 'models/weapons/xotbr16/w_xotbr16.mdl', 100, 'Titan XO-16 chaingun (compact scale)'),
    'shotgun':     W(268097317, 'models/weapons/titan_shotgun_wys_0404/w_titan_shotgun_wys0404.mdl', 110, 'Titan shotgun (WYS-0404)'),
    'grenade':     W(268095616, 'models/weapons/titan_triple_threat/w_titan_triple_threat.mdl', 120, 'Titan Triple Threat grenade launcher'),
    'handmsl':     W(268097317, 'models/weapons/titan_rocket_launcher/titan_rocket_launcher.mdl', 150, 'Titan quad rocket launcher'),
    'plasma':      W(904418924, 'models/minic23/xcom/mec/mec_particlebeam.mdl', 110, 'XCOM MEC particle beam'),
    'blade':       W(3309731444, 'models/jijia/ronindao.mdl', 190, 'Titanfall 2 Ronin broadsword', '--yaw', 'long180'),
    'shield':      W(3492397241, 'models/doomthedarkages/weapons_titan/shield.mdl', 180, 'DOOM Dark Ages Atlan shield (untextured grey in the source)', '--yaw', '90'),
    'pilebunker':  W(3772907723, E_ + 'enemy_algebra_seljq_left_hand_weapon.mdl', 130, 'AC4 Seljuq twin pile bunker'),
    'sniper':      W(268095616, 'models/weapons/titan_sniper_rifle/w_titan_sniper_rifle.mdl', 190, 'Titan sniper rifle'),
    'burstrifle':  W(268093486, 'models/weapons/thr_40mm/w_thr_40mm.mdl', 140, 'Titan 40 mm tracker cannon'),
    'flamer':      W(904418924, 'models/minic23/xcom/mec/mec_flamethrower.mdl', 110, 'XCOM MEC flamethrower', '--yaw', 'long180'),
    'eshotgun':    W(268093486, 'models/weapons/titan_arc_rifle/w_titan_arc_rifle.mdl', 120, 'Titan arc rifle'),
    'heavyblade':  W(3492397241, 'models/doomthedarkages/weapons_titan/sword.mdl', 230, 'DOOM Dark Ages Atlan sword (untextured grey in the source)', '--yaw', 'long180'),
    # --- shoulder units
    'lasercannon':   W(904418924, 'models/minic23/xcom/mec/mec_railgun.mdl', 160, 'XCOM MEC rail gun'),
    'grenadecannon': W(AC_PACK, 'models/naki/ac4/aaliyah.mdl', 150, '03-AALIYAH back cannon', '--only-parts', 'back cannon'),
    'autocannon':    W(3738530795, 'models/ac4/ene/enemy_rayleonard_00_aretha_right_hand_weapon.mdl', 150, 'AC4 00-ARETHA six-barrel gatling'),
    'vm6':           W(3772907723, E_ + 'enemy_ga_gam3_solarwind_left_shoulder_weapon.mdl', 110, 'AC4 Solar Wind shoulder missile pack'),
    'dualmsl':       W(3772907723, E_ + 'enemy_ga_gam3_solarwind_shoulder_weapons.mdl', 150, 'AC4 Solar Wind twin missile packs'),
    'vm12':          W(3549564685, 'models/ac4/garage/ac_berlioz_supplice_shoulder_left_weapon.mdl', 140, 'AC4 Berlioz shoulder missile launcher'),
    'multimsl':      W(3460036871, 'models/ac4/garage/ac_oldking_lisa_right_back_weapon.mdl', 140, 'AC For Answer Old King back missile container'),
    'flak':          W(3460036871, 'models/ac4/garage/ac_oldking_lisa_left_back_weapon_deployed.mdl', 150, 'AC For Answer Old King back autocannon'),
    'clusterart':    W(3549564685, 'models/ac4/garage/ac_berlioz_supplice_right_back_weapon_deployed.mdl', 160, 'AC4 Berlioz long back cannon'),
    'pulseshield':   W(904418924, 'models/minic23/xcom/mec/mec_electropulse_mark3.mdl', 100, 'XCOM MEC electro-pulse emitter'),
    'repair':        W(904418924, 'models/minic23/xcom/mec/mec_medkit_mark2.mdl', 100, 'XCOM MEC medkit module'),
    'decoy':         W(3497937577, 'models/ac4/garage/ac_abemarsh_whiteglint_right_back_weapon.mdl', 90, 'AC For Answer White Glint back unit'),
    'minelayer':     W(904418924, 'models/minic23/xcom/mec/mec_minelauncher_mark3.mdl', 100, 'XCOM MEC mine launcher'),
    'orbitdrones':   W(1563865814, 'models/kss/mirrorsedgecatalyst/ksec_drones/kss_mec_drone_hunter_x3.mdl', 130, "Mirror's Edge Catalyst hunter drone trio"),
}
# grip / mount base as fractions of the prop's bounds (x 0 = rear, 1 = muzzle; y 0.5 = centre line; z 0 = bottom), picked on the side views
# (10 Nov 2026 side views; laser / smg / burstrifle / grenade / sniper / shotgun moved off the magazine onto the grip behind it). Arm: the top of the pistol grip / fore-grip, where a fist closes; blades at the hilt; the shield by its back
# face (it sits in front of the hand). Shoulder: bottom centre of the unit (the mount bracket where it has one).
G = lambda fx, fz, fy=0.5: (fx, fy, fz)
GRIPS = {
    'rifle': G(0.22, 0.30), 'gatling': G(0.30, 0.25), 'shotgun': G(0.35, 0.25), 'laser': G(0.23, 0.35), 'bazooka': G(0.30, 0.35),
    'grenade': G(0.33, 0.25), 'blade': G(0.08, 0.50), 'plasma': G(0.20, 0.30), 'rail': G(0.20, 0.28), 'handmsl': G(0.30, 0.35),
    'shield': G(0.0, 0.50), 'smg': G(0.33, 0.30), 'pilebunker': G(0.25, 0.50), 'sniper': G(0.33, 0.25), 'burstrifle': G(0.29, 0.30),
    'flamer': G(0.35, 0.35), 'eshotgun': G(0.55, 0.30), 'heavyblade': G(0.18, 0.50),
}
MOUNT_BASE = G(0.5, 0.0)            # every shoulder unit
TITAN = {}          # kept so old callers import; the Titan models are in SOURCES now
GREY, DARK, OLIVE, WHITE = (108, 112, 118), (42, 44, 48), (84, 92, 72), (184, 186, 180)
# box props: (parts: (sx, sy, sz, centre, colour) or ('tube', p0, p1, r, colour), glow rgb for 'edge' parts or None)
B = lambda sx, sy, sz, c, col=GREY: ('box', sx, sy, sz, c, col)
T = lambda p0, p1, r, col=GREY: ('tube', p0, p1, r, col)
BOXES = {
    'gatling':   ([B(60, 16, 18, (-15, 0, 0), DARK), T((10, 0, 0), (55, 0, 0), 5.5, GREY), T((10, 0, 4), (50, 0, 4), 2.2, DARK), T((10, 3.5, -2), (50, 3.5, -2), 2.2, DARK), T((10, -3.5, -2), (50, -3.5, -2), 2.2, DARK)], None),
    'shotgun':   ([B(50, 12, 16, (-10, 0, 0), DARK), T((10, 0, 2), (40, 0, 2), 4.0, GREY), B(18, 8, 10, (-30, 0, -10), GREY)], None),
    'smg':       ([B(40, 10, 14, (-8, 0, 0), DARK), T((10, 0, 2), (36, 0, 2), 2.6, GREY), B(8, 6, 16, (-12, 0, -12), GREY)], None),
    'grenade':   ([B(44, 16, 18, (-12, 0, 0), OLIVE), T((8, 0, 0), (42, 0, 0), 7.0, DARK), B(16, 8, 12, (-28, 0, -12), GREY)], None),
    'plasma':    ([B(56, 14, 18, (-10, 0, 0), WHITE), T((14, 0, 2), (46, 0, 2), 5.0, DARK), B(20, 18, 6, (-6, 0, 12), DARK, ), ('edge', 24, 2.5, 3, (20, 0, 10))], (90, 200, 255)),
    'handmsl':   ([B(70, 30, 30, (-10, 0, 0), OLIVE), T((25, -8, 8), (45, -8, 8), 5.5, DARK), T((25, 8, 8), (45, 8, 8), 5.5, DARK), T((25, -8, -8), (45, -8, -8), 5.5, DARK), T((25, 8, -8), (45, 8, -8), 5.5, DARK)], None),
    'blade':     ([B(26, 7, 9, (-50, 0, 0), DARK), B(10, 9, 12, (-36, 0, 0)), B(92, 2.2, 13, (12, 0, 0)), ('edge', 92, 2.6, 2.2, (12, 0, 7.2)), ('edge', 10, 3.0, 13, (59, 0, 0))], (255, 120, 60)),
    'shield':    ([B(6, 90, 90, (0, 0, 0), WHITE), B(10, 40, 14, (-6, 0, 30), DARK), B(10, 40, 14, (-6, 0, -30), DARK), ('edge', 3, 12, 60, (3.5, 0, 0))], (90, 180, 255)),
    'vm6':       ([B(60, 40, 30, (0, 0, 0), OLIVE), B(54, 36, 3, (0, 0, 16), DARK), B(18, 40, 8, (-18, 0, -18))], None),
    'vm12':      ([B(80, 52, 32, (0, 0, 0), OLIVE), B(74, 48, 3, (0, 0, 17), DARK), B(24, 52, 8, (-24, 0, -19))], None),
    'dualmsl':   ([B(40, 36, 14, (-10, 0, -8), OLIVE), T((-35, -10, 2), (35, -10, 2), 9), T((-35, 10, 2), (35, 10, 2), 9), T((34, -10, 2), (36, -10, 2), 9.6, DARK), T((34, 10, 2), (36, 10, 2), 9.6, DARK)], None),
    'flak':      ([B(50, 36, 30, (-10, 0, 0), OLIVE), B(24, 40, 10, (0, 0, 16), DARK), T((14, -8, 4), (60, -8, 4), 3.8), T((14, 8, 4), (60, 8, 4), 3.8), T((14, 0, 4), (34, 0, 4), 7, DARK)], None),
    'pulseshield': ([B(30, 44, 50, (0, 0, 0), WHITE), T((0, -18, 25), (0, -18, 48), 2.2, DARK), T((0, 18, 25), (0, 18, 48), 2.2, DARK), ('edge', 6, 6, 4, (0, -18, 50)), ('edge', 6, 6, 4, (0, 18, 50)), ('edge', 24, 24, 3, (0, 0, 26))], (90, 200, 255)),
    'repair':    ([B(26, 40, 44, (0, 0, 0), WHITE), T((14, -11, -16), (14, -11, 18), 6), T((14, 11, -16), (14, 11, 18), 6), ('edge', 2, 20, 6, (13.5, 0, 10)), ('edge', 2, 6, 20, (13.5, 0, 10))], (80, 255, 120)),
    'decoy':     ([B(24, 36, 26, (0, 0, 0), OLIVE), B(20, 30, 3, (0, 0, 14), DARK), B(6, 36, 6, (-14, 0, -8))], None),
}


# ---------------------------------------------------------------- grips
def grip_point(key, kind, P):
    """the grip (arm: GRIPS fractions) / mount base (shoulder: MOUNT_BASE) of weapon `key` from its mesh points P (n,3), prop frame
    (+x muzzle). After repivot() this is the model origin (within rounding); tools/weapon_fit.py measures it from the mesh either way."""
    P = np.asarray(P, float); lo, hi = P.min(0), P.max(0)
    f = np.array(GRIPS.get(key, (0.33, 0.5, 0.3)) if kind == 'arm' else MOUNT_BASE)
    return lo + f * (hi - lo), ('grip %.2f / %.2f' % (f[0], f[2])) if kind == 'arm' else 'mount base'


def flat_vmat(name, rgb, rough=0.55, metal=0.5, glow=None):
    d = os.path.join(OUT, REL_T, 'proc'); os.makedirs(d, exist_ok=True)
    Image.new('RGB', (4, 4), tuple(rgb)).save(os.path.join(d, name + '_color.png'))
    Image.new('L', (4, 4), int(rough * 255)).save(os.path.join(d, name + '_rough.png'))
    rel = '%s/proc' % REL_T
    lines = ['// IRONFRAME procedural weapon prop (generated)', 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1',
             '\tTextureColor "%s/%s_color.png"' % (rel, name), '\tg_flModelTintAmount "1.000"', '\tTextureNormal "materials/default/default_normal.tga"',
             '\tTextureRoughness "%s/%s_rough.png"' % (rel, name), '\tg_flMetalness "%.3f"' % metal]
    if glow:
        Image.new('L', (4, 4), 255).save(os.path.join(d, 'glow_mask.png'))
        lines += ['\tF_SELF_ILLUM 1', '\tTextureSelfIllumMask "%s/glow_mask.png"' % rel, '\tg_flSelfIllumScale "1.000"', '\tg_flSelfIllumBrightness "14.000"',
                  '\tg_flSelfIllumAlbedoFactor "1.000"', '\tg_vSelfIllumTint "[%.3f %.3f %.3f 0.000000]"' % tuple(c / 255.0 for c in glow)]
    lines.append('}')
    open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return '%s/%s.vmat' % (rel, name)


def build_box(key):
    parts, glow = BOXES[key]
    groups = {}                                  # material name -> mesh
    for p in parts:
        if p[0] == 'box': _, sx, sy, sz, c, col = p; m = geo.rbox(sx, sy, sz, r=min(1.2, sx / 3, sy / 3, sz / 3), seg=1, mat='m', center=c); mat = 'c%02x%02x%02x' % col
        elif p[0] == 'tube': _, p0, p1, r, col = p; m = geo.tube([p0, p1], [r, r], sides=10, mat='m'); mat = 'c%02x%02x%02x' % col
        else: _, sx, sy, sz, c = p; m = geo.rbox(sx, sy, sz, r=0.4, seg=1, mat='m', center=c); mat = 'edge'
        groups[mat] = fx_models.merge([groups[mat], m]) if mat in groups else m
    d = os.path.join(OUT, REL_M, key); os.makedirs(d, exist_ok=True)
    lines = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    remaps = []; allV = []
    for mat, m in groups.items():
        rgb = tuple(int(mat[1 + 2 * i:3 + 2 * i], 16) for i in range(3)) if mat != 'edge' else glow
        vm = flat_vmat('%s_%s' % (key, mat), rgb if mat != 'edge' else tuple(min(255, int(c * 0.6)) for c in glow), glow=glow if mat == 'edge' else None)
        remaps.append(('%s_%s.vmat' % (key, mat), vm)); allV.append(m.V)
        uv = m.V[:, [0, 2]] / 32.0
        for f in m.F:
            lines.append('%s_%s.vmat' % (key, mat))
            for i in f:
                x, y, z = m.V[i]; nx, ny, nz = m.N[i]
                lines.append("0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f" % (y, -x, z, ny, -nx, nz, uv[i, 0], 1 - uv[i, 1]))
    lines.append("end")
    open(os.path.join(d, key + '.smd'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    V = np.vstack(allV); lo, hi = V.min(0), V.max(0)
    modelio.write_hull_smd(os.path.join(d, key + '_hull.smd'), [np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])])
    txt = modelio.vmdl_text(key, '%s/%s' % (REL_M, key), [key], remaps, [key + '_hull'], surface='metal', archetype='', entity='prop_dynamic', single_lod=True)
    vp = '%s/%s.vmdl' % (REL_M, key)
    open(os.path.join(OUT, vp.replace('/', os.sep)), 'w', newline='\n').write(txt)
    return dict(vmdl=vp, tris=[sum(len(m.F) for m in groups.values())], bounds=[lo.round(1).tolist(), hi.round(1).tolist()], source='procedural box')


def convert_source(key, src, p, preview):
    root = os.path.join(p['work'], 'extract', str(src['item']))
    if not glob.glob(os.path.join(root, 'models', '**', '*.mdl'), recursive=True):
        root = FR.extract(p, src['item'])
        if root is None: raise RuntimeError('item %s not downloaded' % src['item'])
    mdl = os.path.join(root, src['mdl'])
    if not os.path.exists(mdl): raise RuntimeError('missing ' + src['mdl'])
    rep = os.path.join(p['work'], 'reports', 'w_%s.json' % key)
    cmd = [sys.executable, '-X', 'utf8', '-I', os.path.join(CREATE, 'mdl2cs2.py'), mdl, OUT, key, '--sub', REL_M, '--matsub', '%s/%s' % (REL_T, key),
           '--length', str(src['length']), '--yaw', 'long', '--origin', 'center', '--dynamic', '--report', rep,
           '--credit', 'GMod Workshop port, see docs/CREDITS.md'] + list(src.get('args', []))
    if preview:
        os.makedirs(os.path.join(PROJ, 'preview', 'weapons'), exist_ok=True); cmd += ['--preview', os.path.join(PROJ, 'preview', 'weapons', key + '.png')]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    tail = '\n'.join((r.stdout + r.stderr).strip().splitlines()[-5:])
    if r.returncode != 0: raise RuntimeError('mdl2cs2 failed: ' + tail[-300:])
    R = json.load(open(rep, encoding='utf-8')); mi = R['models']['model']
    return dict(vmdl=mi['vmdl'], tris=mi['tris'], bounds=mi['bounds'], source='%s: %s' % (src['item'], src['mdl']), what=src['what'], item=src['item'],
                yaw_how=R.get('yaw_how'), warnings=R.get('warnings', []))


def smd_files(vmdl_rel):
    """every SMD a weapon vmdl references (LODs + hull), main mesh first"""
    import re
    txt = open(os.path.join(OUT, vmdl_rel.replace('/', os.sep)), encoding='utf-8').read()
    return [os.path.join(OUT, f.replace('/', os.sep)) for f in dict.fromkeys(re.findall(r'filename = "([^"]+\.smd)"', txt))]


def smd_bounds(path):
    """model-frame (x muzzle, y left, z up) bounds of an SMD's triangles"""
    L = open(path, encoding='utf-8', errors='replace').read().split('\n'); i = L.index('triangles') + 1; P = []
    while i < len(L) and L[i].strip() != 'end':
        for k in range(3):
            t = L[i + 1 + k].split(); P.append((-float(t[2]), float(t[1]), float(t[3])))
        i += 4
    P = np.array(P); return P.min(0), P.max(0)


def repivot(key, kind, vmdl_rel):
    """move the model origin to the grip (arm) / mount base (shoulder). Returns (model-frame shift applied, new bounds); the shift is 0
    when the origin is already there. Every SMD of the vmdl moves by the shift the main mesh fixes (LODs and hull stay in register)."""
    files = smd_files(vmdl_rel)
    if not files: return None, None
    lo, hi = smd_bounds(files[0])
    f = np.array(GRIPS.get(key, (0.5, 0.5, 0.5)) if kind == 'arm' else MOUNT_BASE)
    g = lo + f * (hi - lo)
    if np.abs(g).max() < 0.05: return [0.0, 0.0, 0.0], [lo.round(1).tolist(), hi.round(1).tolist()]
    sx, sy, sz = g[1], -g[0], g[2]                      # the shift in the SMD's own (y, -x, z) frame
    for path in files:
        L = open(path, encoding='utf-8', errors='replace').read().split('\n'); i = L.index('triangles') + 1
        while i < len(L) and L[i].strip() != 'end':
            for k in range(3):
                t = L[i + 1 + k].split()
                t[1] = '%.4f' % (float(t[1]) - sx); t[2] = '%.4f' % (float(t[2]) - sy); t[3] = '%.4f' % (float(t[3]) - sz)
                L[i + 1 + k] = ' '.join(t)
            i += 4
        open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(L))
    return g.round(2).tolist(), [(lo - g).round(1).tolist(), (hi - g).round(1).tolist()]


def repivot_only(keys, kinds, compile_, p, state, state_path):
    """--repivot: re-pivot the existing converted SMDs, compile the moved ones, update the state bounds"""
    res_all = state.setdefault('weapons', {}); moved = []
    for key in keys:
        r = res_all.get(key, {})
        if not r.get('ok'): print('%-14s not built' % key); continue
        shift, b = repivot(key, kinds[key], r['vmdl'])
        if shift is None: print('%-14s no SMDs' % key); continue
        r['bounds'] = b; r['pivot'] = 'grip' if kinds[key] == 'arm' else 'mount base'
        vc = os.path.join(FR.GAME, r['vmdl'].replace('/', os.sep) + '_c')       # compiled copy older than the SMD: recompile it too
        stale = not os.path.exists(vc) or os.path.getmtime(vc) < os.path.getmtime(smd_files(r['vmdl'])[0])
        if any(abs(v) >= 0.05 for v in shift) or stale: moved.append(key)
        print('%-14s shift %s  bounds %s' % (key, shift, b), flush=True)
    failed = []
    FR.save_state(state_path, state, ('weapons',))
    if compile_ and moved:
        vm = [res_all[k]['vmdl'] for k in moved]
        cres = FR.compile_models(OUT, [REL_M, REL_T], vm, os.path.join(p['work'], 'logs', 'rc_weapons.log'))
        for k in moved:
            ok, s_, pr = cres[res_all[k]['vmdl']]; res_all[k]['compiled'] = {'ok': ok, 'seconds': s_, 'problems': pr}
            print('compile %-14s %s %.1fs %s' % (k, 'ok' if ok else 'FAIL', s_, '; '.join(pr)[:160]), flush=True)
            if not ok: failed.append(k)
        FR.save_state(state_path, state, ('weapons',))
    print('%d re-pivoted, %d compile failures%s' % (len(moved), len(failed), (': ' + ', '.join(failed)) if failed else ''))
    return 1 if failed else 0


def main():
    args = sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    compile_, preview, all_ = '--no-compile' not in args, '--preview' in args, '--all' in args
    cat = json.load(open(os.path.join(PROJ, 'data', 'frames.json'), encoding='utf-8'))
    parts = json.load(open(os.path.join(PROJ, 'data', 'parts.json'), encoding='utf-8'))
    p = dict(cat['paths']); p['work'] = os.environ.get('IF_WORK', p['work'])
    for d in (os.path.join(OUT, REL_M), os.path.join(p['work'], 'reports'), os.path.join(p['work'], 'logs')): os.makedirs(d, exist_ok=True)
    keys = [x['key'] for x in parts['parts'] if x.get('kind') in ('arm', 'shoulder')]
    kinds = {x['key']: x['kind'] for x in parts['parts'] if x.get('kind') in ('arm', 'shoulder')}
    if only: keys = [k for k in keys if k in only]
    state_path = os.path.join(p['work'], 'state.json')
    state = json.load(open(state_path, encoding='utf-8')) if os.path.exists(state_path) else {}
    if '--repivot' in args: return repivot_only(keys, kinds, compile_, p, state, state_path)
    res_all = state.setdefault('weapons', {})
    failed = []
    for key in keys:
        t = time.time(); res = None
        src = SOURCES.get(key)
        try:
            if src:
                try: res = convert_source(key, src, p, preview)
                except Exception as e:
                    print('%-14s source failed (%s), box instead' % (key, str(e)[:160]))
            if res is None and key in BOXES: res = build_box(key)
            if res is None: raise RuntimeError('no source and no box spec')
            shift, b = repivot(key, kinds[key], res['vmdl'])        # origin -> grip / mount base (the script's contract)
            if b: res['bounds'] = b; res['pivot'] = 'grip' if kinds[key] == 'arm' else 'mount base'
            res['ok'] = True
            print('%-14s %-40s tris %s  %.0fs  %s' % (key, res['vmdl'], res['tris'], time.time() - t, res.get('what', res['source'])), flush=True)
        except Exception as e:
            res = {'ok': False, 'error': str(e)[:400]}; failed.append(key); print('%-14s FAILED: %s' % (key, res['error']))
        res_all[key] = res
    FR.save_state(state_path, state, ('weapons',))
    if compile_:
        vmdls = [res_all[k]['vmdl'] for k in keys if res_all.get(k, {}).get('ok')]
        cres = FR.compile_models(OUT, [REL_M, REL_T], vmdls, os.path.join(p['work'], 'logs', 'rc_weapons.log'))
        for k in keys:
            r = res_all.get(k, {})
            if r.get('ok') and r['vmdl'] in cres:
                ok, s, pr = cres[r['vmdl']]; r['compiled'] = {'ok': ok, 'seconds': s, 'problems': pr}
                if not ok: failed.append(k); print('compile %-14s FAIL %s' % (k, '; '.join(pr)[:200]))
        FR.save_state(state_path, state, ('weapons',))
    mpath = os.path.join(OUT, '_gen', 'models.json'); os.makedirs(os.path.dirname(mpath), exist_ok=True)
    data = json.load(open(mpath, encoding='utf-8')) if os.path.exists(mpath) else {}
    data.setdefault('frames', {}); data.setdefault('fx', {})
    wpath = os.path.join(PROJ, 'data', 'weapons.json')
    wj = json.load(open(wpath, encoding='utf-8')) if os.path.exists(wpath) else {}
    for k, r in res_all.items():
        if k in keys and r.get('ok'):
            e = wj.setdefault(k, {}); e['source'] = r['source']; e['status'] = e.get('status', 'review')
            for f in ('item', 'what'):
                if r.get(f) is not None: e[f] = r[f]
                else: e.pop(f, None)
    json.dump(dict(sorted(wj.items())), open(wpath, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    data['weapons'] = {k: r['vmdl'] for k, r in res_all.items() if r.get('ok') and (r.get('compiled', {}).get('ok', True)) and (all_ or wj.get(k, {}).get('status') == 'approved')}
    json.dump(data, open(mpath, 'w', encoding='utf-8'), indent=1)
    print('\n%d weapons in models.json (%d from the AC pack, %d boxes), %d failed%s' % (
        len(data['weapons']), sum(1 for r in res_all.values() if r.get('ok') and r.get('item')), sum(1 for r in res_all.values() if r.get('source') == 'procedural box'),
        len(failed), (': ' + ', '.join(failed)) if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
