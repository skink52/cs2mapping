"""mg_trenchwarfare model swap table (remaster step 6): for each map slot, the model it uses, the fallback, the fix-ups a swap needs, the
archetype, and the turntable comparisons the choice was made from. Reads models from the staging tree (out/addon) and the content addon
(read only); writes renders under out/step6/ and nothing else. tools/patch_models.py applies SWAPS to the map.

usage: python tools/tw_models.py table                     the swap table as text + out/step6/tw_models.json
       python tools/tw_models.py compare [slot,slot]       out/step6/turntables/<slot>.png: current (left) vs candidate(s), 3 views each
       python tools/tw_models.py view <model.vmdl> [...]   out/step6/turntables/<name>.png: one model from 4 sides (rebuilt props)
       python tools/tw_models.py weapons [gewehr98,mondragon,lewis]   out/step6/turntables/weapon_<key>.png: ours, stock, scale overlay, candidates
       python tools/tw_models.py check                      every chosen / fallback model exists (staged or in the content addon)

Renders: create/smd_view.py's software rasteriser with a fixed sun (Lambert, two-sided) so form reads; textures from the vmats (ours as
PNGs; stock Valve materials decoded from pak01 with create/vtexread.py into a cache). Same scale and camera for both sides of a pair.
Level: "looked at in a software render" (docs/reference/compatibility.md); nothing here is compiled.
"""
import json, math, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path[:] = [os.path.join(REPO, 'create')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import smd_view            # noqa: E402

CONTENT = os.environ.get('TW_CONTENT', r'C:\source1\links\content_addons\mg_trenchwarfare')
STAGE = os.path.join(PROJ, 'out', 'addon')
OUT = os.path.join(PROJ, 'out', 'step6')
CACHE = os.environ.get('TW_STOCK_CACHE', r'C:\source1\gmod_assets\trenchwarfare\stock_tex')
M = lambda n: 'models/tw/%s/%s.vmdl' % (n, n.split('/')[-1])

# ---------------------------------------------------------------------------------------------------------------- the swap table
# slot: the model the map uses today (key of the prop entities). chosen: what the map should use after step 6. fallback: what to put
# back if the chosen model is missing or must not ship (Workshop build). fix: scale / origin / rotation fix-ups applied to the entity on
# a swap (none needed when chosen == slot). archetype: static (prop_static, static_prop_model) or dynamic (prop_dynamic, model_archetype "").
# owner_rule: only tw_gen instances are swapped; tw_user / ungrouped are listed for the user (patch_models.py).
SWAPS = {
    # aircraft (script-moved: prop_dynamic on *_dyn twins; the parked statics on the airfields use the static model)
    'plane_spad7':      dict(slot=M('ext/plane_spad7'), chosen=M('ext/plane_spad7'), fallback=M('ext/plane_spad7'), archetype='static+dyn twin',
                             decision='keep', candidates=['gm_camel', 'gm_spad13']),
    'plane_dr1':        dict(slot=M('ext/plane_dr1'), chosen=M('ext/plane_dr1'), fallback=M('ext/plane_dr1'), archetype='static+dyn twin',
                             decision='keep', candidates=[]),
    # armour
    'tank_renault_ft':  dict(slot=M('ext/tank_renault_ft'), chosen=M('ext/tank_renault_ft'), fallback=M('wreck_tank'), archetype='static',
                             decision='keep', candidates=['gm_ft_female']),
    'tank_a7v':         dict(slot=M('ext/tank_a7v'), chosen=M('ext/tank_a7v'), fallback=M('wreck_tank'), archetype='static',
                             decision='keep + LODs', candidates=[]),
    'wreck_tank':       dict(slot=M('wreck_tank'), chosen=M('wreck_tank'), fallback=M('wreck_tank'), archetype='static',
                             decision='keep', candidates=['gm_w1s_mark1']),
    # guns and mortars
    'gun_75mm':         dict(slot=M('ext/gun_75mm'), chosen=M('ext/gm_canon75'), fallback=M('ext/gun_75mm'), archetype='static',
                             decision='swap (Canon de 75, ws 3576805717; licence to verify before Workshop)', candidates=['gm_canon75'],
                             fix={}),     # converted facing and centred like gun_75mm (yaw 270, pivot +32.5 x): no entity fix-up
    'howitzer_bl8':     dict(slot=M('ext/howitzer_bl8'), chosen=M('ext/howitzer_bl8'), fallback=M('wreck_fieldgun'), archetype='static',
                             decision='keep + LODs', candidates=[]),
    'mortar_58mm':      dict(slot=M('ext/mortar_58mm'), chosen=M('ext/mortar_58mm'), fallback=M('ext/mortar_58mm'), archetype='dynamic (mortar_ct_K, step 5 twin)',
                             decision='keep', candidates=['gm_ie_58mm', 'gm_mortar2in_carriage', 'gm_mortar2in_barrel']),
    'minenwerfer':      dict(slot=M('minenwerfer'), chosen=M('minenwerfer'), fallback=M('minenwerfer'), archetype='dynamic (mortar_t_K, step 5 twin)',
                             decision='keep', candidates=['gm_ie_minenwerfer']),
    'ammo_box_mortar':  dict(slot=M('ammo_box_mortar'), chosen=M('ammo_box_mortar'), fallback=M('ammo_box_mortar'), archetype='static',
                             decision='keep', candidates=['gm_ie_mw_crate']),
    # trench dressing
    'sandbag_wall_a':   dict(slot=M('sandbag_wall_a'), chosen=M('sandbag_wall_a'), fallback=M('sandbag_wall_a'), archetype='static',
                             decision='keep', candidates=['gm_w1s_sandbags', 'gm_nb_sandbag']),
    'sandbag_wall_128': dict(slot=M('sandbag_wall_128'), chosen=M('sandbag_wall_128'), fallback=M('sandbag_wall_128'), archetype='static',
                             decision='keep', candidates=['gm_rm_sandbag_nest']),
    'duckboard':        dict(slot=M('duckboard'), chosen=M('duckboard'), fallback=M('duckboard'), archetype='static',
                             decision='keep', candidates=['gm_w1s_duckboard']),
    'wire_fence_a':     dict(slot=M('wire_fence_a'), chosen=M('wire_fence_a'), fallback=M('wire_fence_a'), archetype='static',
                             decision='keep', candidates=['gm_w1s_wire', 'gm_rm_wire']),
    'crate_german':     dict(slot=M('crate_german'), chosen=M('crate_german'), fallback=M('crate_german'), archetype='static',
                             decision='keep', candidates=['gm_rm_crate']),
    'shelter':          dict(slot=M('shelter'), chosen=M('shelter'), fallback=M('shelter'), archetype='static',
                             decision='keep', candidates=['gm_pa_okop1']),
}
# Workshop candidates not converted into a slot, with the reason, live in tools/tw_gmod_catalog.json (status / rip / quality).

# ---------------------------------------------------------------------------------------------------------------- rendering
_VPK = None


def stock_png(vmat):
    """colour texture of a stock Valve vmat (pak01) as a cached PNG path, or None"""
    global _VPK
    key = re.sub(r'[^a-z0-9]+', '_', vmat.lower()) + '.png'
    out = os.path.join(CACHE, key)
    if os.path.exists(out): return out
    try:
        import vtexread
        data = vtexread.vpk_read(vmat + '_c')
        refs = [r for r in vtexread.refs(data) if r.endswith('.vtex')]
        col = [r for r in refs if re.search(r'(color|albedo|_c_|basecolor|diffuse)', r, re.I)] or refs
        if not col: return None
        img = vtexread.decode_vtex(vtexread.vpk_read(col[0] + '_c'))
        os.makedirs(CACHE, exist_ok=True)
        img.convert('RGB').save(out)
        return out
    except Exception:
        return None


class Scene(smd_view.Scene):
    """smd_view.Scene over several roots (staging first, then the content addon), stock textures from pak01, sun shading"""
    def __init__(self, roots):
        super().__init__(roots[0]); self.roots = roots
        self.sun = np.array([0.45, 0.35, 0.82]); self.sun /= np.linalg.norm(self.sun)

    def find(self, rel):
        for r in self.roots:
            p = os.path.join(r, rel)
            if os.path.exists(p): return p
        return None

    def add_model(self, vmdl, off=(0, 0, 0), yaw=0.0):
        p = self.find(vmdl)
        txt = open(p).read()
        mats = smd_view.load_vmdl_mats(txt); mats.update({k + '.vmat': v for k, v in list(mats.items())})
        smd = smd_view.vmdl_smd(txt) or vmdl.replace('.vmdl', '.smd')
        tris = smd_view.load_smd(self.find(smd), mats, off, yaw)
        self.tris += tris
        P = np.array([v[:3] for _, vs in tris for v in vs])
        return P.min(0), P.max(0), len(tris)

    def tex(self, vmat):
        from PIL import Image
        if vmat in self._tex: return self._tex[vmat]
        c = a = None
        vp = self.find(vmat)
        if vp:
            t = open(vp, errors='ignore').read()
            mc = re.search(r'TextureColor\s+"([^"]+)"', t); ma = re.search(r'TextureTranslucency\s+"([^"]+)"', t)
            c = mc and self.find(mc.group(1)); a = ma and self.find(ma.group(1))
            if not mc and re.search(r'TextureColor', t) is None: c = None
        else:
            c = stock_png(vmat)
        col = np.array(Image.open(c).convert('RGB')).astype(np.float32) if c else np.full((4, 4, 3), 150, np.float32)
        al = np.array(Image.open(a).convert('L')).astype(np.float32) / 255 if a else None
        if al is not None and al.shape != col.shape[:2]:
            al = np.array(Image.fromarray((al * 255).astype(np.uint8)).resize(col.shape[1::-1])).astype(np.float32) / 255
        self._tex[vmat] = (col, al)
        return self._tex[vmat]

    def _raster(self, img, zb, vmat, tri, fwd, right, upv, f, W, H):
        P = np.array([p[0] for p in tri])
        n = np.cross(P[1] - P[0], P[2] - P[0]); ln = np.linalg.norm(n)
        shade = 0.42 + 0.58 * abs(float(n @ self.sun) / ln) if ln > 1e-12 else 0.7
        key = (vmat, round(shade, 2))
        if key not in self._tex:
            t, al = self.tex(vmat) if vmat else (np.full((4, 4, 3), 200, np.float32), None)
            self._tex[key] = (t * shade, al)
        super()._raster(img, zb, key, tri, fwd, right, upv, f, W, H)


VIEWS = ((35, 18), (-145, 28), (90, 5))       # front-left 3/4, rear-right from above, side (+X = front)


def turntable(vmdl, roots, views=VIEWS, size=(560, 380), radius=None, centre=None, label=''):
    from PIL import Image, ImageDraw
    sc = Scene(roots)
    lo, hi, nt = sc.add_model(vmdl)
    c = (lo + hi) / 2 if centre is None else np.asarray(centre, float)
    r = radius or float(np.linalg.norm(hi - lo)) / 2
    ims = []
    for az, el in views:
        a, b = math.radians(az), math.radians(el)
        eye = c + 2.5 * r * np.array([math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b)])
        ims.append(sc.render(eye=tuple(eye), at=tuple(c), size=size, fov=40, bg=(92, 100, 112)))
    W = Image.new('RGB', (size[0], size[1] * len(ims)))
    for i, im in enumerate(ims): W.paste(im, (0, i * size[1]))
    d = ImageDraw.Draw(W)
    d.rectangle((0, 0, size[0], 18), fill=(20, 20, 20))
    d.text((4, 3), '%s  %d tris  %s' % (label or os.path.basename(vmdl), nt, (hi - lo).round(0).astype(int).tolist()), fill=(255, 255, 255))
    return W, lo, hi


def bounds(vmdl, roots):
    lo, hi, _ = Scene(roots).add_model(vmdl)
    return hi, lo


def gmod_models():
    p = os.path.join(PROJ, 'out', 'gmod_models.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def cmd_compare(only):
    from PIL import Image
    gm = gmod_models()
    os.makedirs(os.path.join(OUT, 'turntables'), exist_ok=True)
    roots = [STAGE, CONTENT]
    for slot, s in SWAPS.items():
        if only and slot not in only: continue
        cands = [c for c in s['candidates'] if c in gm]
        if not cands: continue
        sheets = []
        rad = max(float(np.linalg.norm(np.subtract(*bounds(m, roots)))) / 2 for m in [s['slot']] + [gm[c]['model'] for c in cands])
        cur, lo, hi = turntable(s['slot'], roots, radius=rad, label='CURRENT ' + slot)
        sheets.append(cur)
        for c in cands:
            im, l2, h2 = turntable(gm[c]['model'], roots, radius=rad, label='%s (ws %s, rip %s)' % (c, gm[c]['workshop_id'], gm[c].get('rip_risk') or '?'))
            sheets.append(im)
        W = Image.new('RGB', (sum(i.size[0] for i in sheets), max(i.size[1] for i in sheets)))
        x = 0
        for i in sheets: W.paste(i, (x, 0)); x += i.size[0]
        path = os.path.join(OUT, 'turntables', slot + '.png')
        W.save(path); print('  %s  (%d candidates)' % (os.path.relpath(path, PROJ), len(cands)))


def cmd_view(models, tag=''):
    os.makedirs(os.path.join(OUT, 'turntables'), exist_ok=True)
    for m in models:
        im, lo, hi = turntable(m, [STAGE, CONTENT], views=VIEWS + ((0, 80),))
        name = os.path.splitext(os.path.basename(m))[0] + (tag or '_view')
        path = os.path.join(OUT, 'turntables', name + '.png')
        im.save(path); print('  %s  bounds %s .. %s' % (os.path.relpath(path, PROJ), lo.round(1).tolist(), hi.round(1).tolist()))


# ---------------------------------------------------------------------------------------------------------------- weapons
# what ships (vdata class -> our model) against the stock CS2 weapon it replaces (S2V export, same model space and skeleton) and the
# Workshop candidates (converted SMDs, muzzle +X, centred). The overlay row is the scale check: ours (blue) over stock (red).
STOCK_DIR = os.environ.get('TW_STOCK_WEAPONS', 'C:/source2/projects/trenchwarfare/stock')
WEAPONS = {
    'gewehr98':  dict(cls='weapon_awp (T rifle)', ours='models/weapons/ww1/gewehr98/gewehr98_body.dmx', stock='weapon_snip_awp_body_hd1.dmx',
                      candidates=['gm_w1s_gewehr98', 'gm_ie_gewehr98']),
    'mondragon': dict(cls='weapon_g3sg1 (T streak)', ours='models/weapons/ww1/mondragon_m1908/mondragon_m1908_body.dmx', stock='weapon_snip_g3sg1_body_hd1.dmx',
                      candidates=[]),
    'lewis':     dict(cls='weapon_scar20 (CT streak)', ours='models/weapons/ww1/lewis_mk1/lewis_mk1_body.dmx', stock='weapon_snip_scar20_body_hd1.dmx',
                      candidates=['gm_w1s_lewis']),
}


def dmx_tris(path):
    """[(vmat, [(x, y, z, u, v)] * 3)] of every DmeMesh in a model DMX (bind pose; DMX UVs are top-left, smd_view wants bottom-left)"""
    import dmx9
    dm = dmx9.DMX.load(path); out = []
    for me in [e for e in dm.elements if e.type == 'DmeMesh']:
        vd = me['currentState']
        P = vd['position$0']; pi = vd['position$0Indices']; T = vd['texcoord$0']; ti = vd['texcoord$0Indices']
        for fs in me['faceSets']:
            mat = (fs['material']['mtlName'] if fs['material'] else '').replace(chr(92), '/')
            if mat and not mat.endswith('.vmat'): mat += '.vmat'
            cur = []
            for i in fs['faces']:
                if i >= 0: cur.append(i); continue
                vs = [(P[pi[j]][0], P[pi[j]][1], P[pi[j]][2], T[ti[j]][0], 1.0 - T[ti[j]][1]) for j in cur]
                out += [(mat, [vs[0], vs[k], vs[k + 1]]) for k in range(1, len(vs) - 1)]
                cur = []
    return out


def cmd_weapons(only):
    from PIL import Image, ImageDraw
    gm = gmod_models()
    os.makedirs(os.path.join(OUT, 'turntables'), exist_ok=True)
    roots = [STAGE, CONTENT]
    for key, w in WEAPONS.items():
        if only and key not in only: continue
        sets = [('OURS %s  %s' % (key, w['cls']), dmx_tris(os.path.join(CONTENT, *w['ours'].split('/')))),
                ('STOCK %s' % w['stock'][:-12], dmx_tris(os.path.join(STOCK_DIR, w['stock'])))]
        for c in w['candidates']:
            if c not in gm: continue
            sc = Scene(roots); sc.add_model(gm[c]['model'])
            T = sc.tris
            P = np.array([v[:3] for _, vs in T for v in vs]); ours_P = np.array([v[:3] for _, vs in sets[0][1] for v in vs])
            d = (ours_P.min(0) + ours_P.max(0)) / 2 - (P.min(0) + P.max(0)) / 2          # candidates centred on ours for the picture
            T = [(m, [(v[0] + d[0], v[1] + d[1], v[2] + d[2], v[3], v[4]) for v in vs]) for m, vs in T]
            sets.append(('%s (ws %s, rip %s)' % (c, gm[c]['workshop_id'], gm[c].get('rip_risk') or '?'), T))
        allP = np.array([v[:3] for _, t in sets[:2] for _, vs in t for v in vs])
        lo, hi = allP.min(0), allP.max(0); c0 = (lo + hi) / 2; r = float(np.linalg.norm(hi - lo)) / 2
        size = (620, 300); cols = []
        masks = []
        for label, T in sets:
            sc = Scene(roots); sc.tris = T
            ims = []
            for az, el in ((-90, 0), (-60, 20), (200, 12)):      # left side (as the stock icon), 3/4 from the left front, over the shoulder
                a, b = math.radians(az), math.radians(el)
                eye = c0 + 2.9 * r * np.array([math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b)])
                ims.append(sc.render(eye=tuple(eye), at=tuple(c0), size=size, fov=40, bg=(92, 100, 112)))
            masks.append(np.any(np.abs(np.asarray(ims[0], np.float32) - np.array([92, 100, 112])) > 3, axis=2))
            col = Image.new('RGB', (size[0], size[1] * 3))
            for i, im in enumerate(ims): col.paste(im, (0, i * size[1]))
            P = np.array([v[:3] for _, vs in T for v in vs])
            dd = ImageDraw.Draw(col); dd.rectangle((0, 0, size[0], 18), fill=(20, 20, 20))
            dd.text((4, 3), '%s  %d tris  len %.1f u' % (label, len(T), float(P[:, 0].max() - P[:, 0].min())), fill=(255, 255, 255))
            cols.append(col)
        ov = np.full(masks[0].shape + (3,), 235, np.uint8)
        ov[masks[1]] = (220, 70, 60); ov[masks[0]] = (60, 90, 220); ov[masks[0] & masks[1]] = (150, 60, 160)
        ovi = Image.new('RGB', (size[0], size[1] * 3), (235, 235, 235)); ovi.paste(Image.fromarray(ov), (0, 0))
        ImageDraw.Draw(ovi).text((4, size[1] + 4), 'scale check, side view: ours blue, stock red, both purple', fill=(0, 0, 0))
        cols.insert(2, ovi)
        W = Image.new('RGB', (size[0] * len(cols), size[1] * 3))
        for i, cimg in enumerate(cols): W.paste(cimg, (i * size[0], 0))
        path = os.path.join(OUT, 'turntables', 'weapon_' + key + '.png')
        W.save(path); print('  %s' % os.path.relpath(path, PROJ))


def exists(m):
    return any(os.path.exists(os.path.join(r, *m.split('/'))) for r in (STAGE, CONTENT))


def cmd_table():
    rows = []
    for slot, s in SWAPS.items():
        rows.append(dict(slot_name=slot, **s, chosen_present=exists(s['chosen']), fallback_present=exists(s['fallback'])))
        print('%-17s %-15s chosen %-48s fallback %-36s %s' % (slot, s['decision'], s['chosen'], s['fallback'], s['archetype']))
    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, 'tw_models.json'), 'w'), indent=1)


def swaps_to_apply():
    """slot model -> (chosen model, fix) for every slot whose choice differs from what the map has"""
    return {s['slot']: (s['chosen'], s.get('fix', {})) for s in SWAPS.values() if s['chosen'] != s['slot']}


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == 'table': cmd_table()
    elif a[0] == 'compare': cmd_compare(set(a[1].split(',')) if len(a) > 1 else set())
    elif a[0] == 'view': cmd_view(a[1:])
    elif a[0] == 'weapons': cmd_weapons(set(a[1].split(',')) if len(a) > 1 else set())
    elif a[0] == 'check':
        bad = [(k, m) for k, s in SWAPS.items() for m in (s['chosen'], s['fallback']) if not exists(m)]
        for k, m in bad: print('  MISSING %s: %s' % (k, m))
        print('check: %d missing' % len(bad)); sys.exit(1 if bad else 0)
    else: print(__doc__)


if __name__ == '__main__':
    main()
