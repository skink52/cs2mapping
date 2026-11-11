"""tools/kv3text.py, create/gen_light.py, create/gen_physics.py, and the MCP tools status / script_api / script_write / asset_search /
catalog_info plus map_edit's light and physics ops (fake CS2 root; nothing is compiled or launched).

  python -m unittest discover -s tools/tests -p "test_extras.py" -v
"""
import os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
import kv3text

KV = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc29:version{3cec427c-1b0e-4d48-a90a-0436f33a6041} -->
{
	// a comment
	rootNode =
	{
		_class = "RootNode"
		children = [ { _class = "RenderMeshFile" filename = "models/x.fbx" import_scale = 1.0 }, ]
		flags = [ 1, 2, 3 ]
		on = true
		off = false
		none = null
		model = resource_name:"models/x.vmdl"
		/* block
		   comment */
		text = """
two
lines"""
		"quoted key" = -12.5e1
	}
}
'''


class KV3(unittest.TestCase):
    def test_parse_and_roundtrip(self):
        d = kv3text.loads(KV)
        r = d.root['rootNode']
        self.assertEqual(r['children'][0]['filename'], 'models/x.fbx'); self.assertEqual(r['flags'], [1, 2, 3])
        self.assertIs(r['on'], True); self.assertIs(r['off'], False); self.assertIsNone(r['none'])
        self.assertEqual(r['model'], kv3text.Flagged('resource_name', 'models/x.vmdl'))
        self.assertEqual(r['text'], 'two\nlines'); self.assertEqual(r['quoted key'], -125.0)
        self.assertIn('modeldoc29', d.header)
        again = kv3text.loads(kv3text.dumps(d))
        self.assertEqual(repr(again.root), repr(d.root))
        with self.assertRaises(ValueError): kv3text.loads('{ a = ')


LIGHT = r'''
import os, sys
sys.path.insert(0, CREATE)
import vmapgen, primitives as P, gen_light, gen_physics
P.CATALOG = None
d = vmapgen.open_map(os.path.join(TOOLS, 'box_template.vmap'), os.path.dirname(OUT))
gen_light.light(((0, 0, 0), (1024, 1024, 512)), 'golden_hour')
gen_light.lamp((10, 10, 100), 'spot', name='spot1')
door = P.box((0, 0, 0), (8, 64, 96), 'materials/dev/reflectivity_50.vmat')
gen_physics.door(door, 'door1', move='+z')
gen_physics.button(P.box((20, 0, 40), (24, 8, 48)), 'btn1', [('door1', 'Open')])
gen_physics.lift(P.box((100, 100, 0), (164, 164, 8)), 'lift1', 256)
gen_physics.rotator(P.box((200, 200, 0), (232, 232, 32)), 'fan', axis='x')
gen_physics.breakable(P.box((300, 0, 0), (364, 4, 64)), 'glass1')
gen_physics.physics_prop('models/props/de_dust/dust_rusty_barrel.vmdl', (400, 0, 0))
gen_physics.zone(P.box((500, 0, 0), (564, 64, 64)), 'teleport', 'tp1', destination=(0, 0, 8))
gen_physics.zone(P.box((600, 0, 0), (664, 64, 64)), 'push', push_dir=(-45, 0, 0))
gen_physics.ladder((700, 0, 0), 256, facing=(1, 0))
vmapgen.finish(d, OUT, group='t')
'''


class LightPhysics(unittest.TestCase):
    @unittest.skipUnless(__import__('fgdcat').fgd_paths(), 'CS2 not installed (the map build reads its FGDs)')
    def test_entities(self):
        root = tempfile.mkdtemp(prefix='cs2mcp_lp_')
        try:
            out = F.make_map(os.path.join(root, 'lp.vmap'), LIGHT)
            import vmapedit as V, collections, subprocess
            m = V.Map(out)
            c = collections.Counter(m.cls(e) for e in m.entities())
            for cls in ('env_sky', 'light_environment', 'env_gradient_fog', 'env_combined_light_probe_volume', 'env_cubemap_box', 'light_omni2',
                        'func_door', 'func_button', 'func_movelinear', 'func_rotating', 'func_breakable', 'prop_physics_override',
                        'trigger_teleport', 'info_teleport_destination', 'trigger_push'):
                self.assertEqual(c[cls], 1, cls)
            sun = m.by_class('light_environment')[0]
            self.assertEqual(m.P(sun, 'skytexture'), 'sky'); self.assertEqual([round(x) for x in m.g(sun, b'angles')], [18, 250, 0])
            door = m.by_class('func_door')[0]
            self.assertEqual(m.P(door, 'movedir'), '-90 0 0'); self.assertEqual(m.P(door, 'lip'), '2.0')
            btn = m.by_class('func_button')[0]
            self.assertEqual(m.conn_tuple(m.conns(btn)[0])[:3], ('OnPressed', 'door1', 'Open'))
            self.assertEqual(m.P(m.by_class('func_rotating')[0], 'spawnflags'), '5')
            self.assertEqual(m.P(m.by_class('trigger_teleport')[0], 'target'), 'tp1_dest')
            mats = set()
            for n, _ in m.walk():
                if m.type(n) == b'CMapMesh':
                    mats |= {x.decode() if isinstance(x, bytes) else x for x in m.g(m.g(n, b'meshData'), b'materials')}
            self.assertIn('materials/tools/toolslightmapres.vmat', mats); self.assertIn('materials/tools/toolsinvisibleladder.vmat', mats)
            r = subprocess.run([sys.executable, os.path.join(F.CREATE, 'check_mesh.py'), out], capture_output=True, text=True, cwd=F.CREATE)
            self.assertTrue(r.stdout.strip().endswith(' 0 bad'), r.stdout)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    @unittest.skipUnless(__import__('fgdcat').fgd_paths(), 'CS2 not installed')
    def test_skies_and_keys_exist(self):
        import fgdcat, vpk
        sys.path.append(F.CREATE); import gen_light
        v = vpk.VPK(os.path.join(fgdcat.cs2_root(), 'game', 'csgo', 'pak01_dir.vpk'))
        self.assertEqual([p['sky'] for p in gen_light.PRESETS.values() if p.get('sky') and not v.has(p['sky'] + '_c')], [])
        cat = fgdcat.load()
        for cls, keys in (('light_environment', ['skycolor', 'skyintensity', 'skytexture']), ('env_gradient_fog', ['fogstartheight', 'fogendheight']),
                          ('func_movelinear', ['movedistance', 'startposition']), ('light_omni2', ['outer_angle', 'inner_angle'])):
            self.assertEqual([k for k in keys if k.lower() not in cat.keys(cls)], [], cls)


class McpExtras(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_mcp_server import Client
        cls.root, cls.vmap = F.temp_root()
        env = dict(os.environ, CS2_ROOT=cls.root, CS2MAP_BACKUPS=os.path.join(cls.root, 'bk'), CS2MCP_PLUGIN_DIR=os.path.join(cls.root, 'none'),
                   PYTHONIOENCODING='utf-8')
        cls.c = Client(env)
        cls.c.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}})
        cls.content = os.path.join(cls.root, 'content', 'csgo_addons', 'test_addon')

    @classmethod
    def tearDownClass(cls):
        cls.c.close(); shutil.rmtree(cls.root, ignore_errors=True)

    def call(self, tool_name, **a):
        r = self.c.request('tools/call', {'name': tool_name, 'arguments': a})['result']
        self.assertFalse(r['isError'], r['content'][0]['text'][-1500:])
        return r['structuredContent']

    def test_status_catalog_api(self):
        s = self.call('status')
        self.assertEqual(s['fgd_files'], 2); self.assertFalse(s['resourcecompiler'])
        c = self.call('catalog_info')
        self.assertIn('golden_hour', c['light_presets']); self.assertIn('street_small', c['kits'])
        api = self.call('script_api', query='OnPlayerJump')
        self.assertTrue(api['hits'][0]['decl'].startswith('OnPlayerJump'))
        a = self.call('asset_search', kind='model', words='crate', addon_content=self.content)
        self.assertIn('models/test/crate.vmdl  (addon)', a['assets'])

    @unittest.skipUnless(shutil.which('node'), 'Node not installed')
    def test_script_write(self):
        good = 'import { Instance } from "cs_script/point_script";\nInstance.OnRoundStart(() => Instance.Msg("hi"));\n'
        r = self.call('script_write', content=self.content, name='hello', code=good, seconds=10)
        self.assertEqual(r['mock']['exit_code'], 0); self.assertTrue(os.path.exists(r['written']))
        bad = 'import { Instance } from "cs_script/point_script";\nInstance.OnRoundStart(() => { null.x; });\n'
        r = self.call('script_write', content=self.content, name='broken', code=bad, seconds=10)
        self.assertNotEqual(r['mock']['exit_code'], 0); self.assertNotIn('written', r)

    def test_map_edit_light_physics(self):
        ops = [{'op': 'light', 'box': [[0, 0, 0], [512, 512, 256]], 'preset': 'night', 'lamps': [{'origin': [0, 0, 64], 'name': 'l1'}]},
               {'op': 'physics', 'kind': 'door', 'shape': {'shape': 'box', 'mins': [0, 0, 0], 'maxs': [8, 64, 96]}, 'name': 'd1'},
               {'op': 'physics', 'kind': 'button', 'shape': {'shape': 'box', 'mins': [20, 0, 40], 'maxs': [24, 8, 48]}, 'name': 'b1',
                'targets': [['d1', 'Open']]}]
        out = os.path.join(self.content, 'maps', 'lp.vmap')
        r = self.call('map_edit', in_vmap=self.vmap, out_vmap=out, ops=ops, wait=120)
        self.assertTrue(r['result']['ok'], r)
        info = self.call('map_info', vmap=out)
        self.assertEqual(info['classes'].get('func_door'), 1); self.assertEqual(info['classes'].get('light_omni2'), 1)


if __name__ == '__main__':
    unittest.main()
