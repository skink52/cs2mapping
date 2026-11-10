"""create/matkit.py, sndkit.py, fxkit.py, blenderkit.py and tools/propatlas.py. No CS2, no Blender run (scripts are only parsed).

  python -m unittest discover -s tools/tests -p "test_assetkits.py" -v
"""
import ast, json, os, shutil, subprocess, sys, tempfile, unittest, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path.append(F.CREATE)
import numpy as np
from PIL import Image
import matkit, blenderkit, propatlas


class Tmp(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='cs2mcp_kit_')
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)


class Materials(Tmp):
    def test_patterns_and_vmat(self):
        for p in matkit.PATTERNS:
            alb, h = matkit.generate(p, 64, '#a05030', seed=2)
            self.assertEqual(alb.shape, (64, 64, 3)); self.assertEqual(h.shape, (64, 64))
            self.assertTrue(0 <= h.min() and h.max() <= 1)
        alb, h = matkit.generate('bricks', 128)
        rel = matkit.write_material(self.tmp, 'materials/gen', 'brick', alb, h, roughness=0.8)
        self.assertEqual(rel, 'materials/gen/brick.vmat')
        text = open(os.path.join(self.tmp, 'materials', 'gen', 'brick.vmat')).read()
        self.assertIn('shader "csgo_complex.vfx"', text); self.assertIn('TextureNormal "materials/gen/brick_normal.png"', text)
        for sfx in ('color', 'normal', 'rough', 'ao'): self.assertTrue(os.path.exists(os.path.join(self.tmp, 'materials', 'gen', 'brick_%s.png' % sfx)))

    def test_tileable_and_normals(self):
        rnd = np.random.default_rng(3).integers(0, 255, (64, 64, 3)).astype(np.uint8)
        grad = np.tile(np.linspace(0, 255, 64)[None, :, None], (64, 1, 3)).astype(np.uint8)
        self.assertLess(matkit.seam_error(matkit.make_tileable(grad)), matkit.seam_error(grad) / 4)
        n = matkit.normal_from(np.tile(np.linspace(0, 1, 32)[None, :], (32, 1)))
        self.assertLess(n[16, 16, 0], 128)                              # height rising to +x tilts the normal to -x
        self.assertTrue(np.all(n[..., 2] > 128))
        self.assertEqual(matkit.fbm(32, 4, 1).shape, (32, 32))
        self.assertLess(abs(matkit.fbm(64, 4, 1)[:, 0] - matkit.fbm(64, 4, 1)[:, -1]).mean(), 0.2)   # tileable noise

    def test_photo_variant_kinds(self):
        photo = os.path.join(self.tmp, 'p.png')
        Image.fromarray(np.random.default_rng(1).integers(0, 255, (100, 150, 3)).astype(np.uint8)).save(photo)
        alb, h = matkit.from_image(photo, region=(10, 10, 110, 90))
        self.assertEqual(alb.shape[0], alb.shape[1])
        v = matkit.variant(os.path.join(self.tmp, 'p.png'), '#ff0000', 0.0, 1.0)
        self.assertTrue(np.all(v[..., 1] == 0))                          # grey * red tint: no green
        for kind in ('glass', 'emissive', 'water', 'decal'):
            img = matkit.text_image('EXIT', transparent=(kind == 'decal'))
            rel = matkit.write_material(self.tmp, 'gen', 'k_' + kind, img, kind=kind)
            text = open(os.path.join(self.tmp, *rel.split('/'))).read()
            self.assertIn({'glass': 'csgo_glass', 'emissive': 'F_SELF_ILLUM 1', 'water': 'csgo_water_fancy', 'decal': 'F_OVERLAY'}[kind], text.replace('"1"', '1'))
        with self.assertRaises(ValueError): matkit.generate('marble')


class Sounds(Tmp):
    def test_presets_events(self):
        import sndkit
        for p in sndkit.PRESETS:
            x = sndkit.synth(p, 0.2)
            self.assertEqual(len(x), int(0.2 * 44100)); self.assertLessEqual(float(np.abs(x).max()), 0.81)
        rel = sndkit.write(self.tmp, 'beep', sndkit.synth('beep', 0.3), loop=True)
        self.assertEqual(rel, 'sounds/gen/beep.vsnd')
        with wave.open(os.path.join(self.tmp, 'sounds', 'gen', 'beep.wav')) as w: self.assertEqual((w.getframerate(), w.getsampwidth()), (44100, 2))
        data = open(os.path.join(self.tmp, 'sounds', 'gen', 'beep.wav'), 'rb').read()
        self.assertIn(b'smpl', data)                                      # loop markers
        x, rate = sndkit.read_wav(os.path.join(self.tmp, 'sounds', 'gen', 'beep.wav'))
        self.assertEqual(len(sndkit.resample(x, rate, 22050)), len(x) // 2)
        sndkit.event(self.tmp, 't.beep', rel); sndkit.event(self.tmp, 't.hum', rel, kind='flat')
        r = sndkit.event(self.tmp, 't.beep', rel, range_=500)
        self.assertEqual(r['events_in_block'], ['t.beep', 't.hum'])
        text = open(r['file']).read()
        self.assertEqual(text.count('"t.beep"'), 1); self.assertIn('500.0, 0.00', text)


FX_BUILD = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, primitives as P, fxkit
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
fxkit.effect('smoke', (0, 0, 0), 'smoke1', group='t')
fxkit.precipitation(((0, 0, 0), (512, 512, 512)), 'snow', 'snow1', group='t')
fxkit.weather_tiles(((0, 0, 0), (2048, 1024, 512)), 'rain', 'rain1', group='t')
fxkit.lightning('storm', (0, 0, 600), thunder='test.thunder', group='t')
vmapgen.finish(d, OUT, group='t')
'''


class Effects(Tmp):
    def test_fx_entities(self):
        out = F.make_map(os.path.join(self.tmp, 'fx.vmap'), FX_BUILD)
        import vmapedit as V, collections
        m = V.Map(out)
        c = collections.Counter(m.cls(e) for e in m.entities())
        self.assertEqual(c['info_particle_system'], 1 + 2)
        self.assertEqual(c['func_precipitation'], 1); self.assertEqual(c['env_fade'], 1); self.assertEqual(c['point_soundevent'], 1)
        relay = [e for e in m.entities() if m.name(e) == 'rain1'][0]
        self.assertEqual(sorted(t[1] for t in map(m.conn_tuple, m.conns(relay))), ['rain1_0_0', 'rain1_0_0', 'rain1_1_0', 'rain1_1_0'])
        pr = m.by_class('func_precipitation')[0]
        self.assertEqual(m.P(pr, 'subclass_name'), 'precipitation_snow')
        self.assertEqual(len([c for c in m.children(pr) if m.type(c) == b'CMapMesh']), 1)

    @unittest.skipUnless(os.path.exists(os.path.join(F.TOOLS, '..')) and __import__('fgdcat').fgd_paths(), 'CS2 not installed')
    def test_stock_particles_exist(self):
        import fgdcat, vpk, fxkit
        v = vpk.VPK(os.path.join(fgdcat.cs2_root(), 'game', 'csgo', 'pak01_dir.vpk'))
        missing = [p for p in fxkit.EFFECTS.values() if not v.has(p + '_c')]
        self.assertEqual(missing, [])


class Blender(Tmp):
    def test_scripts_parse_and_vmdl(self):
        for t in blenderkit.TEMPLATES:
            ast.parse(blenderkit.script('x', self.tmp, template=t))
        for ext in ('.obj', '.fbx', '.glb', '.blend'):
            ast.parse(blenderkit.script('x', self.tmp, imported='a' + ext, height=72))
        user = os.path.join(self.tmp, 'u.py'); F.write(user, "box('a', 0, 0, 0, 8, 8, 8)\n")
        ast.parse(blenderkit.script('x', self.tmp, user_script=user))
        r = blenderkit.build(self.tmp, 'crate1', template='crate', size=(40, 40, 40), dry_run=True)
        self.assertEqual(r['model'], 'models/props/crate1/crate1.vmdl')
        v = open(r['vmdl']).read()
        self.assertIn('filename = "models/props/crate1/crate1.fbx"', v); self.assertIn('PhysicsHullFile', v)
        self.assertIn('W, D, H = 40.0, 40.0, 40.0', open(r['script']).read())
        with self.assertRaises(ValueError): blenderkit.script('x', self.tmp, template='spaceship')
        with self.assertRaises(FileNotFoundError):
            blenderkit.build(self.tmp, 'c2', template='crate', blender=None) if not blenderkit.find_blender() else (_ for _ in ()).throw(FileNotFoundError())


class Atlas(Tmp):
    def test_search_notes_categories(self):
        models = ['models/props/crates/wood_crate_01.vmdl', 'models/props/barrels/oil_barrel.vmdl', 'models/foliage/tree_oak.vmdl',
                  'models/props/de_dust/terrain_patch.vmdl']
        class B:
            def get_many(self, ms): return {m: [[-8, -8, 0], [8, 8, 16]] for m in ms}
        a = propatlas.Atlas('X:/none', models, os.path.join(self.tmp, 'notes.json'), B())
        self.assertEqual(propatlas.category(models[0]), 'crate'); self.assertEqual(propatlas.category(models[3]), 'other')
        r = a.search('crate', sizes=True)
        self.assertEqual(r['matches'], 1); self.assertEqual(r['models'][0]['size'], [16, 16, 16])
        a.note(models[1], category='barrel', tags=['red', 'explosive'], mount='floor')
        self.assertEqual(a.search('explosive')['models'][0]['model'], models[1])
        self.assertEqual(json.load(open(os.path.join(self.tmp, 'notes.json')))[models[1]]['mount'], 'floor')
        self.assertEqual(a.categories()['foliage'], 1)


if __name__ == '__main__':
    unittest.main()
