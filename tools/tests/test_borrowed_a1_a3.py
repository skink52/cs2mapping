"""A1 texlights.py (lights.rad texture lights from the BSP), A2 lighting.lightcal (compiled falloff + BSP line traces), A3 daylight.fullbright.
Synthetic BSPs are written in a temp folder; the real-map checks run only where the PC's BSPs are present.

  python -m unittest discover -s tools/tests -p "test_borrowed_a1_a3.py" -v
"""
import math, os, shutil, struct, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import texlights as T, lighting as L, daylight as D

BSPS = r'C:\source1\bspsrc-windows'


def write_bsp(path, lumps, versions=None):
    """VBSP 21 with the given {lump index: bytes}"""
    versions = versions or {}
    head = bytearray(b'VBSP' + struct.pack('<i', 21) + b'\0' * (16 * 64) + struct.pack('<i', 1))
    body = bytearray(); off = len(head)
    for i in range(64):
        data = lumps.get(i, b'')
        struct.pack_into('<iiii', head, 8 + 16 * i, off + len(body) if data else 0, len(data), versions.get(i, 0), 0)
        body += data
        while len(body) % 4: body += b'\0'
    with open(path, 'wb') as f: f.write(bytes(head) + bytes(body))


def worldlight(org, inten, typ, c=0.0, l=0.0, q=0.0, normal=(0, 0, 1), stopdot2=0.0, radius=0.0):
    """version-1 dworldlight_t (100 bytes)"""
    return (struct.pack('<3f3f3f3f', *org, *inten, *normal, 0, 0, 0) + struct.pack('<3i', 0, typ, 0)
            + struct.pack('<7f', 0.0, stopdot2, 0.0, radius, c, l, q) + struct.pack('<3i', 0, 0, 0))


def light_panel_bsp(path, name=b'maps/test/lights/panel_1_2_3', lights=4, inten=10.0, lightmap=b'\x10\x10\x10\x00', extra_lights=b''):
    """one 64 x 64 face at z = 0 facing up with SURF_LIGHT, `lights` surface lights on it of `inten` each"""
    strdata = name + b'\0' + b'tools/toolsnodraw\0'
    strtab = struct.pack('<ii', 0, len(name) + 1)
    texdata = struct.pack('<3fiiiii', 1, 1, 1, 0, 64, 64, 64, 64) + struct.pack('<3fiiiii', 1, 1, 1, 1, 64, 64, 64, 64)
    texinfo = struct.pack('<16f', *([0.0] * 16)) + struct.pack('<16f', *([0.0] * 16))
    texinfo = struct.pack('<8f8fii', *([0.0] * 16), T.SURF_LIGHT, 0) + struct.pack('<8f8fii', *([0.0] * 16), T.SURF_NODRAW, 1)
    verts = struct.pack('<12f', 0, 0, 0, 64, 0, 0, 64, 64, 0, 0, 64, 0)
    edges = struct.pack('<8H', 0, 1, 1, 2, 2, 3, 3, 0)
    surfedges = struct.pack('<4i', 0, 1, 2, 3)
    planes = struct.pack('<4fi', 0, 0, 1, 0, 2)
    face = struct.pack('<HBBihh', 0, 0, 0, 0, 4, 0) + b'\0' * 12 + struct.pack('<f', 64.0 * 64.0) + b'\0' * 28
    assert len(face) == 56
    wl = b''.join(worldlight((8 + 16 * i, 32, 0), (inten, inten, inten), T.EMIT_SURFACE) for i in range(lights)) + extra_lights
    # tree for the tracer: node 0 splits at z = 0, front (above) = leaf 0 (empty), back = leaf 1 (solid)
    nodes = struct.pack('<3i', 0, -1, -2) + b'\0' * 20
    leafs = struct.pack('<i', 0) + b'\0' * 28 + struct.pack('<i', 1) + b'\0' * 28
    models = struct.pack('<9f', 0, 0, 0, 64, 64, 64, 0, 0, 0) + struct.pack('<3i', 0, 0, 1)
    write_bsp(path, {T.LUMP_PLANES: planes, T.LUMP_TEXDATA: texdata, T.LUMP_VERTEXES: verts, T.LUMP_NODES: nodes, T.LUMP_TEXINFO: texinfo,
                     T.LUMP_FACES: face, T.LUMP_LIGHTING: lightmap * 16, T.LUMP_LEAFS: leafs, T.LUMP_EDGES: edges, T.LUMP_SURFEDGES: surfedges,
                     T.LUMP_MODELS: models, T.LUMP_WORLDLIGHTS: wl, T.LUMP_TEXDATA_STRING_DATA: strdata, T.LUMP_TEXDATA_STRING_TABLE: strtab},
              versions={T.LUMP_WORLDLIGHTS: 1, T.LUMP_LEAFS: 1})


class Ctx:
    def __init__(s, root, addon='zz_test'):
        s.addon = addon; s.root = root; s.content = os.path.join(root, 'content', addon)
        s.files = {}; s.log = []; s.todo = []
    def write(s, rel, data): s.files[rel] = data if isinstance(data, bytes) else data.encode('utf-8')


class FakeMap:
    def __init__(s, ents=()):
        s.ents = [dict(e) for e in ents]; s.added = []
    def new_entity(s, cls, origin, props, angles=(0, 0, 0), parent=None):
        e = dict(props, classname=cls, _o=tuple(origin), _a=tuple(angles)); s.ents.append(e); s.added.append(e); return e
    def entities(s): return s.ents
    def by_class(s, *cls): return [e for e in s.ents if e['classname'] in cls]
    def cls(s, e): return e['classname']
    def P(s, e, k, d=None): return e.get(k, d)
    def setp(s, e, k, v): e[k] = v
    def origin(s, e): return e['_o']
    def name(s, e): return e.get('targetname', '')


VMAT = 'Layer0\n{\n    shader "csgo_complex.vfx"\n    TextureColor "materials\\lights\\panel.png"\n}\n'


class TempDir(unittest.TestCase):
    def setUp(s): s.tmp = tempfile.mkdtemp(prefix='borrowed_a_')
    def tearDown(s): shutil.rmtree(s.tmp, ignore_errors=True)


class BspReader(TempDir):
    def test_lumps_and_lights(s):
        p = os.path.join(s.tmp, 'a.bsp'); light_panel_bsp(p, extra_lights=worldlight((5, 5, 50), (100, 100, 100), T.EMIT_POINT, q=1))
        b = T.Bsp(p)
        s.assertEqual(T.texinfo_list(b)[0], (T.SURF_LIGHT, 'maps/test/lights/panel_1_2_3'))
        wl = T.world_lights(b)
        s.assertEqual([w['type'] for w in wl], [0, 0, 0, 0, 1])
        s.assertEqual(wl[-1]['q'], 1.0)
        s.assertTrue(T.lightmaps_lit(b))

    def test_lzma_lump(s):
        import lzma
        raw = b'hello world ' * 50
        comp = lzma.compress(raw, format=lzma.FORMAT_ALONE)    # props(5) dictsize... + size(8) + data
        props, data = comp[:5], comp[13:]
        lump = b'LZMA' + struct.pack('<II', len(raw), len(data)) + props + data
        p = os.path.join(s.tmp, 'z.bsp'); write_bsp(p, {T.LUMP_ENTITIES: lump})
        s.assertEqual(T.Bsp(p).lump(T.LUMP_ENTITIES), raw)

    def test_not_a_bsp(s):
        p = os.path.join(s.tmp, 'x.bsp'); open(p, 'wb').write(b'nope' * 300)
        with s.assertRaises(ValueError): T.Bsp(p)


class TextureLights(TempDir):
    def test_emission_is_pi_rho(s):
        p = os.path.join(s.tmp, 'a.bsp'); light_panel_bsp(p, lights=4, inten=100.0)
        tl = T.texture_lights(T.Bsp(p))
        s.assertEqual(list(tl), ['lights/panel'])               # compiler copy name mapped back
        s.assertAlmostEqual(tl['lights/panel'][0], math.pi * 400.0 / 4096.0, places=6)

    def test_dim_lights_dropped(s):
        p = os.path.join(s.tmp, 'a.bsp'); light_panel_bsp(p, lights=1, inten=0.01)
        s.assertEqual(T.texture_lights(T.Bsp(p)), {})

    def test_unpatched(s):
        s.assertEqual(T.unpatched('maps/de_x/lights/white001_-12_340_56'), 'lights/white001')
        s.assertEqual(T.unpatched('materials/maps/de_x/nature/blend_wvt_patch'), 'nature/blend')
        s.assertEqual(T.unpatched('lights/white001'), 'lights/white001')

    def test_self_illum(s):
        tint, br = T.self_illum((8.0, 4.0, 2.0))
        s.assertEqual(tint, (1.0, 0.5, 0.25)); s.assertAlmostEqual(br, 3.0)
        s.assertEqual(T.self_illum((0, 0, 0)), ((1.0, 1.0, 1.0), 0.0))

    def test_glow_vmat(s):
        out = T.glow_vmat(VMAT, (4.0, 4.0, 2.0))
        s.assertIn('F_SELF_ILLUM 1', out); s.assertIn('g_flSelfIllumBrightness "2.000"', out)
        s.assertIn('g_vSelfIllumTint "[1.000000 1.000000 0.500000 0.000000]"', out)
        s.assertIn('TextureColor', out)
        again = T.glow_vmat(out, (2.0, 2.0, 2.0))                  # re-run replaces, doesn't stack
        s.assertEqual(again.count('F_SELF_ILLUM'), 1); s.assertIn('"1.000"', again)
        masked = VMAT.replace('TextureColor', 'TextureSelfIllumMask "materials\\m.png"\n    TextureColor')
        s.assertIn('materials\\m.png', T.glow_vmat(masked, (2, 2, 2)))
        s.assertIsNone(T.glow_vmat(VMAT.replace('csgo_complex', 'csgo_water'), (2, 2, 2)))

    def test_rect_lights(s):
        pts = [(0, 0, 0), (256, 0, 0), (256, 64, 0), (0, 64, 0)]
        rl, skipped = T.rect_lights({'w': [(pts, (0, 0, -1))], 'slant': [([(0, 0, 0), (64, 0, 64), (64, 64, 64)], (0.7, 0, 0.7))]},
                                    {'w': (5.0, 5.0, 2.5), 'slant': (5, 5, 5)})
        s.assertEqual(len(rl), 4); s.assertEqual(skipped, 1)        # 256 x 64 cut into four 64 x 64 tiles
        s.assertEqual(rl[0]['angles'], (90.0, 0.0, 0.0))             # facing down
        s.assertEqual(rl[0]['origin'][2], -2.0)
        s.assertEqual(rl[0]['color'], '255 255 128')
        s.assertAlmostEqual(rl[0]['lumens'], 5.0 * 64 * 64 / T.LIGHTMAP_PER_LUX)

    def test_run_glow_and_rect(s):
        import assets
        root = os.path.join(s.tmp, 'root'); c = Ctx(root)
        os.makedirs(os.path.join(c.content, 'materials', 'lights')); os.makedirs(os.path.join(root, 'source1', 'maps'))
        light_panel_bsp(os.path.join(root, 'source1', 'maps', 'zz_test.bsp'), lights=4, inten=200.0)
        old = assets.mesh_materials
        try:
            assets.mesh_materials = lambda m: {'materials/lights/panel.vmat': [0]}
            # stock material (not in the addon): light_rect
            m = FakeMap(); s.assertEqual(T.run(m, c), 1)
            s.assertEqual(len(m.added), 1); s.assertEqual(m.added[0]['classname'], 'light_rect')
            s.assertEqual(m.added[0]['_a'], (-90.0, 0.0, 0.0)); s.assertEqual(c.files, {})
            # in the addon: self-illum, no light
            open(os.path.join(c.content, 'materials', 'lights', 'panel.vmat'), 'w').write(VMAT)
            m = FakeMap(); c.log = []; T.run(m, c)
            s.assertEqual(m.added, []); s.assertIn('F_SELF_ILLUM 1', c.files['materials/lights/panel.vmat'].decode())
            s.assertTrue(any('texlights' in t for t in c.todo))
        finally:
            assets.mesh_materials = old

    def test_no_bsp(s):
        c = Ctx(s.tmp); s.assertEqual(T.run(FakeMap(), c), 0); s.assertIn('no BSP', c.todo[0])

    @unittest.skipUnless(os.path.isfile(os.path.join(BSPS, 'mg maps', 'mg_jahoukarail_2015.bsp')), 'PC BSPs not present')
    def test_real_jahoukarail(s):
        tl = T.texture_lights(T.Bsp(os.path.join(BSPS, 'mg maps', 'mg_jahoukarail_2015.bsp')))
        s.assertEqual(list(tl), ['devneons/white_neon'])
        s.assertAlmostEqual(tl['devneons/white_neon'][0], 13.67, places=1)


class LightCal(TempDir):
    def test_tracer(s):
        p = os.path.join(s.tmp, 'a.bsp'); light_panel_bsp(p)
        tr = L.BspTracer(T.Bsp(p))
        s.assertAlmostEqual(tr.trace((10, 10, 100), (0, 0, -1)), 100.0, places=3)
        s.assertIsNone(tr.trace((10, 10, 100), (0, 0, 1)))

    def test_quadratic_matches_relight_scale(s):
        """a quadratic light gets the legacy relight gives it, whatever the distances"""
        wl = {'type': 1, 'intensity': (1e4 * 265 / 255,) * 3, 'c': 0.0, 'l': 0.0, 'q': 1.0, 'radius': 0}
        s.assertAlmostEqual(L.match_legacy(wl, [60, 200, 900, None] * 4), 1.0, places=6)

    def test_ldr_cap(s):
        wl = {'type': 1, 'intensity': (1e4 * 265 / 255,) * 3, 'c': 0.0, 'l': 0.0, 'q': 1.0, 'radius': 0}
        s.assertLess(L.match_legacy(wl, [50.0] * 10, cap=2.0), 1.0)     # 4.2 at 50 u counted as 2

    def test_vrad_fifty_percent(s):
        """constants vrad compiled for _fifty_percent_distance 55 (ttt_cg_skyscraper_2017_b1's light list)"""
        wl = L.vrad_falloff({'classname': 'light', '_light': '255 255 255 200', '_fifty_percent_distance': '55'})
        s.assertAlmostEqual(wl['c'], 0.03065, places=5); s.assertAlmostEqual(wl['l'], 0.0005573, places=6)
        s.assertAlmostEqual(wl['q'], 0.00064089, places=7)
        s.assertAlmostEqual(wl['intensity'][0], 200 / 255.0, places=6)    # not normalised to 100 u
        lin = L.vrad_falloff({'classname': 'light', '_light': '255 255 255 200', '_linear_attn': '1', '_quadratic_attn': '0'})
        s.assertEqual((lin['c'], lin['l'], lin['q']), (0.0, 1.0, 0.0)); s.assertAlmostEqual(lin['intensity'][0], 200 / 255.0 * 100)

    def test_calibrate_report_and_apply(s):
        p = os.path.join(s.tmp, 'a.bsp')
        light_panel_bsp(p, extra_lights=worldlight((5, 5, 400), (1e4 * 265 / 255 * 2,) * 3, T.EMIT_POINT, l=0.0, q=1.0)
                        + worldlight((40, 40, 400), (2.0,) * 3, T.EMIT_POINT, c=0.03065, l=0.0005573, q=0.00064089))
        m = FakeMap([{'classname': 'light_omni2', '_o': (5, 5, 400), 'brightness_legacy': '1'},
                     {'classname': 'light_omni2', '_o': (40, 40, 400), 'brightness_legacy': '1'},
                     {'classname': 'light_omni2', '_o': (900, 0, 0), 'brightness_legacy': '1'}])
        c = Ctx(s.tmp)
        rows = L.calibrate(m, c, p)
        s.assertEqual(len(rows), 2); s.assertAlmostEqual(rows[0][3], 2.0, places=4)
        s.assertEqual(m.ents[0]['brightness_legacy'], '1')                      # report only
        s.assertIn('1 lights not in the light list', c.log[0])
        L.calibrate(m, c, p, apply=True)
        s.assertEqual(m.ents[0]['brightness_lumens'], '2000')
        s.assertIn('range', m.ents[1])                                           # non-quadratic: range from the new brightness

    @unittest.skipUnless(os.path.isfile(os.path.join(BSPS, 'mg maps', 'ttt_cg_skyscraper_2017_b1.bsp')), 'PC BSPs not present')
    def test_real_compiled_fifty(s):
        wl = [w for w in T.world_lights(T.Bsp(os.path.join(BSPS, 'mg maps', 'ttt_cg_skyscraper_2017_b1.bsp'))) if w['c'] > 0]
        s.assertTrue(wl)
        for w in wl:
            D_ = 0.03065 / w['l']                                                # D from the linear term
            s.assertAlmostEqual(w['q'], 0.03065 * 63.25 / D_ ** 2, delta=w['q'] * 0.01)

    def test_fifty_units_and_baseline(s):
        """A fifty-percent light on a never-relit map (mg_antique_course, 23 Nov: 'median x0.01'): the calibrated value is the compiled
        falloff's (intensity NOT x attn(100)), the report also compares with what relight gives and says the map was never relit."""
        D_ = 60.0
        wl = L.vrad_falloff({'classname': 'light', '_light': '255 255 255 200', '_fifty_percent_distance': str(D_)})
        p = os.path.join(s.tmp, 'a.bsp')
        light_panel_bsp(p, extra_lights=worldlight((5, 5, 400), wl['intensity'], T.EMIT_POINT, c=wl['c'], l=wl['l'], q=wl['q']))
        v = os.path.join(s.tmp, 'm.vmf')
        open(v, 'w').write('entity\n{\n"classname" "light"\n"origin" "5 5 400"\n"_light" "255 255 255 200"\n"_fifty_percent_distance" "60"\n}\n')
        importer = 8.65                                                           # what the importer wrote (never relit)
        m = FakeMap([{'classname': 'light_omni2', '_o': (5, 5, 400), 'brightness_legacy': str(importer)}])
        c = Ctx(s.tmp)
        rows = L.calibrate(m, c, p, vmfpath=v)
        _n, _cls, cur, cal, rel = rows[0]
        dists = [d for d in (L.BspTracer(T.Bsp(p)).trace((5, 5, 400), x) for x in L._DIRS) if d]
        want = math.exp(sum(math.log(L.s1_brightness(wl, d) * d * d) for d in dists) / len(dists)) / L.S1_LEGACY1
        s.assertAlmostEqual(cal, want, places=6)
        s.assertAlmostEqual(cal, 200 / 255 * 400 ** 2 / (0.03065 * 63.25 * (400 / 60) ** 2) / L.S1_LEGACY1, delta=cal * 0.1)   # ~0.14
        s.assertAlmostEqual(rel, L.relight_legacy({'_light': '255 255 255 200', '_fifty_percent_distance': '60'}))
        s.assertIn('what relight gives', c.log[0]); s.assertIn('never relit', c.log[0])

    def test_lightmap_check(s):
        """the luxel under a light against the compiled falloff: 1 when the lightmap holds exactly the predicted direct light"""
        p = os.path.join(s.tmp, 'a.bsp')
        lux = 16 / 255.0                                                         # light_panel_bsp's lightmap: 0x10 x 2^0
        light_panel_bsp(p, lights=0, extra_lights=worldlight((32, 32, 100), (lux * 1e4,) * 3, T.EMIT_POINT, q=1.0))
        b = T.Bsp(p)
        r, n = L.lightmap_check(b, L.BspTracer(b), [w for w in T.world_lights(b) if w['type'] in (1, 2)])
        s.assertEqual(n, 1); s.assertAlmostEqual(r, 1.0, places=6)

    def test_fifty_note(s):
        v = os.path.join(s.tmp, 'm.vmf'); open(v, 'w').write('"_fifty_percent_distance" "64"\n"_fifty_percent_distance" "0"\n')
        c = Ctx(s.tmp); s.assertEqual(L.fifty_percent_note(c, v), 1); s.assertIn('lightcal', c.todo[0])


class FullBright(TempDir):
    def test_detect(s):
        lit, dark, none = (os.path.join(s.tmp, n + '.bsp') for n in ('lit', 'dark', 'none'))
        light_panel_bsp(lit); light_panel_bsp(dark, lightmap=b'\0\0\0\x05'); light_panel_bsp(none, lightmap=b'')
        s.assertTrue(T.lightmaps_lit(T.Bsp(lit)))
        s.assertFalse(T.lightmaps_lit(T.Bsp(dark))); s.assertFalse(T.lightmaps_lit(T.Bsp(none)))

    def test_unlit_vmat(s):
        s.assertIn('csgo_unlitgeneric.vfx', D.unlit_vmat(VMAT))
        s.assertIsNone(D.unlit_vmat(VMAT.replace('TextureColor', 'F_ALPHA_TEST 1\n    TextureColor')))
        s.assertIsNone(D.unlit_vmat(VMAT.replace('csgo_complex', 'csgo_water')))

    def test_pass(s):
        import assets
        root = os.path.join(s.tmp, 'root'); c = Ctx(root)
        os.makedirs(os.path.join(c.content, 'materials', 'w')); os.makedirs(os.path.join(root, 'source1', 'maps'))
        open(os.path.join(c.content, 'materials', 'w', 'wall.vmat'), 'w').write(VMAT)
        bsp = os.path.join(root, 'source1', 'maps', 'zz_test.bsp')
        light_panel_bsp(bsp)
        s.assertFalse(D.fullbright(FakeMap(), c))                                # lit map: nothing
        light_panel_bsp(bsp, lightmap=b'')
        s.assertTrue(D.fullbright(FakeMap(), c, apply=False)); s.assertEqual(c.files, {})
        old_mm, old_am = assets.mesh_materials, D.all_meshes
        try:
            assets.mesh_materials = lambda m: {'materials/w/wall.vmat': [0], 'materials/stock/x.vmat': [1]}
            D.all_meshes = lambda m: []
            m = FakeMap([{'classname': 'info_player_terrorist', '_o': (0, 0, 0)}, {'classname': 'env_combined_light_probe_volume', '_o': (0, 0, 0)}])
            s.assertTrue(D.fullbright(m, c))
        finally:
            assets.mesh_materials, D.all_meshes = old_mm, old_am
        s.assertIn('csgo_unlitgeneric', c.files['materials/w/wall.vmat'].decode())
        sun = [e for e in m.added if e['classname'] == 'light_environment']
        s.assertEqual(len(sun), 1); s.assertEqual(sun[0]['_a'], (90.0, 0.0, 0.0)); s.assertEqual(sun[0]['castshadows'], 0)
        s.assertTrue(any('stock' in t for t in c.todo))


if __name__ == '__main__':
    unittest.main()
