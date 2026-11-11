"""tools/mcp_server.py round-2 tools over stdio: map_edit (create/mapops.py job), map_backups, release_plan, visual_check, material_create,
sound_create, model_build (dry run), mechanics_build, prop_note. Fake CS2 root: nothing is compiled, Blender is never started.

  python -m unittest discover -s tools/tests -p "test_mcp_round2.py" -v
"""
import json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
from test_mcp_server import Client

OPS = [
    {'op': 'box', 'mins': [0, 0, -16], 'maxs': [512, 512, 0]},
    {'op': 'mesh_edit', 'shape': {'shape': 'box', 'mins': [600, 0, 0], 'maxs': [664, 64, 64]},
     'edits': [{'edit': 'bevel', 'radius': 6}], 'cut': [{'shape': 'cylinder', 'center': [632, 32], 'radius': 12, 'z0': -8, 'z1': 72}], 'uv': {'fit': [1, 1]}},
    {'op': 'mesh_edit', 'shape': {'shape': 'box', 'mins': [700, 0, 0], 'maxs': [828, 128, 8]}, 'edits': [{'edit': 'subdivide', 'n': 4}], 'paint': 'x'},
    {'op': 'entity', 'cls': 'logic_relay', 'origin': [0, 0, 64], 'keys': {'targetname': 'r1'}},
    {'op': 'connect', 'from': 'r1', 'output': 'OnTrigger', 'target': 'r1', 'input': 'CancelPending'},
    {'op': 'brush', 'cls': 'trigger_multiple', 'shape': {'shape': 'box', 'mins': [0, 0, 0], 'maxs': [64, 64, 64], 'material': 'materials/tools/toolstrigger.vmat'},
     'keys': {'targetname': 't1'}},
    {'op': 'layout', 'plan': {'z': 0, 'rooms': {'a': [1000, 0, 1256, 256], 'b': [1256, 0, 1512, 256]}, 'doors': [['a', 'b', 64, 96]]}},
    {'op': 'building', 'footprint': [2000, 0, 2384, 256], 'floors': 2},
    {'op': 'street', 'path': [[0, -600], [1024, -600]]},
    {'op': 'scatter', 'area': [0, 1000, 512, 1512], 'spacing': 128},
    {'op': 'kit', 'kit': 'street_small', 'part': 'crate32', 'row': [[0, -400, 0], [256, -400, 0]]},
    {'op': 'competitive', 'kind': 'wingman', 'anchors': {'t': [100, 100, 0], 'ct': [400, 100, 0], 'a': [250, 400, 0]}},
    {'op': 'course', 'bhop': {'start': [0, 2000, 0], 'count': 3}},
    {'op': 'fx', 'lightning': {'name': 'storm', 'origin': [0, 0, 600]}},
    {'op': 'mechanics', 'config': {'abilities': [{'kind': 'double_jump'}]}, 'name': 'mech'},
]


class Round2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()
        cls.store = os.path.join(cls.root, 'backups')
        cls.atlas = os.path.join(cls.root, 'notes.json')
        env = dict(os.environ, CS2_ROOT=cls.root, CS2MAP_BACKUPS=cls.store, CS2MAP_ATLAS=cls.atlas, CS2MAP_CACHE=os.path.join(cls.root, 'b.json'),
                   CS2MCP_PLUGIN_DIR=os.path.join(cls.root, 'no_plugins'), PYTHONIOENCODING='utf-8')
        cls.c = Client(env)
        cls.c.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}})
        cls.c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        cls.content = os.path.join(cls.root, 'content', 'csgo_addons', 'test_addon')

    @classmethod
    def tearDownClass(cls):
        cls.c.close(); shutil.rmtree(cls.root, ignore_errors=True)

    def call(self, tool_name, **a):
        r = self.c.request('tools/call', {'name': tool_name, 'arguments': a})['result']
        self.assertFalse(r['isError'], r['content'][0]['text'][-1500:])
        return r['structuredContent']

    def test_1_map_edit_backup_restore(self):
        out = os.path.join(self.content, 'maps', 'gen.vmap')
        dry = self.call('map_edit', in_vmap=self.vmap, out_vmap=out, ops=OPS, dry_run=True, wait=120)
        self.assertEqual(dry['state'], 'done', dry); self.assertTrue(dry['result']['ok'], dry['result'])
        self.assertFalse(os.path.exists(out))
        job = self.call('map_edit', in_vmap=self.vmap, out_vmap=out, ops=OPS, wait=120)
        self.assertTrue(job['result']['ok'], job)
        self.assertEqual(len(job['result']['ops']), len(OPS))
        info = self.call('map_info', vmap=out)
        self.assertEqual(info['classes']['info_player_terrorist'], 3 + 2)       # fixture's 3 + wingman's 2
        self.assertIn('point_script', info['classes'])
        self.assertTrue(os.path.exists(os.path.join(self.content, 'maps', 'scripts', 'mech.js')))
        bad = self.call('map_edit', in_vmap=out, out_vmap=out, ops=[{'op': 'box', 'mins': [0, 0, 0], 'maxs': [1, 1, 1]}, {'op': 'nonsense'}], wait=120)
        self.assertFalse(bad['result']['ok']); self.assertEqual(bad['result']['failed_op'], 1)
        again = self.call('map_edit', in_vmap=out, out_vmap=out, ops=OPS[:1], wait=120)                # same group: replaced, backed up first
        self.assertTrue(again['result']['ok']); self.assertIsNotNone(again['result']['backup'])
        lst = self.call('map_backups', vmap=out)
        self.assertEqual(len(lst['backups']), 1)
        r = self.call('map_backups', action='restore', vmap=out, to=os.path.join(self.root, 'restored.vmap'))
        self.assertTrue(os.path.exists(r['to']))

    def test_2_release_visual(self):
        rel = self.call('release_plan', vmap=self.vmap)
        self.assertIn('models/test/missing.vmdl', rel['missing']); self.assertIn('PUBLISH', rel['publish_md'].upper())
        vis = self.call('visual_check', vmap=self.vmap)
        self.assertIn('counts', vis)

    def test_3_assets(self):
        m = self.call('material_create', content=self.content, name='wall1', source='pattern', value='bricks', color='#a05030')
        self.assertEqual(m['material'], 'materials/gen/wall1.vmat')
        d = self.call('material_create', content=self.content, name='exit', source='decal', value='EXIT')
        self.assertTrue(os.path.exists(os.path.join(self.content, 'materials', 'gen', 'exit_alpha.png')))
        s = self.call('sound_create', content=self.content, name='zap1', preset='zap', seconds=0.3, event='test.zap')
        self.assertEqual(s['vsnd'], 'sounds/gen/zap1.vsnd'); self.assertEqual(s['event']['events_in_block'], ['test.zap'])
        b = self.call('model_build', content=self.content, name='box1', template='crate')
        self.assertTrue(b['dry_run']); self.assertFalse(os.path.exists(b['vmdl']))          # the default is a dry run: nothing written
        b = self.call('model_build', content=self.content, name='box1', template='crate', dry_run=False, blender=False)
        self.assertFalse(b['dry_run']); self.assertTrue(os.path.exists(b['vmdl']))
        n = self.call('prop_note', model='models/x.vmdl', category='crate', tags=['wood'])
        self.assertEqual(json.load(open(self.atlas))['models/x.vmdl']['tags'], ['wood'])

    @unittest.skipUnless(shutil.which('node'), 'Node not installed')
    def test_4_mechanics(self):
        r = self.call('mechanics_build', config={'abilities': [{'kind': 'dash', 'key': 'attack2'}]}, content=self.content, name='dash', seconds=20)
        self.assertEqual(r['mock']['exit_code'], 0, r); self.assertIn('maps/scripts/dash.js', r['written'])


if __name__ == '__main__':
    unittest.main()
