"""The three helpers an agent reads before it writes: tools/mapdigest.py (a .vmap's entities and wiring), create/test/api.py (the
cs_script typings, and a check of a script's calls against them), create/context.py (a project snapshot). All three only read.

  python -m unittest discover -s tools/tests -p "test_agent_tools.py" -v
"""
import contextlib, io, json, os, shutil, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs2mcp_fixtures as F
sys.path[:0] = [F.CREATE, os.path.join(F.CREATE, 'test')]
import mapdigest, api, context


def tree(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            with open(p, 'rb') as h: out[os.path.relpath(p, root)] = (h.read(), os.stat(p).st_mtime_ns)
    return out


def run(fn, argv):
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err): code = fn(argv)
    return code, buf.getvalue(), err.getvalue()


class MapDigest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()
        import vmapedit as V
        m = V.Map(cls.vmap)
        a = m.new_entity('logic_relay', [10, 20, 30], {'targetname': 'relay_a'})
        m.new_entity('func_door', [100, 0, 0], {'targetname': 'door_1', 'parentname': 'lift'})
        m.add_conn(a, 'OnTrigger', 'door_1', 'Open', '', 0.5, 1)
        m.add_conn(a, 'OnTrigger', 'nobody_home', 'Kill')
        m.add_conn(a, 'OnTrigger', '!activator', 'SetHealth', '100')
        m.save(cls.vmap)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_entities_wiring_and_dangling_targets(self):
        d = mapdigest.digest(self.vmap)
        by = {e.get('name'): e for e in d['entities'] if e.get('name')}
        self.assertEqual(by['relay_a']['origin'], [10.0, 20.0, 30.0])
        self.assertEqual(by['relay_a']['out'][0], ['OnTrigger', 'door_1', 'Open', '', 0.5, 1])
        self.assertEqual(by['door_1']['parent'], 'lift')
        s = d['summary']
        self.assertEqual(s['dangling_targets'].get('nobody_home'), 1)               # a target nothing is named: flagged
        self.assertEqual(s['special_targets'].get('!activator'), 1); self.assertNotIn('!activator', s['dangling_targets'])
        self.assertNotIn('door_1', s['dangling_targets'])
        self.assertEqual(s['entities'], s['entities_in_map']); self.assertGreater(s['meshes'], 0); self.assertEqual(len(s['bounds']), 2)
        self.assertEqual(d['level'], 'untested')                                    # a read of the file proves nothing about the map in game
        self.assertNotIn('vertexData', json.dumps(d)); self.assertLess(len(mapdigest.dumps(d)), os.path.getsize(self.vmap))

    def test_filters(self):
        logic = mapdigest.digest(self.vmap, classes=['logic_*'])['entities']
        self.assertIn('relay_a', [e.get('name') for e in logic]); self.assertTrue(all(e['class'].startswith('logic_') for e in logic))
        self.assertEqual([e.get('name') for e in mapdigest.digest(self.vmap, names=['door_?'])['entities']], ['door_1'])
        near = mapdigest.digest(self.vmap, near=[10, 20, 30, 5])['entities']
        self.assertIn('relay_a', [e.get('name') for e in near]); self.assertNotIn('door_1', [e.get('name') for e in near])
        self.assertEqual(sorted(e['name'] for e in mapdigest.digest(self.vmap, touches=['door_1'])['entities']), ['door_1', 'relay_a'])
        lim = mapdigest.digest(self.vmap, limit=1)
        self.assertEqual(len(lim['entities']), 1); self.assertTrue(lim['summary']['truncated']); self.assertGreater(lim['summary']['entities'], 1)

    def test_graph_and_cli_never_write_the_map(self):
        before = tree(self.root)
        code, out, _ = run(mapdigest.main, [self.vmap, '--graph', '--class', 'logic_relay'])
        self.assertEqual(code, 0)
        self.assertIn('relay_a (logic_relay) OnTrigger -> door_1.Open [0.5s] [once]', out)
        code, out, _ = run(mapdigest.main, [self.vmap, '--summary'])
        self.assertEqual(json.loads(out)['summary']['dangling_targets'].get('nobody_home'), 1)
        code, out, _ = run(mapdigest.main, [self.vmap])
        self.assertTrue(json.loads(out)['entities'])
        self.assertEqual(run(mapdigest.main, [self.vmap, '--out', self.vmap])[0], 2)                       # never over the map
        self.assertEqual(run(mapdigest.main, [self.vmap, '--out', os.path.join(self.root, 'x.vmap')])[0], 2)
        self.assertEqual(run(mapdigest.main, [os.path.join(self.root, 'missing.vmap')])[0], 2)
        self.assertEqual(run(mapdigest.main, [self.vmap, '--near', '1,2'])[0], 2)
        self.assertEqual(tree(self.root), before)
        out_json = os.path.join(self.root, 'digest.json')
        self.assertEqual(run(mapdigest.main, [self.vmap, '--out', out_json])[0], 0)
        with open(out_json, encoding='utf-8') as f: self.assertTrue(json.load(f)['entities'])


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='api_')
        self.decls = api.parse(os.path.join(F.CREATE, 'test', 'point_script.d.ts'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def script(self, body):
        p = os.path.join(self.tmp, 's%d.js' % len(os.listdir(self.tmp)))        # a new file each time: earlier scripts stay as they were
        with open(p, 'w', encoding='utf-8') as f: f.write('import { Instance, Entities } from "cs_script/point_script";\n' + body)
        return p

    def test_the_typings_parse_into_members(self):
        names = {(d['container'], d['name']) for d in self.decls}
        self.assertIn(('IPointScript', 'Msg'), names); self.assertIn(('IEntities', 'FindByName'), names)
        self.assertTrue(any(d['kind'] == 'enum' and d['name'] == 'CSInputs' for d in self.decls))
        self.assertGreater(sum(1 for d in self.decls if d['kind'] == 'member'), 300)

    def test_lookup(self):
        code, out, _ = run(api.main, ['FindByName'])
        self.assertEqual(code, 0); self.assertIn('IEntities.FindByName', out); self.assertIn('(', out)
        self.assertEqual(run(api.main, ['NoSuchCallAnywhereAtAll'])[0], 1)
        code, out, _ = run(api.main, ['--members', 'Entities'])                    # the global name resolves to its interface
        self.assertEqual(code, 0); self.assertIn('FindByClass', out)

    def test_check_catches_an_invented_call_and_a_deprecated_one(self):
        good = self.script('Instance.DebugSphere({});\nconst e = Entities.FindByName("door");\n// Instance.MadeUpInAComment();\n')
        self.assertEqual(api.check(self.decls, good), ([], []))
        bad = self.script('Instance.TeleportEveryoneHome();\nconst e = Instance.FindEntityByName("door");\ne.GetHealthPercentageNow();\n')
        unknown, deprecated = api.check(self.decls, bad)
        self.assertEqual([l for l, _ in unknown], [2, 4])
        self.assertIn('Instance.TeleportEveryoneHome is not in the typings', unknown[0][1])
        self.assertIn('GetHealthPercentageNow', unknown[1][1])
        self.assertEqual([l for l, _ in deprecated], [3])
        self.assertEqual(run(api.main, ['--check', bad])[0], 1)
        self.assertEqual(run(api.main, ['--check', good])[0], 0)
        dep_only = self.script('Instance.FindEntityByName("door");\n')
        self.assertEqual(run(api.main, ['--check', dep_only])[0], 0)               # listed, not fatal ...
        self.assertEqual(run(api.main, ['--strict', '--check', dep_only])[0], 1)   # ... unless asked

    def test_a_script_that_moved_to_the_right_object_gets_the_hint(self):
        moved = self.script('Instance.FindByName("door");\n')
        unknown, _ = api.check(self.decls, moved)
        self.assertIn('declared on: IEntities', unknown[0][1])

    def test_every_tracked_port_script_calls_only_what_exists(self):
        import glob
        ports = sorted(glob.glob(os.path.join(F.CREATE, '..', 'ports', '*', 'scripts', '*.js')))
        self.assertGreater(len(ports), 20)
        bad = [(os.path.basename(p), u) for p in ports for u in api.check(self.decls, p)[0]]
        self.assertEqual(bad, [])


class Context(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ctx_'); self.proj = os.path.join(self.tmp, 'demo-cs2')
        os.makedirs(os.path.join(self.proj, 'docs')); os.makedirs(os.path.join(self.proj, 'src')); os.makedirs(os.path.join(self.proj, 'test'))
        with open(os.path.join(self.proj, 'docs', 'STATUS.md'), 'w', encoding='utf-8') as f:
            f.write('# Demo notes\n\n## Resume here\n' + ''.join('- step %d\n' % i for i in range(60)) + '\n## History\nold stuff ' * 1 + '\n' + 'x' * 20000 + '\n## Next steps\n1. ship it\n')
        with open(os.path.join(self.proj, 'README.md'), 'w', encoding='utf-8') as f: f.write('# Demo\n\nRun `node test/sim.cjs` then `sh test/run_mock.sh`.\n')
        with open(os.path.join(self.proj, 'src', 'main.js'), 'w', encoding='utf-8') as f:
            f.write('import { Instance } from "cs_script/point_script";\nInstance.OnScriptInput("start", () => {});\nInstance.Msg("x");\nInstance.FindEntityByName("a");\nInstance.NotARealCall();\n')
        with open(os.path.join(self.proj, 'test', 'sim.cjs'), 'w') as f: f.write('// test\n')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_snapshot_is_small_points_at_lines_and_changes_nothing(self):
        before = tree(self.tmp)
        s = context.snapshot(self.proj, lines=10)
        text = context.render(s, max_bytes=12000)
        self.assertEqual(tree(self.tmp), before)
        self.assertEqual([w['title'] for w in s['where']], ['Resume here', 'Next steps'])
        self.assertEqual((len(s['where'][0]['text']), s['where'][0]['more'], s['where'][0]['line']), (10, 50, 3))
        self.assertIn('[docs/STATUS.md line 3]', text); self.assertIn('50 more lines', text)
        self.assertLess(len(text), 4000); self.assertGreater(s['status_bytes'], 20000)       # 20 KB of history stayed out
        self.assertIn('script inputs answered: start', text)
        self.assertIn('NOT IN THE TYPINGS: Instance.NotARealCall', text)
        self.assertIn('deprecated in the typings: Instance.FindEntityByName', text)
        self.assertIn('run: node test/sim.cjs', text); self.assertIn('sim.cjs', text)

    def test_context_json_and_cli(self):
        with open(os.path.join(self.proj, 'context.json'), 'w') as f: json.dump({'sections': ['Next steps'], 'notes': 'paused'}, f)
        s = context.snapshot(self.proj)
        self.assertEqual([w['title'] for w in s['where']], ['Next steps'])
        code, out, _ = run(context.main, [self.proj, '--max-bytes', '300'])
        self.assertEqual(code, 0); self.assertIn('paused', out); self.assertIn('cut at 300 bytes', out)
        code, out, _ = run(context.main, [self.proj, '--json'])
        self.assertEqual(json.loads(out)['project'], 'demo-cs2')
        with self.assertRaises(SystemExit): context.find_project('no-such-project-anywhere')

    def test_real_projects_render(self):
        for name in ('cs2mapTTT', 'trenchwarfare-cs2'):
            s = context.snapshot(context.find_project(name), lines=5)
            self.assertTrue(s['docs']); self.assertLess(len(context.render(s, 12000).encode('utf-8')), 12200)


if __name__ == '__main__':
    unittest.main()
