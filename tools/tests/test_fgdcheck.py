"""fgdcat.py (FGD catalog) and fgdcheck.py (read-only vmap validation). Runs without CS2; the real-FGD test runs only where CS2 is installed.

  python -m unittest discover -s tools/tests -p "test_fgdcheck.py" -v
"""
import os, shutil, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
import fgdcat, fgdcheck


class Catalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = F.catalog()

    def test_classes_and_exclusions(self):
        c = self.cat
        self.assertTrue(c.is_entity('prop_dynamic'))
        self.assertFalse(c.is_entity('Targetname'))                       # base class
        self.assertFalse(c.is_entity('info_ladder_dismount'))             # @exclude
        self.assertTrue(c.is_entity('env_sky'))                           # excluded, then redefined by the game FGD
        self.assertIn('skyname', c.keys('env_sky'))                       # the later definition replaced the core one
        self.assertIn('info_ladder_dismount', c.excluded)

    def test_inheritance_remove_key_and_override(self):
        c = self.cat
        keys = c.keys('prop_dynamic')
        self.assertIn('targetname', keys); self.assertIn('rendercolor', keys)
        self.assertNotIn('old_key', keys)                                 # remove_key
        ins, outs = c.io('logic_relay')
        self.assertIn('cancelpending', ins); self.assertIn('trigger', ins); self.assertIn('kill', ins)   # @OverrideClass merged
        self.assertIn('onuser1', outs)
        self.assertEqual(c.helper_keys('env_combined_light_probe_volume'), {'box_mins', 'box_maxs'})

    def test_key_details(self):
        k = self.cat.keys('trigger_multiple')['spawnflags']
        self.assertEqual(k.type, 'flags'); self.assertEqual(k.default, '1'); self.assertEqual([v for v, _ in k.choices], ['1', '2', '4'])
        t = self.cat.keys('prop_dynamic')['targetname']
        self.assertTrue(t.help.endswith('continued over a line.'))        # "a" + "b" joined
        m = self.cat.keys('prop_dynamic')['model']
        self.assertEqual(m.type, 'resource:model')
        d = self.cat.defaults('prop_dynamic')
        self.assertEqual(d['solid'], '6'); self.assertEqual(d['rendermode'], 'kRenderNormal')

    def test_describe_search_similar(self):
        d = self.cat.describe('trigger_multiple')
        self.assertTrue(d['brush_entity']); self.assertIn('OnTrigger', d['outputs'])
        self.assertIn('error', self.cat.describe('info_ladder_dismount'))
        self.assertEqual(self.cat.search('relay')[0][0], 'logic_relay')
        self.assertIn('prop_dynamic', self.cat.similar('prop_dynamik'))


class Values(unittest.TestCase):
    def key(self, typ, choices=()):
        k = fgdcat.Key('k', typ); k.choices = list(choices); return k

    def test_types(self):
        vp = fgdcheck.value_problem
        self.assertIsNone(vp(self.key('integer'), '12')); self.assertIsNone(vp(self.key('integer'), '3.0'))
        self.assertEqual(vp(self.key('integer'), '3.5')[0], 'bad_value')
        self.assertEqual(vp(self.key('float'), 't')[0], 'bad_value')    # ba_jail_seaside's buoyancyScale "t" (build log: "Error parsing string 't'")
        self.assertIsNone(vp(self.key('boolean'), '1')); self.assertEqual(vp(self.key('boolean'), '2')[0], 'bad_value')
        self.assertIsNone(vp(self.key('color255'), '255 128 0')); self.assertEqual(vp(self.key('color255'), '255 0')[0], 'bad_value')
        self.assertIsNone(vp(self.key('vector'), '1 2 3')); self.assertEqual(vp(self.key('vector'), '1 2')[0], 'bad_value')
        self.assertIsNone(vp(self.key('integer'), ''))                    # empty is always allowed

    def test_choices(self):
        vp = fgdcheck.value_problem
        named = self.key('choices', [('kRenderNormal', ''), ('kRenderTransColor', ''), ('15', 'Distort')])
        self.assertIsNone(vp(named, 'krendernormal'))
        self.assertIsNone(vp(named, '1'))                                 # index into the named values (importer writes these)
        self.assertIsNone(vp(named, '15'))
        self.assertEqual(vp(named, '7')[0], 'bad_choice')
        ints = self.key('intchoices', [('0', ''), ('6', '')])
        self.assertIsNone(vp(ints, '6')); self.assertEqual(vp(ints, '2')[0], 'bad_choice')


class Check(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()
        cls.res = fgdcheck.run(cls.vmap, cs2=cls.root, cat=F.catalog())
        cls.codes = {}
        for f in cls.res['findings']: cls.codes.setdefault(f['code'], []).append(f['text'])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def has(self, code, text):
        self.assertTrue(any(text in t for t in self.codes.get(code, [])), '%s with %r not in %s' % (code, text, self.codes.get(code)))

    def test_addon_found_from_path(self):
        self.assertEqual(self.res['addon'], 'test_addon')

    def test_classes(self):
        self.has('excluded_class', 'info_ladder_dismount')
        self.has('unknown_class', 'prop_physics_respawnable')

    def test_io(self):
        self.has('dangling_target', 'door_nowhere')
        self.has('bad_input', 'relay1.Explode')
        self.has('bad_output', 'OnTriggered')
        self.assertFalse(any('CancelPending' in t for t in self.codes.get('bad_input', [])))
        self.assertFalse(any('relay1.Trigger' in t for t in self.codes.get('bad_input', [])))

    def test_keys_values_targets(self):
        self.has('unknown_key', 'bogus'); self.has('unknown_key', 'old_key')
        self.has('bad_value', 'renderamt'); self.has('bad_value', 'rendercolor')
        self.has('bad_choice', 'solid = "3"')
        self.has('key_target', 'no_such_filter')
        self.assertNotIn('unknown_key', [f['code'] for f in self.res['findings'] if f['cls'] == 'env_combined_light_probe_volume'])

    def test_assets(self):
        self.has('missing_asset', 'models/test/missing.vmdl')
        self.has('missing_asset', 'materials/test/sky.vmat')
        self.assertFalse(any('crate.vmdl' in t for t in self.codes.get('missing_asset', [])))   # exists in the addon content folder
        self.has('missing_material', 'toolstrigger')                     # the fake install has no VPKs

    def test_no_assets_mode_and_exit_code(self):
        res = fgdcheck.run(self.vmap, cs2=self.root, cat=F.catalog(), use_assets=False)
        self.assertFalse(any(f['code'] in ('missing_asset', 'missing_material') for f in res['findings']))
        self.assertGreater(res['errors'], 0)

    def test_map_is_untouched(self):
        before = open(self.vmap, 'rb').read()
        fgdcheck.run(self.vmap, cs2=self.root, cat=F.catalog())
        self.assertEqual(open(self.vmap, 'rb').read(), before)


@unittest.skipUnless(fgdcat.fgd_paths(), 'CS2 not installed')
class RealFGDs(unittest.TestCase):
    def test_installed_catalog(self):
        cat = fgdcat.load()
        for cls in ('prop_dynamic', 'trigger_multiple', 'func_buyzone', 'light_environment', 'point_script', 'info_player_terrorist'):
            self.assertTrue(cat.is_entity(cls), cls)
        self.assertFalse(cat.is_entity('info_ladder_dismount'))
        self.assertIn('enable', cat.io('trigger_multiple')[0])

    def test_matches_mapcheck_parser(self):
        import mapcheck
        classes, excluded = mapcheck.parse_fgd(mapcheck.fgd_files())
        cat = fgdcat.load()
        self.assertEqual(excluded, cat.excluded)
        for name in classes:
            i, o = mapcheck.io(classes, name)
            ci, co = cat.io(name)
            self.assertEqual((i, o), (set(ci), set(co)), name)


if __name__ == '__main__':
    unittest.main()
