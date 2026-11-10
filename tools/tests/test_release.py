"""release.py: dependency walk from a map, compiled-file mapping, PUBLISH.md, apply into a new addon (never uploads).

  python -m unittest discover -s tools/tests -p "test_release.py" -v
"""
import os, shutil, sys, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
import release as R


class Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()
        c = os.path.join(cls.root, 'content', 'csgo_addons', 'test_addon')
        g = os.path.join(cls.root, 'game', 'csgo_addons', 'test_addon')
        F.write(os.path.join(c, 'models', 'test', 'crate.vmdl'),
                '<!-- kv3 -->\n{ rootNode = { children = [ { _class = "RenderMeshFile" filename = "models/test/crate.fbx" } '
                '{ _class = "MaterialRemap" to = "materials/test/crate.vmat" } { to = "materials/dev/reflectivity_50.vmat" } ] } }')
        F.write(os.path.join(c, 'models', 'test', 'crate.fbx'), 'fbx')
        F.write(os.path.join(c, 'materials', 'test', 'crate.vmat'), 'Layer0\n{\n\tshader "csgo_complex.vfx"\n\tTextureColor "materials/test/crate_color.png"\n}\n')
        F.write(os.path.join(c, 'materials', 'test', 'crate_color.png'), 'png')
        F.write(os.path.join(c, 'materials', 'test', 'unused.vmat'), 'Layer0 { }')
        F.write(os.path.join(c, 'soundevents', 'soundevents_addon.vsndevts'), '<!-- kv3 -->\n{ ev = { vsnd_files_track_01 = "sounds/test/a.vsnd" } }')
        F.write(os.path.join(c, 'sounds', 'test', 'a.wav'), 'wav')
        F.write(os.path.join(c, 'addoninfo.txt'), '"AddonInfo" { }')
        F.write(os.path.join(c, 'resource', 'overviews', 'test_map.txt'), '"test_map" { }')
        for rel in ('maps/test_map.vpk', 'models/test/crate.vmdl_c', 'materials/test/crate.vmat_c', 'soundevents/soundevents_addon.vsndevts_c'):
            F.write(os.path.join(g, *rel.split('/')), b'x' * 1000, 'wb')
        old = time.time() - 3600
        os.utime(os.path.join(g, 'materials', 'test', 'crate.vmat_c'), (old, old))          # older than its source: stale
        cls.plan = R.Plan(cls.vmap, 'test_map_release', cs2=cls.root).build()
        cls.s = cls.plan.summary()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_sources(self):
        src = set(self.s['sources'])
        for rel in ('models/test/crate.vmdl', 'models/test/crate.fbx', 'materials/test/crate.vmat', 'materials/test/crate_color.png',
                    'soundevents/soundevents_addon.vsndevts', 'sounds/test/a.wav', 'addoninfo.txt', 'resource/overviews/test_map.txt'):
            self.assertIn(rel, src)
        self.assertNotIn('materials/test/unused.vmat', src)
        self.assertEqual(self.s['maps'], ['maps/test_map.vmap'])

    def test_missing_and_compiled(self):
        self.assertIn('materials/test/sky.vmat', self.s['missing'])
        self.assertIn('models/test/missing.vmdl', self.s['missing'])
        self.assertIn('maps/test_map.vpk', self.s['compiled'])
        self.assertIn('sounds/test/a.vsnd_c', self.s['compiled_missing'])
        self.assertIn('materials/test/crate.vmat_c', self.s['compiled_stale'])
        self.assertNotIn('materials/test/crate_color.vtex_c', self.s['compiled_missing'])    # images compile inside the vmat
        self.assertIn('Build first', self.s['publish_md']); self.assertIn('**test_map_release**', self.s['publish_md'])

    def test_apply(self):
        out = os.path.join(self.root, 'out')
        res = self.plan.apply(out)
        self.assertTrue(os.path.exists(os.path.join(out, 'content', 'csgo_addons', 'test_map_release', 'maps', 'test_map.vmap')))
        self.assertTrue(os.path.exists(os.path.join(out, 'game', 'csgo_addons', 'test_map_release', 'maps', 'test_map.vpk')))
        self.assertTrue(os.path.exists(os.path.join(out, 'content', 'csgo_addons', 'test_map_release', 'PUBLISH.md')))
        self.assertFalse(os.path.exists(os.path.join(out, 'content', 'csgo_addons', 'test_map_release', 'materials', 'test', 'unused.vmat')))
        with self.assertRaises(FileExistsError): self.plan.apply(out)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(R.main([self.vmap, '--name', 'test_addon']), 0)             # dry run never refuses
        with self.assertRaises(ValueError): R.Plan(self.vmap, 'test_addon', cs2=self.root).build().apply(self.root, force=True)


if __name__ == '__main__':
    unittest.main()
