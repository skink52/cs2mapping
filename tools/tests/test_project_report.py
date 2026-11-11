"""`python cs2mapping.py project-report` and the map digest's references: one read-only report from context.py, api.py and mapdigest.py.

  python -m unittest discover -s tools/tests -p "test_project_report.py" -v
"""
import contextlib, io, json, os, shutil, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import cs2mcp_fixtures as F
REPO = os.path.dirname(F.CREATE)
sys.path[:0] = [REPO, F.CREATE, os.path.join(F.CREATE, 'test')]
import cs2mapping, mapdigest


def tree(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            with open(p, 'rb') as h: out[os.path.relpath(p, root)] = (h.read(), os.stat(p).st_mtime_ns)
    return out


class ProjectReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.vmap = F.temp_root()
        import vmapedit as V
        m = V.Map(cls.vmap)
        m.new_entity('point_script', [0, 0, 0], {'targetname': 'io_script', 'cs_script': 'scripts/demo_io.vjs'})
        m.new_entity('prop_dynamic', [5, 0, 0], {'targetname': 'crate', 'model': 'models/demo/crate.vmdl'})
        m.new_entity('prop_dynamic', [9, 0, 0], {'model': 'models/demo/crate.vmdl'})
        m.new_entity('ambient_generic', [0, 9, 0], {'targetname': 'music', 'soundName': 'demo.music'})
        b = m.new_entity('func_button', [1, 1, 1], {'targetname': 'btn'})
        m.add_conn(b, 'OnPressed', 'io_script', 'RunScriptInput', 'start')
        m.add_conn(b, 'OnPressed', 'io_script', 'RunScriptInput', 'Cmd_3')
        m.add_conn(b, 'OnPressed', 'io_script', 'RunScriptInput', 'forgotten')
        m.add_conn(b, 'OnPressed', 'ambient_generic', 'StopSound')                  # a class name used as a target
        m.add_conn(b, 'OnPressed', 'ghost', 'Kill')
        m.save(cls.vmap)
        cls.proj = os.path.join(cls.root, 'demo_project')
        os.makedirs(os.path.join(cls.proj, 'scripts'))
        with open(os.path.join(cls.proj, 'README.md'), 'w', encoding='utf-8') as f: f.write('# Demo\n\n## To do\n- finish it\n')
        with open(os.path.join(cls.proj, 'scripts', 'demo_io.js'), 'w', encoding='utf-8') as f:
            f.write('import { Instance, Entities } from "cs_script/point_script";\nInstance.OnScriptInput("start", () => {});\n'
                    'for (let i = 0; i < 8; i++) Instance.OnScriptInput("Cmd_" + i, () => {});\n'
                    'Instance.Msg("old");\nEntities.FindByName("crate");\nInstance.MadeUpCall();\n')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_digest_references_class_targets_and_script_inputs(self):
        s = mapdigest.digest(self.vmap)['summary']
        self.assertEqual(s['references']['models']['models/demo/crate.vmdl'], 2)      # the fixture map brings two models of its own
        self.assertEqual(s['references']['scripts'], {'scripts/demo_io.vjs': 1}); self.assertEqual(s['references']['sounds'], {'demo.music': 1})
        self.assertEqual(s['reference_counts'], {'scripts': 1, 'models': len(s['references']['models']), 'sounds': 1})
        self.assertEqual(s['script_inputs'], {'Cmd_3': 1, 'forgotten': 1, 'start': 1})
        self.assertEqual(s['class_targets'], {'ambient_generic': 1})                # not reported as a missing entity
        self.assertEqual(s['dangling_targets'].get('ghost'), 1); self.assertNotIn('ambient_generic', s['dangling_targets'])

    def test_report_joins_the_three_tools_and_writes_nothing(self):
        before = tree(self.root)
        r = cs2mapping.project_report(self.proj, self.vmap)
        self.assertEqual(tree(self.root), before)
        self.assertEqual((r['project'], r['level'], r['manual_check_required']), ('demo_project', 'simulated', True))
        self.assertEqual([w['title'] for w in r['where']], ['To do'])
        self.assertEqual((r['api']['invalid'], r['api']['deprecated']), (1, 1))
        self.assertIn('Console.Log', r['scripts'][0]['deprecated'][0])
        m = r['map']
        self.assertEqual((m['references']['scripts'], m['references']['sounds']), (1, 1)); self.assertEqual(m['dangling_targets'].get('ghost'), 1)
        self.assertEqual(m['inputs_no_script_answers'], ['forgotten'])              # "start" is answered, "Cmd_3" by the "Cmd_" + i loop
        self.assertEqual(len(r['warnings']), 4)
        json.dumps(r)

    def test_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): rc = cs2mapping.main(['project-report', self.proj, '--vmap', self.vmap])
        text = out.getvalue()
        self.assertEqual(rc, 0); self.assertIn('never "works in game"', text); self.assertIn('RunScriptInput names no script answers: forgotten', text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out): cs2mapping.main(['project-report', self.proj, '--json'])
        self.assertNotIn('map', json.loads(out.getvalue()))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()): cs2mapping.main(['project-report'])


if __name__ == '__main__':
    unittest.main()
