"""create/gen_layout.py, gen_buildings.py, gen_world.py, gen_kits.py, gen_gameplay.py: every shape closed and outward, a written test map
whose meshes pass create/check_mesh.py, the plan / timing maths, and (where CS2 is installed) every stock material and model they name.

  python -m unittest discover -s tools/tests -p "test_generators.py" -v
"""
import math, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path.append(F.CREATE)
import primitives as P
import gen_layout, gen_buildings, gen_world, gen_kits, gen_gameplay

PLAN = {'rooms': {'hall': [0, 0, 512, 256], 'side': [512, 0, 768, 256], 'corr': [0, 256, 128, 768], 'big': [-256, 768, 512, 1280]},
        'doors': [['hall', 'side', 64, 96], ['hall', 'corr', 64, 96], ['corr', 'big', 96, 112]]}


class Shapes(unittest.TestCase):
    def all_ok(self, named):
        bad = [(n, P.check(s)[:1]) for n, s in named if P.check(s)]
        self.assertEqual(bad, [])

    def test_layout(self):
        out = gen_layout.build(PLAN)
        self.all_ok(out['shapes'])
        self.assertEqual(len(out['doors']), 3)
        walls = [s for n, s in out['shapes'] if n.startswith('wall')]
        lines = [n for n, s in out['shapes'] if n.startswith('wall_x512')]
        self.assertEqual(len(lines), 2)                         # x = 512: the shared hall / side wall (with the door) + big's east wall
        door_wall = [s for n, s in out['shapes'] if n == 'wall_x512_0'][0]
        self.assertAlmostEqual(P.volume(door_wall), 8 * 264 * 128 - 8 * 64 * 96, delta=1)
        with self.assertRaises(ValueError): gen_layout.build({'rooms': {'a': [0, 0, 64, 64], 'b': [200, 0, 300, 64]}, 'doors': [['a', 'b']]})
        self.assertEqual(gen_layout.shared_edge(gen_layout._room('a', [0, 0, 64, 64], {}), gen_layout._room('b', [64, 32, 128, 128], {})), ('x', 64.0, (32.0, 64.0)))

    def test_buildings(self):
        b = gen_buildings.building((0, 0, 384, 256), 2, front='-y', windows=3, roof='flat')
        self.all_ok(b['shapes'])
        self.assertEqual(b['door'], [192.0, -32.0, 0.0]); self.assertEqual(b['top'], 2 * 128 + 8 + 24)
        self.assertEqual(sum(1 for n, _ in b['shapes'] if n == 'glass'), 5 + 6 + 8)                      # front 3 x 2 floors less the door bay, back 3 x 2, sides 2 x 2 x 2
        g = gen_buildings.building((0, 0, 256, 384), 3, front='+x', roof='gable', style='brick')
        self.all_ok(g['shapes'])
        row = gen_buildings.street_front((0, 0), (1536, 0), seed=2)
        self.assertAlmostEqual(sum(r['footprint'][2] - r['footprint'][0] for r in row), 1536)
        for r in row: self.all_ok(r['shapes'])
        d = gen_buildings.district((0, 0, 1408, 704))
        self.all_ok(d); self.assertGreaterEqual(len(d), 4)

    def test_world(self):
        s = gen_world.street([(0, 0), (1024, 0), (1024, 1024)])
        self.all_ok(s)
        self.assertAlmostEqual(P.volume(s[0][1]), 2048 * 256 * 16, delta=2048 * 256 * 16 * 0.01)     # road: length x width x depth (mitred)
        self.all_ok(gen_world.junction((0, 0))); self.all_ok(gen_world.fence([(0, 0, 0), (500, 0, 0)])); self.all_ok(gen_world.bank([(0, 0), (0, 512)]))
        sc = gen_world.scatter((0, 0, 1000, 1000), 128, avoid=[(400, 400, 600, 600)], z=lambda x, y: x * 0.01)
        self.assertGreater(len(sc), 20)
        self.assertGreaterEqual(min(math.dist(a['origin'][:2], b['origin'][:2]) for i, a in enumerate(sc) for b in sc[i + 1:]), 128)
        self.assertFalse(any(400 <= p['origin'][0] <= 600 and 400 <= p['origin'][1] <= 600 for p in sc))
        self.assertAlmostEqual(sc[0]['origin'][2], sc[0]['origin'][0] * 0.01)

    def test_kits(self):
        k = gen_kits.load('street_small')
        lamp = gen_kits.place(gen_kits.part(k, 'wall_lamp'), (0, 0, 100), normal=(0, -1, 0))
        self.assertEqual(lamp['angles'][1], 270.0); self.assertEqual(lamp['origin'], [0.0, 0.0, 100])
        pl = gen_kits.place(gen_kits.part(k, 'planter'), (0, 0, 100), normal=(1, 0, 0))
        self.assertEqual(pl['origin'][0], 3.5)                                       # its back (x = -3.5) touches the wall
        bench = gen_kits.place(gen_kits.part(k, 'bench'), (0, 0, 0), facing=(0, 1, 0))
        self.assertEqual(bench['angles'][1], 180.0)
        self.assertEqual(len(gen_kits.row(gen_kits.part(k, 'crate32'), (0, 0, 0), (256, 0, 0))), 6)
        self.assertAlmostEqual(gen_kits.stack(gen_kits.part(k, 'crate32'), (0, 0, 0), 3)[2]['origin'][2], 2 * 32.3 + 0.1, places=3)
        with self.assertRaises(ValueError): gen_kits.place(gen_kits.part(k, 'awning67'), (0, 0, 0), normal=(0, 0, 1))

    def test_gameplay(self):
        pl = gen_gameplay.competitive('defuse', {'t': (0, 0, 0), 'ct': (3000, 0, 0), 'a': (2500, 1500, 0), 'b': (2200, -1500, 0)},
                                      {'t-a': [(0, 0), (1000, 1500), (2500, 1500)]})
        self.assertEqual(len(pl['spawns'][2]), 5); self.assertEqual(pl['spawns'][2][0][2], 8.0)
        self.assertEqual(pl['timings']['t-a']['units'], round(math.dist((0, 0), (1000, 1500)) + 1500))
        self.assertTrue(any('site b' in b for b in pl['balance']))
        self.assertEqual(len(gen_gameplay.competitive('wingman', {'t': (0, 0, 0), 'ct': (1, 0, 0), 'a': (2, 0, 0)})['spawns'][3]), 2)
        h = gen_gameplay.competitive('hostage', {'t': (0, 0, 0), 'ct': (1000, 0, 0), 'a': (800, 500, 0)})
        self.assertEqual(len(h['hostages']), 2); self.assertIsNotNone(h['rescue'])
        self.assertIn('sv_autobunnyhopping 1', gen_gameplay.mode_config('bhop')['commands'])
        r = gen_gameplay.surf_ramp((0, 0), (1024, 0), 512)
        self.assertEqual(P.check(r), [])
        n = [f for f in range(len(r[1])) if abs(P._unit(P.newell(r[0], r[1][f]))[2]) > 0.1]
        self.assertTrue(all(abs(math.degrees(math.acos(abs(P._unit(P.newell(r[0], r[1][f]))[2]))) - 50) < 0.5 for f in n if P._unit(P.newell(r[0], r[1][f]))[2] > 0))
        self.all_ok(gen_gameplay.bhop_platforms((0, 0, 0), 4, rise=16))


BUILD = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, primitives as P, gen_layout, gen_buildings, gen_world, gen_kits, gen_gameplay, mechkit
P.CATALOG = None
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
gen_layout.write(gen_layout.build({'rooms': {'a': [0, 0, 256, 256], 'b': [256, 0, 512, 256]}, 'doors': [['a', 'b', 64, 96]]}))
gen_buildings.write(gen_buildings.building((1000, 0, 1384, 256), 2))
gen_world.write(gen_world.street([(0, -600), (1024, -600)]))
k = gen_kits.load('street_small')
gen_kits.props(gen_kits.row(gen_kits.part(k, 'crate32'), (0, -400, 0), (256, -400, 0)))
plan = gen_gameplay.competitive('defuse', {'t': (100, 100, 0), 'ct': (400, 100, 0), 'a': (100, 200, 0), 'b': (400, 200, 0)})
gen_gameplay.place_competitive(plan)
gen_gameplay.course_zones(((0, 0, 0), (64, 64, 64)), ((128, 0, 0), (192, 64, 64)))
vmapgen.finish(d, OUT, group='t')
'''


class Written(unittest.TestCase):
    def test_map(self):
        root = tempfile.mkdtemp(prefix='cs2mcp_gen_')
        try:
            out = F.make_map(os.path.join(root, 'gen.vmap'), BUILD)
            r = subprocess.run([sys.executable, os.path.join(F.CREATE, 'check_mesh.py'), out], capture_output=True, text=True, cwd=F.CREATE)
            self.assertTrue(r.stdout.strip().endswith(' 0 bad'), r.stdout + r.stderr)
            import vmapedit as V, collections
            m = V.Map(out)
            c = collections.Counter(m.cls(e) for e in m.entities())
            self.assertEqual((c['info_player_terrorist'], c['info_player_counterterrorist'], c['func_bomb_target'], c['func_buyzone']), (5, 5, 2, 2))
            self.assertEqual(c['prop_static'], 6); self.assertEqual(c['trigger_multiple'], 2)
            trig = [e for e in m.by_class('trigger_multiple')]
            self.assertEqual(sorted(m.conn_tuple(m.conns(t)[0])[3] for t in trig), ['kz_cp_0', 'kz_cp_1'])
        finally:
            shutil.rmtree(root, ignore_errors=True)


@unittest.skipUnless(__import__('fgdcat').fgd_paths(), 'CS2 not installed')
class StockNames(unittest.TestCase):
    def test_materials_and_models_exist(self):
        import fgdcat, vpk
        vs = [vpk.VPK(os.path.join(fgdcat.cs2_root(), 'game', sub, 'pak01_dir.vpk')) for sub in ('csgo', 'core')]
        has = lambda p: any(v.has(p + '_c') for v in vs)
        names = set(gen_layout.DEFAULT.values()) | set(gen_world.MATS.values()) | {P.DEFAULT_MAT}
        for st in gen_buildings.STYLES.values(): names |= set(st.values())
        names |= {p['model'] for p in gen_kits.load('street_small')['parts']}
        self.assertEqual(sorted(n for n in names if not has(n)), [])


if __name__ == '__main__':
    unittest.main()
