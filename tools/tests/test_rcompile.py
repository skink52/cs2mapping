"""rcompile.py: presets, command lines, output paths and the build-log reader. Never runs resourcecompiler.

  python -m unittest discover -s tools/tests -p "test_rcompile.py" -v
"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F      # noqa: F401  (puts tools/ on the path)
import rcompile as R

LOG = '''Creating render device for graphics adapter 0 'Intel(R) Arc(TM) B580 Graphics'
 - [VRAD3] VRAD3 - Distributed Lighting Tool
WARNING! No lightmap resolution volumes set for this geometry!
Failed loading resource "models/props/cs_assault/moneypallet02a.vmdl_c" (ERROR_FILEOPEN: File not found)
Error parsing string 't' as float64
RESOURCE COMPILE ERROR: materials/x/broken.vmat: Texture not found
Warning: Failed to create physics hulls for one or more meshes.
>>NAVGEN: pass 1
Nav mesh (maps/x) loaded with 812 nav areas
   900 compiled, 1 failed, 3 skipped, 0m:42s
0 failed
'''


class Log(unittest.TestCase):
    def test_analyze(self):
        r = R.analyze(LOG)
        self.assertEqual(r['summary'], {'compiled': 900, 'failed': 1, 'skipped': 3})
        self.assertEqual(r['missing_assets'], ['models/props/cs_assault/moneypallet02a.vmdl'])
        self.assertEqual(r['compile_errors'], ['materials/x/broken.vmat: Texture not found'])
        self.assertIn("Error parsing string 't' as float64", r['errors'])
        self.assertFalse(any('Failed loading resource' in e for e in r['errors']))     # listed under missing_assets instead
        self.assertFalse(any(e == '0 failed' for e in r['errors']))
        self.assertEqual(r['nav_areas'], 812)
        self.assertEqual(r['stage'], 'writing the map')
        self.assertTrue(any('toolslightmapres' in h for h in r['hints']))
        self.assertTrue(any('physics hull' in h for h in r['hints']))
        self.assertFalse(any('ray tracing' in h for h in r['hints']))                  # a normal light bake is not a GPU problem
        self.assertFalse(r['crashed'])

    def test_uncompiled_addon_material_hint(self):
        r = R.analyze("RESOURCE COMPILE WARNING: Mesh 'meshset_0' referencing missing material 'materials/ifr/sprawl/win_cool.vmat'")
        self.assertTrue(any('-fshallow' in h and 'rcompile.py asset' in h for h in r['hints']))

    def test_html_and_utf16(self):
        html_log = '<font color="#FF0000">Failed loading resource &quot;materials/a/b.vtex_c&quot;</font><br/>' \
                   '<font color="#FFFF00">ExtrudeReplaceHull failed to build new convex hull</font><br/>'
        r = R.analyze(html_log)
        self.assertEqual(r['missing_assets'], ['materials/a/b.vtex'])
        self.assertEqual(r['errors'], ['ExtrudeReplaceHull failed to build new convex hull'])
        fd, p = tempfile.mkstemp(suffix='.log'); os.close(fd)
        try:
            F.write(p, LOG.encode('utf-16'), 'wb')                         # what Tee-Object writes on Windows PowerShell 5.1
            self.assertEqual(R.analyze(R.read_log(p))['nav_areas'], 812)
        finally:
            os.remove(p)

    def test_crash_and_gpu(self):
        r = R.analyze('Exception: access violation 0xc0000005 writing x.mdmp\nVK_ERROR_DEVICE_LOST during bake: error\n')
        self.assertTrue(r['crashed'])
        self.assertIn(R.GPU_HINT, r['hints'])


class Argv(unittest.TestCase):
    CS2 = r'D:\Games\CS2'

    def test_presets(self):
        self.assertEqual(R.preset_flags('fast'), ['-world', '-phys', '-nolightmaps'])
        full = R.preset_flags('full', threads=6)
        self.assertIn('-vis', full); self.assertIn('-bakelighting', full); self.assertEqual(full[full.index('-sareverb_threads') + 1], '6')
        self.assertNotIn('-vis', R.preset_flags('final', novis=True))
        self.assertEqual(R.preset_flags('final')[R.preset_flags('final').index('-lightmapMaxResolution') + 1], '2048')
        with self.assertRaises(ValueError): R.preset_flags('ultra')

    def test_map_argv(self):
        vmap = os.path.join(self.CS2, 'content', 'csgo_addons', 'mg_x', 'maps', 'mg_x.vmap')
        a = R.map_argv(vmap, 'nav', threads=4, cs2=self.CS2)
        self.assertTrue(a[0].endswith(os.path.join('game', 'bin', 'win64', 'resourcecompiler.exe')))
        self.assertEqual(a[a.index('-i') + 1], vmap.replace('\\', '/'))
        self.assertEqual(a[-2:], ['-breakpad', '-nop4'])
        b = R.asset_argv([vmap], force=True, cs2=self.CS2, threads=2)
        self.assertEqual(b[-1], '-f'); self.assertIn('-nop4', b)

    def test_paths(self):
        vmap = os.path.join(self.CS2, 'content', 'csgo_addons', 'mg_x', 'maps', 'sub', 'a.vmap')
        self.assertEqual(R.addon_and_map(vmap), ('mg_x', 'a'))
        self.assertEqual(R.compiled_map(vmap, self.CS2), os.path.join(self.CS2, 'game', 'csgo_addons', 'mg_x', 'maps', 'sub', 'a.vpk'))
        self.assertEqual(R.addon_and_map(os.path.join('C:\\', 'links', 'content_addons', 'mg_y', 'maps', 'b.vmap')), ('mg_y', 'b'))

    def test_missing_compiler_refused(self):
        with self.assertRaises(FileNotFoundError):
            R.build_map(os.path.join(self.CS2, 'nope.vmap'), cs2=os.path.join(tempfile.gettempdir(), 'no_cs2_here'))


if __name__ == '__main__':
    unittest.main()
